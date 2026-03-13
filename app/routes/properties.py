"""Property CRUD routes with filtering."""
import csv
import io
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Property
from app.schemas.property import PropertyCreate, PropertyUpdate, PropertyResponse
from app.services.auth import get_current_user
from app.services.agent_detection import detect_and_link_agent


# ── Bulk import schemas ───────────────────────────────────────────────────────

PROPERTY_CATEGORIES = {
    "current_listing",
    "previous_listing",
    "target_property",
    "historic_transaction",
    "appraisal_register",
}


class PropertyBulkItem(BaseModel):
    """A single property row in a bulk import request."""
    address: str = Field(..., min_length=1, max_length=500)
    suburb: Optional[str] = None
    property_type: Optional[str] = Field(None, max_length=100)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    land_size: Optional[str] = None
    cv_estimate: Optional[str] = None          # maps to Property.cv
    last_sold_amount: Optional[str] = None
    last_sold_date: Optional[date] = None
    current_listing_price: Optional[str] = None
    listing_agent: Optional[str] = None
    listing_agency: Optional[str] = None
    last_listed_date: Optional[date] = None
    last_listing_result: Optional[str] = None
    sellability: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None               # stored in appraisal_stage as fallback note
    tags: Optional[list[str]] = None          # informational only — not persisted
    category: Optional[str] = None            # informational only — not persisted

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PROPERTY_CATEGORIES:
            raise ValueError(
                f"category must be one of: {', '.join(sorted(PROPERTY_CATEGORIES))}"
            )
        return v

    @field_validator("last_listing_result")
    @classmethod
    def validate_listing_result(cls, v: Optional[str]) -> Optional[str]:
        valid = {"sold", "withdrawn", "expired", "private_sale", "unknown"}
        if v is not None and v not in valid:
            raise ValueError(f"last_listing_result must be one of: {', '.join(sorted(valid))}")
        return v


class PropertyBulkRequest(BaseModel):
    properties: list[PropertyBulkItem] = Field(..., min_length=1, max_length=500)


class PropertyBulkRowError(BaseModel):
    row: int
    address: Optional[str] = None
    errors: list[str]


class PropertyBulkResponse(BaseModel):
    created: list[PropertyResponse]
    failed: list[PropertyBulkRowError]
    total_submitted: int
    total_created: int
    total_failed: int


# ── CSV export columns ────────────────────────────────────────────────────────

_EXPORT_COLUMNS = [
    "id", "address", "suburb", "city", "property_type",
    "bedrooms", "bathrooms", "toilets", "ensuites", "living_rooms",
    "has_pool", "garaging", "section_size_sqm", "house_size_sqm",
    "land_size", "cv", "land_value", "perceived_value",
    "last_sold_amount", "last_sold_date",
    "current_listing_price", "listing_url", "listing_agent", "listing_agency",
    "last_listed_date", "last_listing_result",
    "sellability", "estimated_value",
    "appraisal_stage", "appraisal_status",
    "renovation_status", "years_owned", "council_valuation",
    "created_at", "updated_at",
]


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/properties", tags=["Properties"])


# ── Static routes MUST come before /{property_id} ────────────────────────────

