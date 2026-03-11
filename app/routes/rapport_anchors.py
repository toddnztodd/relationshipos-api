"""Rapport Anchor CRUD routes.

Endpoints:
- GET  /people/{person_id}/rapport-anchors   — list accepted + suggested anchors
- POST /people/{person_id}/rapport-anchors   — manually add an anchor
- PATCH  /rapport-anchors/{anchor_id}        — update status or text
- DELETE /rapport-anchors/{anchor_id}        — delete an anchor
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, RapportAnchor, AnchorStatus
from app.schemas.rapport_anchor import (
    RapportAnchorCreate,
    RapportAnchorUpdate,
    RapportAnchorResponse,
    RapportAnchorsForPerson,
)
from app.services.auth import get_current_user

# ── Person-scoped router: /people/{person_id}/rapport-anchors ─────────────────

person_router = APIRouter(prefix="/people/{person_id}/rapport-anchors", tags=["Rapport Anchors"])


@person_router.get("/", response_model=RapportAnchorsForPerson)
async def list_rapport_anchors(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return accepted and suggested rapport anchors for a person.

    Dismissed anchors are excluded.  If the person belongs to a relationship
    group, household-level anchors for that group are also included.
    """
    # Verify person belongs to user
    person = await _get_person_or_404(db, person_id, current_user.id)

    # Build query: person's own anchors + household anchors via relationship_group_id
    query = (
        select(RapportAnchor)
        .where(
            RapportAnchor.user_id == current_user.id,
            RapportAnchor.status != AnchorStatus.dismissed,
        )
    )

    if person.relationship_group_id:
        # Include anchors linked to this person OR to the same household group
        query = query.where(
            (RapportAnchor.person_id == person_id)
            | (RapportAnchor.relationship_group_id == person.relationship_group_id)
        )
    else:
        query = query.where(RapportAnchor.person_id == person_id)

    query = query.order_by(RapportAnchor.created_at.desc())
    result = await db.execute(query)
    anchors = result.scalars().all()

    accepted = [a for a in anchors if a.status == AnchorStatus.accepted]
    suggested = [a for a in anchors if a.status == AnchorStatus.suggested]

    return RapportAnchorsForPerson(accepted=accepted, suggested=suggested)


@person_router.post("/", response_model=RapportAnchorResponse, status_code=status.HTTP_201_CREATED)
async def create_rapport_anchor(
    person_id: int,
    payload: RapportAnchorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually add a rapport anchor to a person's profile.

    Manually-created anchors are immediately set to status = 'accepted'.
    """
    person = await _get_person_or_404(db, person_id, current_user.id)

    # For household anchors, use the person's relationship_group_id if available
    rel_group_id = person.relationship_group_id if payload.anchor_type == "household" else None

    anchor = RapportAnchor(
        person_id=person_id,
        relationship_group_id=rel_group_id,
        activity_id=0,  # placeholder — no source activity for manual anchors
        user_id=current_user.id,
        anchor_text=payload.anchor_text,
        anchor_type=payload.anchor_type,
        status=AnchorStatus.accepted,  # manual = auto-accepted
    )

    # We need a real activity_id since it's NOT NULL — create a system_event activity
    from app.models.models import Activity, InteractionType
    from datetime import datetime, timezone

    system_activity = Activity(
        user_id=current_user.id,
        person_id=person_id,
        interaction_type=InteractionType.system_event,
        date=datetime.now(timezone.utc),
        notes=f"Manual rapport anchor added: {payload.anchor_text}",
        is_meaningful=False,
        source="manual_anchor",
    )
    db.add(system_activity)
    await db.flush()
    await db.refresh(system_activity)

    anchor.activity_id = system_activity.id
    db.add(anchor)
    await db.flush()
    await db.refresh(anchor)

    return anchor


# ── Top-level router: /rapport-anchors/{anchor_id} ───────────────────────────

top_router = APIRouter(prefix="/rapport-anchors", tags=["Rapport Anchors"])


@top_router.patch("/{anchor_id}", response_model=RapportAnchorResponse)
async def update_rapport_anchor(
    anchor_id: int,
    payload: RapportAnchorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an anchor's status (accept / dismiss) or edit its text."""
    anchor = await _get_anchor_or_404(db, anchor_id, current_user.id)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(anchor, key, value)

    await db.flush()
    await db.refresh(anchor)

    # Trigger background summary generation when an anchor is accepted
    if anchor.status == AnchorStatus.accepted and anchor.person_id:
        from app.services.summary_generation import generate_summary_background
        asyncio.ensure_future(generate_summary_background(
            person_id=anchor.person_id,
            user_id=current_user.id,
        ))

    return anchor


@top_router.delete("/{anchor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rapport_anchor(
    anchor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete a rapport anchor."""
    anchor = await _get_anchor_or_404(db, anchor_id, current_user.id)
    await db.delete(anchor)
    await db.flush()


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_person_or_404(db: AsyncSession, person_id: int, user_id: int) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


async def _get_anchor_or_404(db: AsyncSession, anchor_id: int, user_id: int) -> RapportAnchor:
    result = await db.execute(
        select(RapportAnchor).where(RapportAnchor.id == anchor_id, RapportAnchor.user_id == user_id)
    )
    anchor = result.scalar_one_or_none()
    if not anchor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rapport anchor not found")
    return anchor
