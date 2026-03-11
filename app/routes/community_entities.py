"""Community Entities — CRUD and linking endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import (
    Activity,
    CommunityEntity,
    CommunityEntityActivity,
    CommunityEntityPerson,
    CommunityEntityProperty,
    Person,
    Property,
)
from app.schemas.community_entity import (
    CommunityEntityActivityLink,
    CommunityEntityCreate,
    CommunityEntityListItem,
    CommunityEntityPersonLink,
    CommunityEntityPropertyLink,
    CommunityEntityResponse,
    CommunityEntityUpdate,
    LinkActivityRequest,
    LinkPersonRequest,
    LinkPropertyRequest,
)
from app.services.auth import get_current_user

# ── Routers ───────────────────────────────────────────────────────────────────

# /community-entities/  and  /community-entities/{id}
router = APIRouter(prefix="/community-entities", tags=["Community Entities"])

# /people/{id}/community-entities
people_router = APIRouter(prefix="/people", tags=["Community Entities"])

# /properties/{id}/community-entities
properties_router = APIRouter(prefix="/properties", tags=["Community Entities"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_response(entity: CommunityEntity) -> CommunityEntityResponse:
    people = [
        CommunityEntityPersonLink(
            person_id=link.person.id,
            first_name=link.person.first_name,
            last_name=link.person.last_name or "",
            role=link.role,
        )
        for link in entity.people_links
        if link.person is not None
    ]
    properties = [
        CommunityEntityPropertyLink(
            property_id=link.property.id,
            address=link.property.address,
        )
        for link in entity.property_links
        if link.property is not None
    ]
    # Return up to 5 most recent activities
    act_links = sorted(
        [l for l in entity.activity_links if l.activity is not None],
        key=lambda l: l.activity.date or l.created_at,
        reverse=True,
    )[:5]
    activities = [
        CommunityEntityActivityLink(
            activity_id=l.activity.id,
            interaction_type=l.activity.interaction_type.value,
            notes=l.activity.notes,
            date=l.activity.date,
        )
        for l in act_links
    ]
    return CommunityEntityResponse(
        id=entity.id,
        name=entity.name,
        type=entity.type.value,
        location=entity.location,
        notes=entity.notes,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        people=people,
        properties=properties,
        recent_activities=activities,
    )


async def _get_entity_or_404(entity_id: int, user_id: int, db: AsyncSession) -> CommunityEntity:
    result = await db.execute(
        select(CommunityEntity)
        .where(CommunityEntity.id == entity_id, CommunityEntity.user_id == user_id)
        .options(
            selectinload(CommunityEntity.people_links).selectinload(CommunityEntityPerson.person),
            selectinload(CommunityEntity.property_links).selectinload(CommunityEntityProperty.property),
            selectinload(CommunityEntity.activity_links).selectinload(CommunityEntityActivity.activity),
        )
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Community entity not found")
    return entity


# ── CRUD endpoints ────────────────────────────────────────────────────────────

@router.get("/", response_model=List[CommunityEntityListItem])
async def list_community_entities(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all community entities for the current user."""
    result = await db.execute(
        select(CommunityEntity)
        .where(CommunityEntity.user_id == current_user.id)
        .options(
            selectinload(CommunityEntity.people_links),
            selectinload(CommunityEntity.property_links),
        )
        .order_by(CommunityEntity.name)
    )
    entities = result.scalars().all()
    return [
        CommunityEntityListItem(
            id=e.id,
            name=e.name,
            type=e.type.value,
            location=e.location,
            people_count=len(e.people_links),
            property_count=len(e.property_links),
            created_at=e.created_at,
        )
        for e in entities
    ]


