"""Background suggested outreach message generation.

Triggered when:
- A relationship summary is accepted
- A rapport anchor is accepted

Uses accepted summary + accepted anchors + most recent interaction to generate
a channel-aware outreach message. Tone is adjusted based on the contact's
preferred_contact_channel field.
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
    PersonContextNode,
    ContextNode,
    CommunityEntity,
    CommunityEntityPerson,
)

logger = logging.getLogger(__name__)

# ── Channel-specific system + user prompts ────────────────────────────────────

_SYSTEM_BASE = (
    "You are a real-estate agent's assistant. "
    "Generate a suggested outreach message for the agent to send to a contact. "
    "Return ONLY the message text — no labels, no explanation, nothing else."
)

_CHANNEL_RULES = {
    "text": (
        "Channel: TEXT MESSAGE\n"
        "Rules:\n"
        "- 1 sentence max, extremely short\n"
        "- No greeting, no sign-off\n"
        "- Casual, mate-style NZ tone\n"
        "- Jump straight in\n"
        "- Reference something specific from the context\n"
        "Examples: 'Saw this and thought of you 👍' / "
        "'Quick one — how did the school thing land?' / "
        "'Mate, just checking in — any update on timing?'"
    ),
    "whatsapp": (
        "Channel: WHATSAPP\n"
        "Rules:\n"
        "- 1-2 sentences, relaxed and conversational\n"
        "- No formal greeting\n"
        "- Casual, friendly NZ tone\n"
        "- Can include one emoji if it feels natural\n"
        "- Reference something specific from the context"
    ),
    "messenger": (
        "Channel: FACEBOOK MESSENGER\n"
        "Rules:\n"
        "- 1-2 sentences, conversational\n"
        "- No formal greeting\n"
        "- Casual, friendly tone\n"
        "- Reference something specific from the context"
    ),
    "email": (
        "Channel: EMAIL\n"
        "Rules:\n"
        "- Include a warm greeting: 'Hi {contact_first_name},'\n"
        "- Short paragraph (2-3 sentences)\n"
        "- Warm but professional tone\n"
        "- End with a soft call to action or open question\n"
        "- Sign off with 'Cheers, [Agent]'\n"
        "- Reference something specific from the context"
    ),
    "call": (
        "Channel: PHONE CALL (talking point)\n"
        "Rules:\n"
        "- Generate a suggested talking point, NOT a message to send\n"
        "- 1 sentence, starting with an action verb\n"
        "- Should remind the agent what to bring up on the call\n"
        "Examples: 'Check in about the school zones they mentioned last time.' / "
        "'Ask how the lease situation is tracking — they were deciding in August.' / "
        "'Follow up on whether the husband has had a chance to look at the numbers.'"
    ),
}

_DEFAULT_RULES = (
    "Channel: TEXT / WHATSAPP (default)\n"
    "Rules:\n"
    "- 1-2 sentences max\n"
    "- Natural, casual, mate-style NZ tone\n"
    "- No formal opener — jump straight in\n"
    "- Reference something specific from the context\n"
    "Examples: 'Saw this and thought of you 👍' / "
    "'Quick one — this popped up and feels like your sort of thing.' / "
    "'Mate, thought this might be worth a look.'"
)

_USER_PROMPT = """\
{channel_rules}

Contact name: {contact_name}

Relationship summary:
{summary}

Key rapport anchors:
{anchors}

Context nodes (communities, schools, sports, etc.):
{context_nodes}

Community entities (organisations, clubs, businesses):
{community_entities}

Most recent interaction:
{last_interaction}

Generate the outreach message (or talking point) now.
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
            # 1. Get person name + preferred channel
            result = await db.execute(
                select(Person).where(Person.id == person_id)
            )
            person = result.scalar_one_or_none()
            if not person:
                logger.warning("Person %s not found — skipping outreach generation", person_id)
                return

            contact_name = f"{person.first_name} {person.last_name or ''}".strip()
            contact_first_name = person.first_name
            preferred_channel = (
                getattr(person, "preferred_contact_channel", None) or ""
            ).strip().lower() or None

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

            # 4. Get context nodes for this person (up to 2)
            result = await db.execute(
                select(PersonContextNode)
                .where(PersonContextNode.person_id == person_id)
                .limit(2)
            )
            pcn_links = result.scalars().all()
            context_nodes_text = "(none)"
            if pcn_links:
                node_ids = [link.context_node_id for link in pcn_links]
                result = await db.execute(
                    select(ContextNode).where(ContextNode.id.in_(node_ids))
                )
                nodes = result.scalars().all()
                if nodes:
                    context_nodes_text = ", ".join(
                        f"{n.name} ({n.type.value})" for n in nodes
                    )

            # 4b. Get community entities for this person (up to 2)
            ce_result = await db.execute(
                select(CommunityEntity)
                .join(CommunityEntityPerson, CommunityEntityPerson.community_entity_id == CommunityEntity.id)
                .where(
                    CommunityEntityPerson.person_id == person_id,
                    CommunityEntity.user_id == user_id,
                )
                .limit(2)
            )
            community_entities_list = ce_result.scalars().all()
            community_entities_text = "(none)"
            if community_entities_list:
                community_entities_text = ", ".join(
                    f"{ce.name} ({ce.type.value})" for ce in community_entities_list
                )

            # Fallback: if no summary and no anchors and no context nodes, skip
            if summary_text == "(none)" and anchors_text == "(none)" and context_nodes_text == "(none)" and community_entities_text == "(none)":
                logger.info("No material for outreach generation for person %s", person_id)
                return

            # 5. Get most recent interaction note
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

            # 6. Select channel-specific rules
            channel_rules = _CHANNEL_RULES.get(preferred_channel, _DEFAULT_RULES)
            # Inject first name into email template if needed
            channel_rules = channel_rules.replace("{contact_first_name}", contact_first_name)

            # 7. Call OpenAI
            prompt = _USER_PROMPT.format(
                channel_rules=channel_rules,
                contact_name=contact_name,
                summary=summary_text,
                anchors=anchors_text,
                context_nodes=context_nodes_text,
                community_entities=community_entities_text,
                last_interaction=last_interaction,
            )

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=200,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": _SYSTEM_BASE},
                    {"role": "user", "content": prompt},
                ],
            )

            message_text = (response.choices[0].message.content or "").strip()
            if not message_text:
                logger.warning("Empty outreach message generated for person %s", person_id)
                return

            # 8. Mark any existing current outreach as not current
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

            # 9. Store new outreach
            outreach = SuggestedOutreach(
                person_id=person_id,
                user_id=user_id,
                message_text=message_text,
                is_current=True,
            )
            db.add(outreach)
            await db.commit()

            logger.info(
                "Generated outreach message for person %s (channel=%s)",
                person_id,
                preferred_channel or "default",
            )
        except Exception:
            await db.rollback()
            raise
