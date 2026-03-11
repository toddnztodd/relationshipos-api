"""Territory Intelligence — CRUD, coverage, farming programs, and territory signals."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, distinct, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import (
    CoverageActivity,
    FarmingProgram,
    Person,
    Property,
    PropertyOwner,
    PropertyPerson,
    Signal,
    Territory,
    TerritoryProperty,
)
from app.schemas.territory import (
    CoverageActivityCreate,
    CoverageActivityResponse,
    CoverageSummary,
    FarmingProgramCreate,
    FarmingProgramResponse,
    FarmingProgramUpdate,
    TerritoryCreate,
    TerritoryDetail,
    TerritoryListItem,
    TerritoryPropertyCreate,
    TerritoryPropertyResponse,
    TerritorySummaryStats,
    TerritoryUpdate,
)
from app.schemas.signal import SignalResponse
from app.services.auth import get_current_user


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _compute_territory_stats(
    db: AsyncSession, territory_id: int, user_id: int
) -> TerritorySummaryStats:
    """Compute summary stats for a territory."""
    now = datetime.now(timezone.utc)
    ninety_days_ago = now - timedelta(days=90)

    # Property IDs in this territory
    prop_ids_q = select(TerritoryProperty.property_id).where(
        TerritoryProperty.territory_id == territory_id
    )
    prop_ids_result = await db.execute(prop_ids_q)
    prop_ids = [r[0] for r in prop_ids_result.fetchall()]

    if not prop_ids:
        return TerritorySummaryStats()

    property_count = len(prop_ids)

    # Owners known: properties with at least one linked owner
    owners_q = select(func.count(distinct(PropertyOwner.property_id))).where(
        and_(
            PropertyOwner.property_id.in_(prop_ids),
            PropertyOwner.user_id == user_id,
        )
    )
    owners_known = (await db.execute(owners_q)).scalar() or 0

    # Relationships known: distinct contacts linked to properties via PropertyPerson
    rels_q = select(func.count(distinct(PropertyPerson.person_id))).where(
        and_(
            PropertyPerson.property_id.in_(prop_ids),
            PropertyPerson.owner_id == user_id,
        )
    )
    relationships_known = (await db.execute(rels_q)).scalar() or 0

    # Recent sales: properties with last_listing_result = 'sold' in last 90 days
    sales_q = select(func.count()).where(
        and_(
            Property.id.in_(prop_ids),
            Property.user_id == user_id,
            Property.last_listing_result == "sold",
            Property.last_listed_date >= ninety_days_ago.date(),
        )
    )
    recent_sales = (await db.execute(sales_q)).scalar() or 0

    # Recent listings: properties with last_listed_date in last 90 days
    listings_q = select(func.count()).where(
        and_(
            Property.id.in_(prop_ids),
            Property.user_id == user_id,
            Property.last_listed_date >= ninety_days_ago.date(),
        )
    )
    recent_listings = (await db.execute(listings_q)).scalar() or 0

    # Signal count: active signals for properties in territory
    signals_q = select(func.count()).where(
        and_(
            Signal.user_id == user_id,
            Signal.entity_type == "property",
            Signal.entity_id.in_(prop_ids),
            Signal.is_active == True,
        )
    )
    signal_count = (await db.execute(signals_q)).scalar() or 0

    return TerritorySummaryStats(
        property_count=property_count,
        owners_known=owners_known,
        relationships_known=relationships_known,
        recent_sales=recent_sales,
        recent_listings=recent_listings,
        signal_count=signal_count,
    )


# ── Territory CRUD Router ───────────────────────────────────────────────────

router = APIRouter(prefix="/territories", tags=["Territories"])


@router.get("/", response_model=list[TerritoryListItem])
async def list_territories(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all territories with summary stats."""
    result = await db.execute(
        select(Territory)
        .where(Territory.user_id == user.id)
        .order_by(Territory.created_at.desc())
    )
    territories = result.scalars().all()

    items = []
    for t in territories:
        stats = await _compute_territory_stats(db, t.id, user.id)
        item = TerritoryListItem.model_validate(t)
        item.stats = stats
        items.append(item)
    return items


