"""Background rapport anchor extraction from voice note transcriptions.

Called asynchronously after a voice_note activity is saved.  Uses OpenAI to
extract simple rapport anchors and stores them as 'suggested' RapportAnchor rows.
"""

import asyncio
import json
import logging
import os
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import select

from app.database import async_session_factory
from app.models.models import Person, RapportAnchor, AnchorStatus

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
You are a real-estate CRM assistant. Given a voice note transcription from a real estate agent, \
extract simple rapport anchors — short factual nuggets about the person or household that the \
agent can use to build rapport in future conversations.

Categories to look for:
- kids / children (e.g. "two kids", "daughter starting school")
- pets (e.g. "golden retriever", "cat lover")
- suburb / location preferences (e.g. "wants to stay in Remuera")
- school zones (e.g. "zoned for Epsom Girls")
- buyer intent (e.g. "looking to upsize", "first home buyer")
- seller intent (e.g. "thinking of selling in spring", "wants to downsize")
- timing signals (e.g. "lease ends in March", "baby due in June")
- lifestyle motivations (e.g. "wants a pool", "needs home office")
- decision-maker clues (e.g. "wife makes the final call", "parents helping with deposit")
- hobbies / interests (e.g. "keen golfer", "loves gardening")

Rules:
- Return ONLY a JSON array of objects, nothing else.
- Each object: {"anchor_text": "<short phrase>", "anchor_type": "individual" or "household"}
- Keep each anchor_text under 60 characters — short and factual, not a sentence.
- If anchor applies to the household/couple, use "household". Otherwise "individual".
- If nothing useful can be extracted, return an empty array: []
- Do NOT invent information not present in the transcription.
- Do NOT include property addresses or agent-specific details.

Transcription:
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


async def extract_anchors_background(
    activity_id: int,
    user_id: int,
    person_id: Optional[int],
    transcription: str,
) -> None:
    """Run anchor extraction in the background.  Errors are logged, never raised."""
    try:
        await _extract_and_store(activity_id, user_id, person_id, transcription)
    except Exception:
        logger.exception("Background anchor extraction failed for activity %s", activity_id)


async def _extract_and_store(
    activity_id: int,
    user_id: int,
    person_id: Optional[int],
    transcription: str,
) -> None:
    client = _get_client()
    if client is None:
        logger.warning("OPENAI_API_KEY not set — skipping anchor extraction")
        return

    if not transcription or len(transcription.strip()) < 20:
        logger.info("Transcription too short for anchor extraction (activity %s)", activity_id)
        return

    # Call OpenAI
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=512,
        temperature=0.3,
        messages=[
            {"role": "system", "content": "You extract rapport anchors from voice note transcriptions. Return only valid JSON."},
            {"role": "user", "content": _EXTRACTION_PROMPT + transcription},
        ],
    )

    raw = (response.choices[0].message.content or "").strip()

    # Parse JSON — handle markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        anchors = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse anchor extraction JSON for activity %s: %s", activity_id, raw[:200])
        return

    if not isinstance(anchors, list) or len(anchors) == 0:
        logger.info("No anchors extracted for activity %s", activity_id)
        return

    # Look up person's relationship_group_id if person_id is set
    relationship_group_id = None
    async with async_session_factory() as db:
        try:
            if person_id:
                result = await db.execute(
                    select(Person.relationship_group_id).where(Person.id == person_id)
                )
                row = result.scalar_one_or_none()
                if row:
                    relationship_group_id = row

            # Store each anchor
            for item in anchors:
                if not isinstance(item, dict):
                    continue
                anchor_text = (item.get("anchor_text") or "").strip()
                anchor_type = (item.get("anchor_type") or "individual").strip().lower()
                if not anchor_text:
                    continue
                if anchor_type not in ("individual", "household"):
                    anchor_type = "individual"

                # For household anchors, use relationship_group_id if available
                rel_group = relationship_group_id if anchor_type == "household" else None

                anchor = RapportAnchor(
                    person_id=person_id,
                    relationship_group_id=rel_group,
                    activity_id=activity_id,
                    user_id=user_id,
                    anchor_text=anchor_text[:500],
                    anchor_type=anchor_type,
                    status=AnchorStatus.suggested,
                )
                db.add(anchor)

            await db.commit()
            logger.info("Stored %d rapport anchors for activity %s", len(anchors), activity_id)
        except Exception:
            await db.rollback()
            raise
