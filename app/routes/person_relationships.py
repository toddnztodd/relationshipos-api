"""Person Relationships CRUD routes — nested under /people and top-level /relationships."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, PersonRelationship
from app.schemas.person_relationship import PersonRelationshipCreate, PersonRelationshipResponse
from app.services.auth import get_current_user

# Nested router: /api/v1/people/{person_id}/relationships
person_router = APIRouter(prefix="/people", tags=["Person Relationships"])

# Top-level router: /api/v1/relationships
top_router = APIRouter(prefix="/relationships", tags=["Person Relationships"])


def _enrich(rel: PersonRelationship, person_a: Person, person_b: Person) -> dict:
    """Build response dict with enriched person names."""
    return {
        "id": rel.id,
        "owner_id": rel.owner_id,
        "person_a_id": rel.person_a_id,
        "person_b_id": rel.person_b_id,
        "relationship_type": rel.relationship_type,
        "custom_label": rel.custom_label,
        "notes": rel.notes,
        "created_at": rel.created_at,
        "person_a_name": f"{person_a.first_name} {person_a.last_name or ''}".strip() if person_a else None,
        "person_b_name": f"{person_b.first_name} {person_b.last_name or ''}".strip() if person_b else None,
    }


async def _enrich_list(rels, db):
    enriched = []
    for rel in rels:
        pa = (await db.execute(select(Person).where(Person.id == rel.person_a_id))).scalar_one_or_none()
        pb = (await db.execute(select(Person).where(Person.id == rel.person_b_id))).scalar_one_or_none()
        enriched.append(_enrich(rel, pa, pb))
    return enriched


# ── Nested endpoints ──────────────────────────────────────────────────────────


@person_router.get("/{person_id}/relationships", response_model=list[PersonRelationshipResponse])
async def list_person_relationships(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all relationships for a person (where they are person_a or person_b)."""
    person = (await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )).scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    result = await db.execute(
        select(PersonRelationship).where(
            PersonRelationship.owner_id == current_user.id,
            or_(
                PersonRelationship.person_a_id == person_id,
                PersonRelationship.person_b_id == person_id,
            ),
        )
    )
    return await _enrich_list(result.scalars().all(), db)


@person_router.post("/{person_id}/relationships", response_model=PersonRelationshipResponse, status_code=201)
async def create_person_relationship(
    person_id: int,
    payload: PersonRelationshipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a relationship between person_id (A) and person_b_id (B)."""
    for pid in [person_id, payload.person_b_id]:
        res = (await db.execute(
            select(Person).where(Person.id == pid, Person.user_id == current_user.id)
        )).scalar_one_or_none()
        if not res:
            raise HTTPException(status_code=404, detail=f"Person {pid} not found")

    rel = PersonRelationship(
        owner_id=current_user.id,
        person_a_id=person_id,
        person_b_id=payload.person_b_id,
        relationship_type=payload.relationship_type,
        custom_label=payload.custom_label,
        notes=payload.notes,
    )
    db.add(rel)
    await db.flush()
    await db.refresh(rel)

    pa = (await db.execute(select(Person).where(Person.id == rel.person_a_id))).scalar_one_or_none()
    pb = (await db.execute(select(Person).where(Person.id == rel.person_b_id))).scalar_one_or_none()
    return _enrich(rel, pa, pb)


@person_router.delete("/{person_id}/relationships/{relationship_id}", status_code=204)
async def delete_person_relationship(
    person_id: int,
    relationship_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a relationship."""
    result = await db.execute(
        select(PersonRelationship).where(
            PersonRelationship.id == relationship_id,
            PersonRelationship.owner_id == current_user.id,
            or_(
                PersonRelationship.person_a_id == person_id,
                PersonRelationship.person_b_id == person_id,
            ),
        )
    )
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    await db.delete(rel)
    await db.flush()


# ── Top-level endpoints ──────────────────────────────────────────────────────


@top_router.get("/", response_model=list[PersonRelationshipResponse])
async def list_all_relationships(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all relationships for the current user."""
    result = await db.execute(
        select(PersonRelationship).where(PersonRelationship.owner_id == current_user.id)
        .order_by(PersonRelationship.created_at.desc())
    )
    return await _enrich_list(result.scalars().all(), db)


@top_router.post("/", response_model=PersonRelationshipResponse, status_code=201)
async def create_relationship_toplevel(
    payload: PersonRelationshipCreate,
    person_a_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a relationship (top-level). Requires person_a_id as query param."""
    for pid in [person_a_id, payload.person_b_id]:
        res = (await db.execute(
            select(Person).where(Person.id == pid, Person.user_id == current_user.id)
        )).scalar_one_or_none()
        if not res:
            raise HTTPException(status_code=404, detail=f"Person {pid} not found")

    rel = PersonRelationship(
        owner_id=current_user.id,
        person_a_id=person_a_id,
        person_b_id=payload.person_b_id,
        relationship_type=payload.relationship_type,
        custom_label=payload.custom_label,
        notes=payload.notes,
    )
    db.add(rel)
    await db.flush()
    await db.refresh(rel)

    pa = (await db.execute(select(Person).where(Person.id == rel.person_a_id))).scalar_one_or_none()
    pb = (await db.execute(select(Person).where(Person.id == rel.person_b_id))).scalar_one_or_none()
    return _enrich(rel, pa, pb)


@top_router.delete("/{relationship_id}", status_code=204)
async def delete_relationship_toplevel(
    relationship_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a relationship by ID."""
    result = await db.execute(
        select(PersonRelationship).where(
            PersonRelationship.id == relationship_id,
            PersonRelationship.owner_id == current_user.id,
        )
    )
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    await db.delete(rel)
    await db.flush()
