"""Property-Person link CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, Property, PropertyPerson
from app.schemas.property_person import PropertyPersonCreate, PropertyPersonResponse
from app.services.auth import get_current_user

router = APIRouter(tags=["Property-Person Links"])


def _enrich(link: PropertyPerson, person: Person | None, prop: Property | None) -> dict:
    return {
        "id": link.id,
        "owner_id": link.owner_id,
        "property_id": link.property_id,
        "person_id": link.person_id,
        "role": link.role,
        "notes": link.notes,
        "created_at": link.created_at,
        "person_name": f"{person.first_name} {person.last_name or ''}".strip() if person else None,
        "property_address": prop.address if prop else None,
    }


@router.get("/properties/{property_id}/people", response_model=list[PropertyPersonResponse])
async def list_property_people(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all people linked to a property."""
    prop = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    if not prop.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Property not found")

    result = await db.execute(
        select(PropertyPerson).where(
            PropertyPerson.property_id == property_id,
            PropertyPerson.owner_id == current_user.id,
        )
    )
    links = result.scalars().all()

    enriched = []
    for link in links:
        p = await db.execute(select(Person).where(Person.id == link.person_id))
        pr = await db.execute(select(Property).where(Property.id == link.property_id))
        enriched.append(_enrich(link, p.scalar_one_or_none(), pr.scalar_one_or_none()))
    return enriched


@router.post("/properties/{property_id}/people", response_model=PropertyPersonResponse, status_code=201)
async def link_person_to_property(
    property_id: int,
    payload: PropertyPersonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link a person to a property with a role."""
    # Verify property
    prop_res = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = prop_res.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Verify person
    person_res = await db.execute(
        select(Person).where(Person.id == payload.person_id, Person.user_id == current_user.id)
    )
    person = person_res.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    link = PropertyPerson(
        owner_id=current_user.id,
        property_id=property_id,
        person_id=payload.person_id,
        role=payload.role,
        notes=payload.notes,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return _enrich(link, person, prop)


@router.delete("/properties/{property_id}/people/{link_id}", status_code=204)
async def unlink_person_from_property(
    property_id: int,
    link_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a person-property link."""
    result = await db.execute(
        select(PropertyPerson).where(
            PropertyPerson.id == link_id,
            PropertyPerson.property_id == property_id,
            PropertyPerson.owner_id == current_user.id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)
    await db.flush()


@router.get("/people/{person_id}/properties", response_model=list[PropertyPersonResponse])
async def list_person_properties(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all properties linked to a person."""
    person = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    if not person.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Person not found")

    result = await db.execute(
        select(PropertyPerson).where(
            PropertyPerson.person_id == person_id,
            PropertyPerson.owner_id == current_user.id,
        )
    )
    links = result.scalars().all()

    enriched = []
    for link in links:
        p = await db.execute(select(Person).where(Person.id == link.person_id))
        pr = await db.execute(select(Property).where(Property.id == link.property_id))
        enriched.append(_enrich(link, p.scalar_one_or_none(), pr.scalar_one_or_none()))
    return enriched
