"""Person Important Dates (v2) CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, PersonImportantDate
from app.schemas.important_date import ImportantDateCreate, ImportantDateUpdate, ImportantDateResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/people", tags=["Important Dates"])


def _enrich(d: PersonImportantDate, person: Person | None) -> dict:
    return {
        "id": d.id,
        "owner_id": d.owner_id,
        "person_id": d.person_id,
        "label": d.label,
        "date": d.date,
        "is_recurring": d.is_recurring,
        "notes": d.notes,
        "person_name": f"{person.first_name} {person.last_name or ''}".strip() if person else None,
    }


@router.get("/{person_id}/important-dates", response_model=list[ImportantDateResponse])
async def list_important_dates(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all important dates for a person."""
    person_res = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = person_res.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    result = await db.execute(
        select(PersonImportantDate).where(
            PersonImportantDate.person_id == person_id,
            PersonImportantDate.owner_id == current_user.id,
        ).order_by(PersonImportantDate.date)
    )
    dates = result.scalars().all()
    return [_enrich(d, person) for d in dates]


@router.post("/{person_id}/important-dates", response_model=ImportantDateResponse, status_code=201)
async def create_important_date(
    person_id: int,
    payload: ImportantDateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an important date for a person."""
    person_res = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = person_res.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    d = PersonImportantDate(
        owner_id=current_user.id,
        person_id=person_id,
        label=payload.label,
        date=payload.date,
        is_recurring=payload.is_recurring,
        notes=payload.notes,
    )
    db.add(d)
    await db.flush()
    await db.refresh(d)
    return _enrich(d, person)


@router.put("/{person_id}/important-dates/{date_id}", response_model=ImportantDateResponse)
async def update_important_date(
    person_id: int,
    date_id: int,
    payload: ImportantDateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an important date."""
    result = await db.execute(
        select(PersonImportantDate).where(
            PersonImportantDate.id == date_id,
            PersonImportantDate.person_id == person_id,
            PersonImportantDate.owner_id == current_user.id,
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Date not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(d, key, value)

    await db.flush()
    await db.refresh(d)

    person_res = await db.execute(select(Person).where(Person.id == person_id))
    return _enrich(d, person_res.scalar_one_or_none())


@router.delete("/{person_id}/important-dates/{date_id}", status_code=204)
async def delete_important_date(
    person_id: int,
    date_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an important date."""
    result = await db.execute(
        select(PersonImportantDate).where(
            PersonImportantDate.id == date_id,
            PersonImportantDate.person_id == person_id,
            PersonImportantDate.owner_id == current_user.id,
        )
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Date not found")
    await db.delete(d)
    await db.flush()