@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    payload: PropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new property record."""
    prop = Property(user_id=current_user.id, **payload.model_dump())
    db.add(prop)
    await db.flush()
    await db.refresh(prop)

    # Auto-detect and link agent if listing_agent provided
    if payload.listing_agent:
        await detect_and_link_agent(
            db, prop.id, payload.listing_agent, agency=payload.listing_agency,
        )
        await db.refresh(prop)

    return prop


@router.get("/", response_model=list[PropertyResponse])
async def list_properties(
    suburb: Optional[str] = Query(None),
    bedrooms_min: Optional[int] = Query(None, ge=0),
    bedrooms_max: Optional[int] = Query(None, ge=0),
    has_pool: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search address or suburb"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List properties with optional filtering and pagination."""
    query = select(Property).where(Property.user_id == current_user.id)

    if suburb:
        query = query.where(Property.suburb.ilike(f"%{suburb}%"))
    if bedrooms_min is not None:
        query = query.where(Property.bedrooms >= bedrooms_min)
    if bedrooms_max is not None:
        query = query.where(Property.bedrooms <= bedrooms_max)
    if has_pool is not None:
        query = query.where(Property.has_pool == has_pool)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Property.address.ilike(pattern)) | (Property.suburb.ilike(pattern))
        )

    query = query.order_by(Property.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/appraisals", response_model=list[PropertyResponse])
async def list_appraisals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return properties with appraisal_status in ('booked', 'completed') for the current user.
    """
    result = await db.execute(
        select(Property)
        .where(
            Property.user_id == current_user.id,
            Property.appraisal_status.in_(["booked", "completed"]),
        )
        .order_by(Property.created_at.desc())
    )
    return result.scalars().all()


@router.get("/doorknock", response_model=list[PropertyResponse])
async def list_doorknock_properties(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all properties suitable for door-knocking (all properties for the user).
    This is an alias used by the frontend for the door-knock workflow.
    """
    result = await db.execute(
        select(Property)
        .where(Property.user_id == current_user.id)
        .order_by(Property.suburb, Property.address)
    )
    return result.scalars().all()


@router.post("/bulk", response_model=PropertyBulkResponse, status_code=status.HTTP_207_MULTI_STATUS)
async def bulk_import_properties(
    payload: PropertyBulkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk-import up to 500 properties in a single request.

    Each row is validated independently. Rows that fail validation are collected
    in `failed` with per-row error messages; valid rows are created and returned
    in `created`. The overall HTTP status is 207 Multi-Status so the caller can
    inspect both successes and failures in one response.

    Field mapping notes:
    - `cv_estimate` → stored as `Property.cv`
    - `notes` → stored as `Property.appraisal_stage` (free-text fallback)
    - `tags` and `category` are validated but not persisted (no DB column yet)
    """
    created_props: list[PropertyResponse] = []
    failed_rows: list[PropertyBulkRowError] = []

    for idx, item in enumerate(payload.properties, start=1):
        try:
            prop = Property(
                user_id=current_user.id,
                address=item.address,
                suburb=item.suburb,
                property_type=item.property_type,
                bedrooms=item.bedrooms,
                bathrooms=item.bathrooms,
                land_size=item.land_size,
                cv=item.cv_estimate,
                last_sold_amount=item.last_sold_amount,
                last_sold_date=item.last_sold_date,
                current_listing_price=item.current_listing_price,
                listing_agent=item.listing_agent,
                listing_agency=item.listing_agency,
                last_listed_date=item.last_listed_date,
                last_listing_result=item.last_listing_result,
                sellability=item.sellability,
                appraisal_stage=item.notes,  # best available free-text field
            )
            db.add(prop)
            await db.flush()
            await db.refresh(prop)

            # Auto-detect and link agent if listing_agent provided
            if item.listing_agent:
                await detect_and_link_agent(
                    db, prop.id, item.listing_agent, agency=item.listing_agency,
                )
                await db.refresh(prop)

            created_props.append(PropertyResponse.model_validate(prop))
        except Exception as exc:
            # Roll back only the failed row by expunging it if it was added
            db.expunge_all()  # safe: already-flushed rows are committed below
            failed_rows.append(
                PropertyBulkRowError(
                    row=idx,
                    address=item.address,
                    errors=[str(exc)],
                )
            )

    if created_props:
        await db.commit()

    return PropertyBulkResponse(
        created=created_props,
        failed=failed_rows,
        total_submitted=len(payload.properties),
        total_created=len(created_props),
        total_failed=len(failed_rows),
    )


@router.get("/export", response_class=StreamingResponse)
async def export_properties_csv(
    category: Optional[str] = Query(None, description="Filter by appraisal_status value"),
    appraisal_status: Optional[str] = Query(None, description="Filter by appraisal_status"),
    suburb: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all properties as a CSV file.

    Query params:
    - `category` / `appraisal_status` — filter by appraisal_status column value
    - `suburb` — case-insensitive partial match on suburb
    """
    query = select(Property).where(Property.user_id == current_user.id)

    # `category` is an alias for appraisal_status to match the bulk import naming
    status_filter = category or appraisal_status
    if status_filter:
        query = query.where(Property.appraisal_status == status_filter)
    if suburb:
        query = query.where(Property.suburb.ilike(f"%{suburb}%"))

    query = query.order_by(Property.created_at.desc())
    result = await db.execute(query)
    properties = result.scalars().all()

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for prop in properties:
        row = {col: getattr(prop, col, None) for col in _EXPORT_COLUMNS}
        # Normalise dates/datetimes to ISO strings for portability
        for key, val in row.items():
            if hasattr(val, "isoformat"):
                row[key] = val.isoformat()
            elif val is None:
                row[key] = ""
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=properties_export.csv"},
    )


# ── Parameterised routes — MUST come after all static routes ─────────────────

@router.patch("/{property_id}/appraisal-stage", response_model=PropertyResponse)
async def update_appraisal_stage(
    property_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update just the appraisal_stage field on a property."""
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    stage = payload.get("appraisal_stage")
    if stage is None:
        raise HTTPException(status_code=422, detail="appraisal_stage is required")
    prop.appraisal_stage = stage
    await db.flush()
    await db.refresh(prop)
    return prop


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single property by ID."""
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return prop


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: int,
    payload: PropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a property record."""
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prop, key, value)

    await db.flush()

    # Auto-detect and link agent if listing_agent was updated
    if "listing_agent" in update_data and update_data["listing_agent"]:
        await detect_and_link_agent(
            db, prop.id, update_data["listing_agent"],
            agency=update_data.get("listing_agency") or prop.listing_agency,
        )

    await db.refresh(prop)
    return prop


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a property record."""
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    await db.delete(prop)
    await db.flush()
