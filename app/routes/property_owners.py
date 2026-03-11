"""Property Owners — CRUD endpoints for linking owners to properties."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Person, Property, PropertyOwner
from app.schemas.property import (
    PropertyOwnerCreate,
    PropertyOwnerPersonSummary,
    PropertyOwnerResponse,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/properties", tags=["Property Owners"])


def _build_response(po: PropertyOwner) -> PropertyOwnerResponse:
    person_summary = None
    if po.person:
        person_summary = PropertyOwnerPersonSummary(
            id=po.person.id,
            first_name=po.person.first_name,
            last_name=po.person.last_name or "",
        )
    return PropertyOwnerResponse(
        id=po.id,
        property_id=po.property_id,
        person_id=po.person_id,
        person=person_summary,
        created_at=po.created_at,
    )


@router.get("/{property_id}/owners", response_model=List[PropertyOwnerResponse])
async def list_property_owners(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all owners of a property."""
    prop_result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    if not prop_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Property not found")

    result = await db.execute(
        select(PropertyOwner)
        .where(PropertyOwner.property_id == property_id, PropertyOwner.user_id == current_user.id)
        .order_by(PropertyOwner.created_at.desc())
    )
    return [_build_response(po) for po in result.scalars().all()]


@router.post(
    "/{property_id}/owners",
    response_model=PropertyOwnerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_property_owner(
    property_id: int,
    payload: PropertyOwnerCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Link a person as an owner of a property."""
    # Verify property
    prop_result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    if not prop_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Property not found")

    # Verify person
    person_result = await db.execute(
        select(Person).where(Person.id == payload.person_id, Person.user_id == current_user.id)
    )
    if not person_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Person not found")

    # Check for duplicate
    existing = await db.execute(
        select(PropertyOwner).where(
            PropertyOwner.property_id == property_id,
            PropertyOwner.person_id == payload.person_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Person is already an owner of this property")

    po = PropertyOwner(
        user_id=current_user.id,
        property_id=property_id,
        person_id=payload.person_id,
    )
    db.add(po)
    await db.flush()
    await db.refresh(po)
    return _build_response(po)


@router.delete("/{property_id}/owners/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_property_owner(
    property_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove a person as an owner of a property."""
    result = await db.execute(
        select(PropertyOwner).where(
            PropertyOwner.property_id == property_id,
            PropertyOwner.person_id == person_id,
            PropertyOwner.user_id == current_user.id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Owner link not found")
    await db.delete(po)
