"""Property-Person link CRUD routes — nested and top-level."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, Property, PropertyPerson
from app.schemas.property_person import PropertyPersonCreate, PropertyPersonResponse
from app.services.auth import get_current_user

# Nested router (registered under /api/v1)
router = APIRouter(tags=["Property-Person Links"])

# Top-level router: /api/v1/property-people
top_router = APIRouter(prefix="/property-people", tags=["Property-Person Links"])


def _enrich(link: PropertyPerson, person: Person | None, prop: Property | None) -> dict:
    return {
        "id": link.id,
        "owner_id": link.owner_id,
        "property_id": link.property_id,
        "person_id": link.person_id,
        "role": link.role,
        "custom_label": link.custom_label,
        "notes": link.notes,
        "created_at": link.created_at,
        "person_name": f"{person.first_name} {person.last_name or ''}".strip() if person else None,
        "property_address": prop.address if prop else None,
    }


async def _enrich_list(links, db):
    enriched = []
    for link in links:
        p = (await db.execute(select(Person).where(Person.id == link.person_id))).scalar_one_or_none()
        pr = (await db.execute(select(Property).where(Property.id == link.property_id))).scalar_one_or_none()
        enriched.append(_enrich(link, p, pr))
    return enriched


# ── Nested endpoints ──────────────────────────────────────────────────────────


@router.get("/properties/{property_id}/people", response_model=list[PropertyPersonResponse])
async def list_property_people(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all people linked to a property."""
    prop = (await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )).scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    result = await db.execute(
        select(PropertyPerson).where(
            PropertyPerson.property_id == property_id,
            PropertyPerson.owner_id == current_user.id,
        )
    )
    return await _enrich_list(result.scalars().all(), db)


@router.post("/properties/{property_id}/people", response_model=PropertyPersonResponse, status_code=201)
async def link_person_to_property(
    property_id: int,
    payload: PropertyPersonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link a person to a property with a role."""
    prop_res = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == current_user.id)
    )
    prop = prop_res.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

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
        custom_label=payload.custom_label,
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
    person = (await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )).scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    result = await db.execute(
        select(PropertyPerson).where(
            PropertyPerson.person_id == person_id,
            PropertyPerson.owner_id == current_user.id,
        )
    )
    return await _enrich_list(result.scalars().all(), db)


# ── Top-level endpoints ──────────────────────────────────────────────────────


@top_router.delete("/{link_id}", status_code=204)
async def delete_property_person_link(
    link_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a property-person link by ID."""
    result = await db.execute(
        select(PropertyPerson).where(
            PropertyPerson.id == link_id,
            PropertyPerson.owner_id == current_user.id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await db.delete(link)
    await db.flush()
