"""Background relationship summary generation from rapport anchors and recent activities.

Called asynchronously when:
- A rapport anchor is accepted (PATCH status -> accepted)
- A voice_note activity is saved for a contact

Uses OpenAI to generate a short 2-5 line plain text summary.
Multi-person: queries activities via both Activity.person_id and activity_people join table.
"""

import json
import logging
import os
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import or_, select, desc

from app.database import async_session_factory
from app.models.models import (
    Person,
    Activity,
    ActivityPerson,
    InteractionType,
    RapportAnchor,
    AnchorStatus,
    RelationshipSummary,
    SummaryStatus,
)

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = """\
You are a real-estate CRM assistant. Generate a short relationship summary (2-5 lines, plain text) \
for a real estate agent's contact based on the information below.

The summary should:
- Be written in third person (e.g. "Sarah and her husband Craig...")
- Capture the key relationship context: who they are, family situation, property interests, timing
- Be useful for the agent to quickly recall the relationship before a call or meeting
- Be factual — only include information provided below
- Be concise — no more than 5 short lines

Contact name: {contact_name}

Accepted rapport anchors:
{anchors}

Recent voice note transcriptions:
{voice_notes}

Recent interaction notes:
{interactions}

Generate the summary now. Return ONLY the summary text, nothing else.
"""

# Module-level lazy client
_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        _client = AsyncOpenAI(api_key=api_key)
    return _client


def _person_activity_filter(person_id: int):
    """Return a filter clause that matches activities linked to person_id
    via either the legacy Activity.person_id column or the activity_people join table."""
    subq = select(ActivityPerson.activity_id).where(ActivityPerson.person_id == person_id)
    return or_(
        Activity.person_id == person_id,
        Activity.id.in_(subq),
    )


async def generate_summary_background(
    person_id: int,
    user_id: int,
) -> None:
    """Run summary generation in the background. Errors are logged, never raised."""
    try:
        await _generate_and_store(person_id, user_id)
    except Exception:
        logger.exception("Background summary generation failed for person %s", person_id)


async def _generate_and_store(
    person_id: int,
    user_id: int,
) -> None:
    client = _get_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set — skipping summary generation")
        return

    async with async_session_factory() as db:
        try:
            # 1. Get person name
            result = await db.execute(
                select(Person).where(Person.id == person_id)
            )
            person = result.scalar_one_or_none()
            if not person:
                logger.warning("Person %s not found — skipping summary generation", person_id)
                return

            contact_name = f"{person.first_name} {person.last_name or ''}".strip()

            # 2. Get accepted rapport anchors
            result = await db.execute(
                select(RapportAnchor)
                .where(
                    RapportAnchor.person_id == person_id,
                    RapportAnchor.user_id == user_id,
                    RapportAnchor.status == AnchorStatus.accepted,
                )
                .order_by(RapportAnchor.created_at.desc())
                .limit(20)
            )
            anchors = result.scalars().all()
            anchors_text = "\n".join(
                f"- [{a.anchor_type}] {a.anchor_text}" for a in anchors
            ) if anchors else "(none)"

            # 3. Get last 5 voice_note activities (via legacy + join table)
            result = await db.execute(
                select(Activity)
                .where(
                    _person_activity_filter(person_id),
                    Activity.user_id == user_id,
                    Activity.interaction_type == InteractionType.voice_note,
                    Activity.notes.isnot(None),
                )
                .order_by(Activity.date.desc())
                .limit(5)
            )
            voice_notes = result.scalars().unique().all()
            voice_notes_text = "\n---\n".join(
                a.notes for a in voice_notes if a.notes
            ) if voice_notes else "(none)"

            # 4. Get last 5 other interaction notes (via legacy + join table)
            result = await db.execute(
                select(Activity)
                .where(
                    _person_activity_filter(person_id),
                    Activity.user_id == user_id,
                    Activity.interaction_type != InteractionType.voice_note,
                    Activity.interaction_type != InteractionType.system_event,
                    Activity.notes.isnot(None),
                )
                .order_by(Activity.date.desc())
                .limit(5)
            )
            interactions = result.scalars().unique().all()
            interactions_text = "\n---\n".join(
                f"[{a.interaction_type.value}] {a.notes}" for a in interactions if a.notes
            ) if interactions else "(none)"

            # 5. Check if there's enough material to generate a summary
            if anchors_text == "(none)" and voice_notes_text == "(none)" and interactions_text == "(none)":
                logger.info("No material for summary generation for person %s", person_id)
                return

            # 6. Call OpenAI
            prompt = _SUMMARY_PROMPT.format(
                contact_name=contact_name,
                anchors=anchors_text,
                voice_notes=voice_notes_text,
                interactions=interactions_text,
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=512,
                temperature=0.4,
                messages=[
                    {"role": "system", "content": "You generate concise relationship summaries for a real estate agent's CRM. Return only the summary text."},
                    {"role": "user", "content": prompt},
                ],
            )

            summary_text = (response.choices[0].message.content or "").strip()
            if not summary_text:
                logger.warning("Empty summary generated for person %s", person_id)
                return

            # 7. Check if an accepted summary already exists
            result = await db.execute(
                select(RelationshipSummary)
                .where(
                    RelationshipSummary.person_id == person_id,
                    RelationshipSummary.user_id == user_id,
                    RelationshipSummary.status == SummaryStatus.accepted,
                )
                .limit(1)
            )
            existing_accepted = result.scalar_one_or_none()

            # 8. Store the new summary
            is_update = existing_accepted is not None
            new_summary = RelationshipSummary(
                person_id=person_id,
                user_id=user_id,
                summary_text=summary_text,
                status=SummaryStatus.suggested,
                is_update=is_update,
            )
            db.add(new_summary)
            await db.commit()

            logger.info(
                "Generated %s summary for person %s (is_update=%s)",
                "suggested", person_id, is_update,
            )
        except Exception:
            await db.rollback()
            raise