@router.post("/", response_model=CommunityEntityResponse, status_code=status.HTTP_201_CREATED)
async def create_community_entity(
    payload: CommunityEntityCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new community entity."""
    from app.models.models import CommunityEntityType
    try:
        entity_type = CommunityEntityType(payload.type)
    except ValueError:
        entity_type = CommunityEntityType.other

    entity = CommunityEntity(
        user_id=current_user.id,
        name=payload.name,
        type=entity_type,
        location=payload.location,
        notes=payload.notes,
    )
    db.add(entity)
    await db.flush()
    await db.refresh(entity)
    return _build_response(entity)


@router.get("/{entity_id}", response_model=CommunityEntityResponse)
async def get_community_entity(
    entity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a community entity with all linked people, properties, and recent activities."""
    entity = await _get_entity_or_404(entity_id, current_user.id, db)
    return _build_response(entity)


@router.patch("/{entity_id}", response_model=CommunityEntityResponse)
async def update_community_entity(
    entity_id: int,
    payload: CommunityEntityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a community entity."""
    from app.models.models import CommunityEntityType
    entity = await _get_entity_or_404(entity_id, current_user.id, db)
    if payload.name is not None:
        entity.name = payload.name
    if payload.type is not None:
        try:
            entity.type = CommunityEntityType(payload.type)
        except ValueError:
            pass
    if payload.location is not None:
        entity.location = payload.location
    if payload.notes is not None:
        entity.notes = payload.notes
    await db.flush()
    entity = await _get_entity_or_404(entity_id, current_user.id, db)
    return _build_response(entity)


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_community_entity(
    entity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a community entity."""
    result = await db.execute(
        select(CommunityEntity).where(
            CommunityEntity.id == entity_id,
            CommunityEntity.user_id == current_user.id,
        )
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Community entity not found")
    await db.delete(entity)


# ── People linking ────────────────────────────────────────────────────────────

@router.post("/{entity_id}/people", response_model=CommunityEntityResponse, status_code=status.HTTP_201_CREATED)
async def link_person(
    entity_id: int,
    payload: LinkPersonRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Link a person to a community entity with an optional role."""
    entity = await _get_entity_or_404(entity_id, current_user.id, db)

    # Verify person belongs to this user
    p_result = await db.execute(
        select(Person).where(Person.id == payload.person_id, Person.user_id == current_user.id)
    )
    person = p_result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check for existing link
    existing = await db.execute(
        select(CommunityEntityPerson).where(
            CommunityEntityPerson.community_entity_id == entity_id,
            CommunityEntityPerson.person_id == payload.person_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Person already linked to this entity")

    link = CommunityEntityPerson(
        community_entity_id=entity_id,
        person_id=payload.person_id,
        role=payload.role,
    )
    db.add(link)
    await db.flush()
    entity = await _get_entity_or_404(entity_id, current_user.id, db)
    return _build_response(entity)


@router.delete("/{entity_id}/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_person(
    entity_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Unlink a person from a community entity."""
    # Verify entity belongs to user
    await _get_entity_or_404(entity_id, current_user.id, db)

    result = await db.execute(
        select(CommunityEntityPerson).where(
            CommunityEntityPerson.community_entity_id == entity_id,
            CommunityEntityPerson.person_id == person_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)


# ── Property linking ──────────────────────────────────────────────────────────

@router.post("/{entity_id}/properties", response_model=CommunityEntityResponse, status_code=status.HTTP_201_CREATED)
async def link_property(
    entity_id: int,
    payload: LinkPropertyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Link a property to a community entity."""
    entity = await _get_entity_or_404(entity_id, current_user.id, db)

    p_result = await db.execute(
        select(Property).where(Property.id == payload.property_id, Property.user_id == current_user.id)
    )
    prop = p_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    existing = await db.execute(
        select(CommunityEntityProperty).where(
            CommunityEntityProperty.community_entity_id == entity_id,
            CommunityEntityProperty.property_id == payload.property_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Property already linked to this entity")

    link = CommunityEntityProperty(
        community_entity_id=entity_id,
        property_id=payload.property_id,
    )
    db.add(link)
    await db.flush()
    entity = await _get_entity_or_404(entity_id, current_user.id, db)
    return _build_response(entity)


@router.delete("/{entity_id}/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_property(
    entity_id: int,
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Unlink a property from a community entity."""
    await _get_entity_or_404(entity_id, current_user.id, db)

    result = await db.execute(
        select(CommunityEntityProperty).where(
            CommunityEntityProperty.community_entity_id == entity_id,
            CommunityEntityProperty.property_id == property_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)


# ── Activity linking ──────────────────────────────────────────────────────────

@router.post("/{entity_id}/activities", response_model=CommunityEntityResponse, status_code=status.HTTP_201_CREATED)
async def link_activity(
    entity_id: int,
    payload: LinkActivityRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Link an activity to a community entity."""
    entity = await _get_entity_or_404(entity_id, current_user.id, db)

    a_result = await db.execute(
        select(Activity).where(Activity.id == payload.activity_id, Activity.user_id == current_user.id)
    )
    act = a_result.scalar_one_or_none()
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    existing = await db.execute(
        select(CommunityEntityActivity).where(
            CommunityEntityActivity.community_entity_id == entity_id,
            CommunityEntityActivity.activity_id == payload.activity_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Activity already linked to this entity")

    link = CommunityEntityActivity(
        community_entity_id=entity_id,
        activity_id=payload.activity_id,
    )
    db.add(link)
    await db.flush()
    entity = await _get_entity_or_404(entity_id, current_user.id, db)
    return _build_response(entity)


@router.delete("/{entity_id}/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_activity(
    entity_id: int,
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Unlink an activity from a community entity."""
    await _get_entity_or_404(entity_id, current_user.id, db)

    result = await db.execute(
        select(CommunityEntityActivity).where(
            CommunityEntityActivity.community_entity_id == entity_id,
            CommunityEntityActivity.activity_id == activity_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)


# ── Cross-entity lookups ──────────────────────────────────────────────────────

@people_router.get("/{person_id}/community-entities", response_model=List[CommunityEntityListItem])
async def get_person_community_entities(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all community entities linked to a person."""
    # Verify person belongs to user
    p_result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    if not p_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Person not found")

    result = await db.execute(
        select(CommunityEntity)
        .join(CommunityEntityPerson, CommunityEntityPerson.community_entity_id == CommunityEntity.id)
        .where(CommunityEntityPerson.person_id == person_id, CommunityEntity.user_id == current_user.id)
        .options(
            selectinload(CommunityEntity.people_links),
            selectinload(CommunityEntity.property_links),
        )
        .order_by(CommunityEntity.name)
    )
    entities = result.scalars().all()
    return [
        CommunityEntityListItem(
            id=e.id,
            name=e.name,
            type=e.type.value,
            location=e.location,
            people_count=len(e.people_links),
            property_count=len(e.property_links),
            created_at=e.created_at,
        )
        for e in entities
    ]


@properties_router.get("/{property_id}/community-entities", response_model=List[CommunityEntityListItem])
async def get_property_community_entities(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all community entities linked to a property."""
    p_result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    if not p_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Property not found")

    result = await db.execute(
        select(CommunityEntity)
        .join(CommunityEntityProperty, CommunityEntityProperty.community_entity_id == CommunityEntity.id)
        .where(CommunityEntityProperty.property_id == property_id, CommunityEntity.user_id == current_user.id)
        .options(
            selectinload(CommunityEntity.people_links),
            selectinload(CommunityEntity.property_links),
        )
        .order_by(CommunityEntity.name)
    )
    entities = result.scalars().all()
    return [
        CommunityEntityListItem(
            id=e.id,
            name=e.name,
            type=e.type.value,
            location=e.location,
            people_count=len(e.people_links),
            property_count=len(e.property_links),
            created_at=e.created_at,
        )
        for e in entities
    ]
