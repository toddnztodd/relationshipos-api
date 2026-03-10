"""People (Person) CRUD routes with search and filtering."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, Activity, TierEnum
from app.schemas.person import (
    PersonCreate,
    PersonUpdate,
    PersonResponse,
    PersonWithCadence,
    PersonSearchByPhone,
)
from app.services.auth import get_current_user
from app.services.cadence import compute_cadence_status, get_cadence_window
from app.services import dashboard_cache

router = APIRouter(prefix="/people", tags=["People"])


@router.post("/", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person(
    payload: PersonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new person record."""
    existing = await db.execute(
        select(Person).where(Person.user_id == current_user.id, Person.phone == payload.phone)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Person with phone '{payload.phone}' already exists",
        )

    person = Person(user_id=current_user.id, **payload.model_dump())
    db.add(person)
    await db.flush()
    await db.refresh(person)
    dashboard_cache.invalidate(current_user.id)
    return person


@router.get("/", response_model=list[PersonWithCadence])
async def list_people(
    tier: Optional[TierEnum] = Query(None),
    relationship_type: Optional[str] = Query(None),
    suburb: Optional[str] = Query(None),
    is_relationship_asset: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search first_name, last_name, or phone"),
    sort_by: str = Query("created_at", regex="^(created_at|first_name|last_name|tier|influence_score|updated_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List people with optional filtering, sorting, and pagination.

    Uses a single batch query to fetch last-activity dates for all people
    at once — avoids N+1 queries that caused timeouts with large contact lists.
    """
    query = select(Person).where(Person.user_id == current_user.id)

    if tier:
        query = query.where(Person.tier == tier)
    if relationship_type:
        query = query.where(Person.relationship_type == relationship_type)
    if suburb:
        query = query.where(Person.suburb.ilike(f"%{suburb}%"))
    if is_relationship_asset is not None:
        query = query.where(Person.is_relationship_asset == is_relationship_asset)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Person.first_name.ilike(pattern))
            | (Person.last_name.ilike(pattern))
            | (Person.phone.ilike(pattern))
        )

    sort_col = getattr(Person, sort_by, Person.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    people = result.scalars().all()

    if not people:
        return []

    # ── Batch fetch last meaningful activity for ALL people in ONE query ──────
    person_ids = [p.id for p in people]
    act_result = await db.execute(
        select(Activity.person_id, func.max(Activity.date).label("last_date"))
        .where(
            Activity.person_id.in_(person_ids),
            Activity.is_meaningful == True,
        )
        .group_by(Activity.person_id)
    )
    last_activity_map: dict = {row.person_id: row.last_date for row in act_result}

    # ── Enrich each person with cadence status ────────────────────────────────
    enriched = []
    for p in people:
        last_meaningful = last_activity_map.get(p.id)
        cadence_status, days_since = compute_cadence_status(p.tier, last_meaningful)
        window = get_cadence_window(p.tier)
        person_data = PersonWithCadence.model_validate(p)
        person_data.cadence_status = cadence_status.value
        person_data.days_since_last_meaningful = days_since
        person_data.cadence_window_days = window
        enriched.append(person_data)

    return enriched


@router.get("/search", response_model=PersonResponse | None)
async def search_by_phone(
    phone: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search for a person by phone number."""
    result = await db.execute(
        select(Person).where(Person.user_id == current_user.id, Person.phone == phone)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


@router.get("/{person_id}", response_model=PersonWithCadence)
async def get_person(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single person by ID with cadence status."""
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    act_result = await db.execute(
        select(func.max(Activity.date))
        .where(Activity.person_id == person.id, Activity.is_meaningful == True)
    )
    last_meaningful = act_result.scalar_one_or_none()
    cadence_status, days_since = compute_cadence_status(person.tier, last_meaningful)
    window = get_cadence_window(person.tier)

    person_data = PersonWithCadence.model_validate(person)
    person_data.cadence_status = cadence_status.value
    person_data.days_since_last_meaningful = days_since
    person_data.cadence_window_days = window
    return person_data


@router.put("/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: int,
    payload: PersonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a person record."""
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "phone" in update_data and update_data["phone"] != person.phone:
        existing = await db.execute(
            select(Person).where(
                Person.user_id == current_user.id,
                Person.phone == update_data["phone"],
                Person.id != person_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone '{update_data['phone']}' already in use",
            )

    for key, value in update_data.items():
        setattr(person, key, value)

    await db.flush()
    await db.refresh(person)
    dashboard_cache.invalidate(current_user.id)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a person record."""
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    await db.delete(person)
    await db.flush()
    dashboard_cache.invalidate(current_user.id)
