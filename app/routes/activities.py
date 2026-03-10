"""Activity / Interaction Logging routes with CRUD and quick-log."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, Property, Activity, InteractionType
from app.schemas.activity import (
    ActivityCreate,
    ActivityQuickLog,
    ActivityUpdate,
    ActivityResponse,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/activities", tags=["Activities"])


async def _validate_person(db: AsyncSession, person_id: int, user_id: int) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


async def _validate_property(db: AsyncSession, property_id: int, user_id: int) -> Property:
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return prop


@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    payload: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new activity/interaction record."""
    await _validate_person(db, payload.person_id, current_user.id)
    if payload.property_id:
        await _validate_property(db, payload.property_id, current_user.id)

    activity = Activity(
        user_id=current_user.id,
        person_id=payload.person_id,
        property_id=payload.property_id,
        interaction_type=payload.interaction_type,
        date=payload.date or datetime.now(timezone.utc),
        notes=payload.notes,
        is_meaningful=payload.is_meaningful,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)
    return activity


@router.post("/quick-log", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def quick_log_activity(
    payload: ActivityQuickLog,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quick-log an interaction — optimised for speed (< 10 seconds on mobile)."""
    await _validate_person(db, payload.person_id, current_user.id)

    activity = Activity(
        user_id=current_user.id,
        person_id=payload.person_id,
        interaction_type=payload.interaction_type,
        date=datetime.now(timezone.utc),
        notes=payload.notes,
        is_meaningful=payload.is_meaningful,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)
    return activity


@router.get("/", response_model=list[ActivityResponse])
async def list_activities(
    person_id: Optional[int] = Query(None),
    property_id: Optional[int] = Query(None),
    interaction_type: Optional[InteractionType] = Query(None),
    is_meaningful: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List activities with optional filtering and pagination."""
    query = select(Activity).where(Activity.user_id == current_user.id)

    if person_id is not None:
        query = query.where(Activity.person_id == person_id)
    if property_id is not None:
        query = query.where(Activity.property_id == property_id)
    if interaction_type is not None:
        query = query.where(Activity.interaction_type == interaction_type)
    if is_meaningful is not None:
        query = query.where(Activity.is_meaningful == is_meaningful)

    query = query.order_by(Activity.date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single activity by ID."""
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


@router.put("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an activity record."""
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "person_id" in update_data:
        await _validate_person(db, update_data["person_id"], current_user.id)
    if "property_id" in update_data and update_data["property_id"] is not None:
        await _validate_property(db, update_data["property_id"], current_user.id)

    for key, value in update_data.items():
        setattr(activity, key, value)

    await db.flush()
    await db.refresh(activity)
    return activity


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an activity record."""
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    await db.delete(activity)
    await db.flush()
