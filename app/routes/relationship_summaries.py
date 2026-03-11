"""Relationship Summary endpoints.

Endpoints:
- GET   /people/{person_id}/relationship-summary    — get accepted + latest suggested
- POST  /people/{person_id}/relationship-summary/generate — manually trigger generation
- PATCH /relationship-summaries/{summary_id}        — update status or text
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, RelationshipSummary, SummaryStatus
from app.schemas.relationship_summary import (
    RelationshipSummaryResponse,
    RelationshipSummaryUpdate,
    RelationshipSummaryForPerson,
    GenerationStartedResponse,
)
from app.services.auth import get_current_user

# ── Person-scoped router: /people/{person_id}/relationship-summary ──────────

person_router = APIRouter(
    prefix="/people/{person_id}/relationship-summary",
    tags=["Relationship Summaries"],
)


@person_router.get("/", response_model=RelationshipSummaryForPerson)
async def get_relationship_summary(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the accepted summary and latest suggested summary for a person."""
    await _get_person_or_404(db, person_id, current_user.id)

    # Get accepted summary (should be at most one)
    result = await db.execute(
        select(RelationshipSummary)
        .where(
            RelationshipSummary.person_id == person_id,
            RelationshipSummary.user_id == current_user.id,
            RelationshipSummary.status == SummaryStatus.accepted,
        )
        .order_by(RelationshipSummary.updated_at.desc())
        .limit(1)
    )
    accepted = result.scalar_one_or_none()

    # Get latest suggested summary
    result = await db.execute(
        select(RelationshipSummary)
        .where(
            RelationshipSummary.person_id == person_id,
            RelationshipSummary.user_id == current_user.id,
            RelationshipSummary.status == SummaryStatus.suggested,
        )
        .order_by(RelationshipSummary.created_at.desc())
        .limit(1)
    )
    suggested = result.scalar_one_or_none()

    return RelationshipSummaryForPerson(accepted=accepted, suggested=suggested)


@person_router.post("/generate", response_model=GenerationStartedResponse)
async def trigger_summary_generation(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a new summary generation for a contact."""
    await _get_person_or_404(db, person_id, current_user.id)

    from app.services.summary_generation import generate_summary_background
    asyncio.ensure_future(generate_summary_background(
        person_id=person_id,
        user_id=current_user.id,
    ))

    return GenerationStartedResponse(message="Generation started")


# ── Top-level router: /relationship-summaries/{summary_id} ──────────────────

top_router = APIRouter(
    prefix="/relationship-summaries",
    tags=["Relationship Summaries"],
)


@top_router.patch("/{summary_id}", response_model=RelationshipSummaryResponse)
async def update_relationship_summary(
    summary_id: int,
    payload: RelationshipSummaryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a summary's status (accept / dismiss) or edit its text.

    When accepting a suggested summary:
    - If another accepted summary exists for the same person, it is dismissed first.
    - This ensures only one accepted summary per person at a time.
    """
    result = await db.execute(
        select(RelationshipSummary)
        .where(
            RelationshipSummary.id == summary_id,
            RelationshipSummary.user_id == current_user.id,
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship summary not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # If accepting this summary, dismiss any existing accepted summary for the same person
    if update_data.get("status") == "accepted":
        existing_result = await db.execute(
            select(RelationshipSummary)
            .where(
                RelationshipSummary.person_id == summary.person_id,
                RelationshipSummary.user_id == current_user.id,
                RelationshipSummary.status == SummaryStatus.accepted,
                RelationshipSummary.id != summary_id,
            )
        )
        for old in existing_result.scalars().all():
            old.status = SummaryStatus.dismissed

    for key, value in update_data.items():
        setattr(summary, key, value)

    await db.flush()
    await db.refresh(summary)

    # Trigger outreach generation when a summary is accepted
    if summary.status == SummaryStatus.accepted and summary.person_id:
        from app.services.outreach_generation import generate_outreach_background
        asyncio.ensure_future(generate_outreach_background(
            person_id=summary.person_id,
            user_id=current_user.id,
        ))

    return summary


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_person_or_404(db: AsyncSession, person_id: int, user_id: int) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    return person
