"""Background suggested outreach message generation.

Triggered when:
- A relationship summary is accepted
- A rapport anchor is accepted

Uses accepted summary + accepted anchors + most recent interaction to generate
a short, casual outreach message suitable for text/WhatsApp.
"""

import logging
import os
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import select

from app.database import async_session_factory
from app.models.models import (
    Person,
    Activity,
    InteractionType,
    RapportAnchor,
    AnchorStatus,
    RelationshipSummary,
    SummaryStatus,
    SuggestedOutreach,
)

logger = logging.getLogger(__name__)

_OUTREACH_PROMPT = """\
You are a real-estate agent's assistant. Generate a short suggested outreach message \
for the agent to send to a contact via text or WhatsApp.

Rules:
- 1-2 sentences max
- Natural, casual, mate-style tone (New Zealand / Australian style)
- No formal "Hi [Name]" opener — jump straight in
- Suitable for text/WhatsApp
- Reference something specific from the relationship context below
- Do NOT mention property prices or make promises
- Do NOT use emojis excessively (one max, if natural)

Examples of good messages:
- "Saw this and thought of you 👍"
- "Quick one — this popped up and feels like your sort of thing."
- "Mate, thought this might be worth a look."
- "Hey, how did the kids settle into the new school?"
- "Just checking in — any updates on the lease situation?"

Contact name: {contact_name}

Relationship summary:
{summary}

Key rapport anchors:
{anchors}

Most recent interaction:
{last_interaction}

Generate the outreach message now. Return ONLY the message text, nothing else.
"""

_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def generate_outreach_background(
    person_id: int,
    user_id: int,
) -> None:
    """Run outreach generation in the background. Errors are logged, never raised."""
    try:
        await _generate_and_store(person_id, user_id)
    except Exception:
        logger.exception("Background outreach generation failed for person %s", person_id)


async def _generate_and_store(
    person_id: int,
    user_id: int,
) -> None:
    client = _get_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set — skipping outreach generation")
        return

    async with async_session_factory() as db:
        try:
            # 1. Get person name
            result = await db.execute(
                select(Person).where(Person.id == person_id)
            )
            person = result.scalar_one_or_none()
            if not person:
                logger.warning("Person %s not found — skipping outreach generation", person_id)
                return

            contact_name = f"{person.first_name} {person.last_name or ''}".strip()

            # 2. Get accepted relationship summary
            result = await db.execute(
                select(RelationshipSummary)
                .where(
                    RelationshipSummary.person_id == person_id,
                    RelationshipSummary.user_id == user_id,
                    RelationshipSummary.status == SummaryStatus.accepted,
                )
                .limit(1)
            )
            summary_row = result.scalar_one_or_none()
            summary_text = summary_row.summary_text if summary_row else "(none)"

            # 3. Get accepted rapport anchors (up to 5)
            result = await db.execute(
                select(RapportAnchor)
                .where(
                    RapportAnchor.person_id == person_id,
                    RapportAnchor.user_id == user_id,
                    RapportAnchor.status == AnchorStatus.accepted,
                )
                .order_by(RapportAnchor.created_at.desc())
                .limit(5)
            )
            anchors = result.scalars().all()
            anchors_text = "\n".join(
                f"- {a.anchor_text}" for a in anchors
            ) if anchors else "(none)"

            # Fallback: if no summary and no anchors, skip
            if summary_text == "(none)" and anchors_text == "(none)":
                logger.info("No material for outreach generation for person %s", person_id)
                return

            # 4. Get most recent interaction note
            result = await db.execute(
                select(Activity)
                .where(
                    Activity.person_id == person_id,
                    Activity.user_id == user_id,
                    Activity.interaction_type != InteractionType.system_event,
                    Activity.notes.isnot(None),
                )
                .order_by(Activity.date.desc())
                .limit(1)
            )
            last_activity = result.scalar_one_or_none()
            last_interaction = (
                f"[{last_activity.interaction_type.value}] {last_activity.notes}"
                if last_activity and last_activity.notes
                else "(none)"
            )

            # 5. Call OpenAI
            prompt = _OUTREACH_PROMPT.format(
                contact_name=contact_name,
                summary=summary_text,
                anchors=anchors_text,
                last_interaction=last_interaction,
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=150,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": "You generate short, casual outreach messages for a real estate agent. Return only the message text."},
                    {"role": "user", "content": prompt},
                ],
            )

            message_text = (response.choices[0].message.content or "").strip()
            if not message_text:
                logger.warning("Empty outreach message generated for person %s", person_id)
                return

            # 6. Mark any existing current outreach as not current
            result = await db.execute(
                select(SuggestedOutreach)
                .where(
                    SuggestedOutreach.person_id == person_id,
                    SuggestedOutreach.user_id == user_id,
                    SuggestedOutreach.is_current == True,
                )
            )
            for old in result.scalars().all():
                old.is_current = False

            # 7. Store new outreach
            outreach = SuggestedOutreach(
                person_id=person_id,
                user_id=user_id,
                message_text=message_text,
                is_current=True,
            )
            db.add(outreach)
            await db.commit()

            logger.info("Generated outreach message for person %s", person_id)
        except Exception:
            await db.rollback()
            raise
