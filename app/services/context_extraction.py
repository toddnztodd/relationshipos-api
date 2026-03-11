"""Background service for extracting context node suggestions from voice notes and conversation updates."""

import json
import logging
import os

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.models import ContextNodeSuggestion, ContextNodeType

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """You are a real-estate CRM assistant. Analyse the following transcription or conversation note and extract any **context signals** — specific communities, schools, sports clubs, locations, interests, networks, or other shared-context items that could help an agent build rapport.

Return a JSON array of objects. Each object must have:
- "name": the specific name (e.g. "Papamoa Primary School", "Mount Maunganui Surf Club", "Ponsonby")
- "type": one of "community", "school", "sport", "location", "interest", "network", "other"

Rules:
- Only extract specific, named entities — not generic concepts like "education" or "fitness"
- Include schools, sports clubs, community groups, suburbs, churches, hobby groups, professional networks
- Do NOT include people's names, phone numbers, or personal details
- If nothing specific is found, return an empty array: []
- Return ONLY valid JSON, nothing else

Transcription:
{transcription}
"""


async def extract_context_nodes_background(
    activity_id: int,
    user_id: int,
    person_id: int | None,
    transcription: str,
) -> None:
    """Extract context node suggestions from a transcription in the background."""
    if not transcription or not transcription.strip():
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — skipping context extraction")
        return

    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=512,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": _EXTRACTION_PROMPT.format(transcription=transcription[:3000]),
                }
            ],
        )

        raw = (response.choices[0].message.content or "").strip()

        # Parse JSON — handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        suggestions = json.loads(raw)

        if not isinstance(suggestions, list) or not suggestions:
            logger.info(f"No context nodes extracted for activity {activity_id}")
            return

        # Valid types
        valid_types = {t.value for t in ContextNodeType}

        async with async_session_factory() as session:
            for item in suggestions[:10]:  # cap at 10 per extraction
                name = (item.get("name") or "").strip()
                node_type = (item.get("type") or "other").strip().lower()
                if not name:
                    continue
                if node_type not in valid_types:
                    node_type = "other"

                suggestion = ContextNodeSuggestion(
                    person_id=person_id,
                    activity_id=activity_id,
                    user_id=user_id,
                    suggested_name=name,
                    suggested_type=ContextNodeType(node_type),
                )
                session.add(suggestion)

            await session.commit()
            logger.info(f"Stored context node suggestions for activity {activity_id}")

    except json.JSONDecodeError as e:
        logger.error(f"Context extraction JSON parse error for activity {activity_id}: {e}")
    except Exception as e:
        logger.error(f"Context extraction failed for activity {activity_id}: {e}")
