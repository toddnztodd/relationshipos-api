"""CRUD routes for person_properties — properties linked to a person."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, PersonProperty
from app.schemas.person_property import (
    PersonPropertyCreate,
    PersonPropertyUpdate,
    PersonPropertyResponse,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/people/{person_id}/properties", tags=["Person Properties"])


async def _get_person_or_404(
    person_id: int, user: User, db: AsyncSession
) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


@router.get("/", response_model=list[PersonPropertyResponse])
async def list_person_properties(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all properties linked to a person."""
    await _get_person_or_404(person_id, current_user, db)
    result = await db.execute(
        select(PersonProperty)
        .where(
            PersonProperty.person_id == person_id,
            PersonProperty.user_id == current_user.id,
        )
        .order_by(PersonProperty.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=PersonPropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_person_property(
    person_id: int,
    payload: PersonPropertyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a property link to a person."""
    await _get_person_or_404(person_id, current_user, db)
    pp = PersonProperty(
        person_id=person_id,
        user_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(pp)
    await db.flush()
    await db.refresh(pp)
    return pp


@router.put("/{property_id}", response_model=PersonPropertyResponse)
async def update_person_property(
    person_id: int,
    property_id: int,
    payload: PersonPropertyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a property link for a person."""
    await _get_person_or_404(person_id, current_user, db)
    result = await db.execute(
        select(PersonProperty).where(
            PersonProperty.id == property_id,
            PersonProperty.person_id == person_id,
            PersonProperty.user_id == current_user.id,
        )
    )
    pp = result.scalar_one_or_none()
    if not pp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person property not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pp, key, value)

    await db.flush()
    await db.refresh(pp)
    return pp


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person_property(
    person_id: int,
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a property link from a person."""
    await _get_person_or_404(person_id, current_user, db)
    result = await db.execute(
        select(PersonProperty).where(
            PersonProperty.id == property_id,
            PersonProperty.person_id == person_id,
            PersonProperty.user_id == current_user.id,
        )
    )
    pp = result.scalar_one_or_none()
    if not pp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person property not found")

    await db.delete(pp)
    await db.flush()