@router.post("/", response_model=TerritoryDetail, status_code=201)
async def create_territory(
    data: TerritoryCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new territory."""
    territory = Territory(
        user_id=user.id,
        name=data.name,
        type=data.type,
        notes=data.notes,
        boundary_data=data.boundary_data,
        map_image_url=data.map_image_url,
    )
    db.add(territory)
    await db.commit()
    await db.refresh(territory)
    stats = await _compute_territory_stats(db, territory.id, user.id)
    detail = TerritoryDetail.model_validate(territory)
    detail.stats = stats
    detail.properties = []
    detail.farming_programs = []
    return detail


@router.get("/{territory_id}", response_model=TerritoryDetail)
async def get_territory(
    territory_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get territory detail with properties, coverage stats, signals, and farming programs."""
    result = await db.execute(
        select(Territory).where(
            Territory.id == territory_id, Territory.user_id == user.id
        )
    )
    territory = result.scalar_one_or_none()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    stats = await _compute_territory_stats(db, territory.id, user.id)

    # Get linked properties
    props_result = await db.execute(
        select(TerritoryProperty)
        .options(selectinload(TerritoryProperty.property))
        .where(TerritoryProperty.territory_id == territory.id)
    )
    prop_links = props_result.scalars().all()
    properties = [
        {
            "id": pl.property.id,
            "address": pl.property.address,
            "linked_manually": pl.linked_manually,
            "territory_property_id": pl.id,
        }
        for pl in prop_links
        if pl.property
    ]

    # Get farming programs
    fp_result = await db.execute(
        select(FarmingProgram).where(FarmingProgram.territory_id == territory.id)
    )
    fps = fp_result.scalars().all()
    farming_programs = [FarmingProgramResponse.model_validate(fp) for fp in fps]

    detail = TerritoryDetail.model_validate(territory)
    detail.stats = stats
    detail.properties = properties
    detail.farming_programs = farming_programs
    return detail


@router.put("/{territory_id}", response_model=TerritoryDetail)
async def update_territory(
    territory_id: int,
    data: TerritoryUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a territory."""
    result = await db.execute(
        select(Territory).where(
            Territory.id == territory_id, Territory.user_id == user.id
        )
    )
    territory = result.scalar_one_or_none()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(territory, key, value)
    await db.commit()
    await db.refresh(territory)

    stats = await _compute_territory_stats(db, territory.id, user.id)
    detail = TerritoryDetail.model_validate(territory)
    detail.stats = stats
    detail.properties = []
    detail.farming_programs = []
    return detail


@router.delete("/{territory_id}", status_code=204)
async def delete_territory(
    territory_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a territory and all linked data."""
    result = await db.execute(
        select(Territory).where(
            Territory.id == territory_id, Territory.user_id == user.id
        )
    )
    territory = result.scalar_one_or_none()
    if not territory:
        raise HTTPException(status_code=404, detail="Territory not found")
    await db.delete(territory)
    await db.commit()


# ── Territory Property Links ────────────────────────────────────────────────

@router.post("/{territory_id}/properties", response_model=TerritoryPropertyResponse, status_code=201)
async def link_property_to_territory(
    territory_id: int,
    data: TerritoryPropertyCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Link a property to a territory."""
    # Verify territory belongs to user
    result = await db.execute(
        select(Territory).where(
            Territory.id == territory_id, Territory.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Territory not found")

    # Check for duplicate
    existing = await db.execute(
        select(TerritoryProperty).where(
            TerritoryProperty.territory_id == territory_id,
            TerritoryProperty.property_id == data.property_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Property already linked to this territory")

    link = TerritoryProperty(
        territory_id=territory_id,
        property_id=data.property_id,
        linked_manually=True,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return TerritoryPropertyResponse.model_validate(link)


@router.delete("/{territory_id}/properties/{property_id}", status_code=204)
async def unlink_property_from_territory(
    territory_id: int,
    property_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlink a property from a territory."""
    result = await db.execute(
        select(Territory).where(
            Territory.id == territory_id, Territory.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Territory not found")

    link_result = await db.execute(
        select(TerritoryProperty).where(
            TerritoryProperty.territory_id == territory_id,
            TerritoryProperty.property_id == property_id,
        )
    )
    link = link_result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)
    await db.commit()


# ── Coverage Activities ──────────────────────────────────────────────────────

coverage_router = APIRouter(prefix="/coverage-activities", tags=["Coverage Activities"])


@coverage_router.post("/", response_model=CoverageActivityResponse, status_code=201)
async def log_coverage_activity(
    data: CoverageActivityCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log a coverage activity."""
    activity = CoverageActivity(
        user_id=user.id,
        territory_id=data.territory_id,
        property_id=data.property_id,
        person_id=data.person_id,
        activity_type=data.activity_type,
        notes=data.notes,
        completed_at=data.completed_at or func.now(),
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return CoverageActivityResponse.model_validate(activity)


@router.get("/{territory_id}/coverage", response_model=CoverageSummary)
async def get_coverage_summary(
    territory_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get coverage summary for a territory."""
    # Verify territory
    result = await db.execute(
        select(Territory).where(
            Territory.id == territory_id, Territory.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Territory not found")

    # Get all property IDs in territory
    prop_ids_result = await db.execute(
        select(TerritoryProperty.property_id).where(
            TerritoryProperty.territory_id == territory_id
        )
    )
    prop_ids = [r[0] for r in prop_ids_result.fetchall()]
    total_properties = len(prop_ids)

    if not prop_ids:
        return CoverageSummary(total_properties=0)

    # Properties with at least one coverage activity (territory_intro, door_knock, etc.)
    introduced_q = select(func.count(distinct(CoverageActivity.property_id))).where(
        and_(
            CoverageActivity.user_id == user.id,
            CoverageActivity.territory_id == territory_id,
            CoverageActivity.property_id.in_(prop_ids),
        )
    )
    properties_introduced = (await db.execute(introduced_q)).scalar() or 0

    # Properties with a linked person (relationship exists)
    with_rel_q = select(func.count(distinct(PropertyPerson.property_id))).where(
        and_(
            PropertyPerson.property_id.in_(prop_ids),
            PropertyPerson.owner_id == user.id,
        )
    )
    properties_with_relationship = (await db.execute(with_rel_q)).scalar() or 0

    properties_untouched = total_properties - properties_introduced

    # Recent activities for this territory (last 20)
    recent_q = (
        select(CoverageActivity)
        .where(
            CoverageActivity.user_id == user.id,
            CoverageActivity.territory_id == territory_id,
        )
        .order_by(CoverageActivity.completed_at.desc())
        .limit(20)
    )
    recent_result = await db.execute(recent_q)
    recent = [
        CoverageActivityResponse.model_validate(a)
        for a in recent_result.scalars().all()
    ]

    return CoverageSummary(
        total_properties=total_properties,
        properties_introduced=properties_introduced,
        properties_with_relationship=properties_with_relationship,
        properties_untouched=max(0, properties_untouched),
        recent_activities=recent,
    )


# ── Farming Programs ─────────────────────────────────────────────────────────

farming_router = APIRouter(prefix="/farming-programs", tags=["Farming Programs"])


@farming_router.post("/", response_model=FarmingProgramResponse, status_code=201)
async def create_farming_program(
    data: FarmingProgramCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a farming program."""
    # Verify territory
    result = await db.execute(
        select(Territory).where(
            Territory.id == data.territory_id, Territory.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Territory not found")

    program = FarmingProgram(
        user_id=user.id,
        territory_id=data.territory_id,
        title=data.title,
        recurrence=data.recurrence,
        next_due_date=data.next_due_date,
        notes=data.notes,
    )
    db.add(program)
    await db.commit()
    await db.refresh(program)
    return FarmingProgramResponse.model_validate(program)


@router.get("/{territory_id}/farming-programs", response_model=list[FarmingProgramResponse])
async def list_farming_programs(
    territory_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List farming programs for a territory."""
    result = await db.execute(
        select(Territory).where(
            Territory.id == territory_id, Territory.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Territory not found")

    fp_result = await db.execute(
        select(FarmingProgram)
        .where(FarmingProgram.territory_id == territory_id)
        .order_by(FarmingProgram.next_due_date.asc().nullslast())
    )
    return [FarmingProgramResponse.model_validate(fp) for fp in fp_result.scalars().all()]


@farming_router.put("/{program_id}", response_model=FarmingProgramResponse)
async def update_farming_program(
    program_id: int,
    data: FarmingProgramUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a farming program (mark completed, update next due, etc.)."""
    result = await db.execute(
        select(FarmingProgram).where(
            FarmingProgram.id == program_id, FarmingProgram.user_id == user.id
        )
    )
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Farming program not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(program, key, value)
    await db.commit()
    await db.refresh(program)
    return FarmingProgramResponse.model_validate(program)


@farming_router.delete("/{program_id}", status_code=204)
async def delete_farming_program(
    program_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a farming program."""
    result = await db.execute(
        select(FarmingProgram).where(
            FarmingProgram.id == program_id, FarmingProgram.user_id == user.id
        )
    )
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Farming program not found")
    await db.delete(program)
    await db.commit()


# ── Territory Signals ────────────────────────────────────────────────────────

@router.get("/{territory_id}/signals")
async def get_territory_signals(
    territory_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return active signals for properties in this territory."""
    result = await db.execute(
        select(Territory).where(
            Territory.id == territory_id, Territory.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Territory not found")

    # Get property IDs in territory
    prop_ids_result = await db.execute(
        select(TerritoryProperty.property_id).where(
            TerritoryProperty.territory_id == territory_id
        )
    )
    prop_ids = [r[0] for r in prop_ids_result.fetchall()]

    if not prop_ids:
        return {"signals": [], "count": 0}

    signals_result = await db.execute(
        select(Signal)
        .where(
            Signal.user_id == user.id,
            Signal.entity_type == "property",
            Signal.entity_id.in_(prop_ids),
            Signal.is_active == True,
        )
        .order_by(Signal.confidence.desc())
    )
    signals = signals_result.scalars().all()
    return {
        "signals": [SignalResponse.model_validate(s) for s in signals],
        "count": len(signals),
    }
