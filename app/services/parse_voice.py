"""Voice-to-contact field extraction using OpenAI gpt-4o-mini.

Called by POST /api/v1/people/parse-voice.
Returns a structured dict of contact fields extracted from a free-form
voice transcription captured by a real estate agent in the field.
"""

import json
import logging
import os
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a data extraction assistant for a New Zealand real estate agent's CRM.
Your job is to extract structured contact information from a spoken transcription.

Extract the following fields where present:
- first_name: given name
- last_name: family name
- phone: mobile or phone number (preserve the format as spoken, e.g. "021 555 1234")
- email: email address if mentioned
- suburb: NZ suburb or town they live in or are interested in
- tier: contact priority — "A" (hot/active), "B" (warm), "C" (cold/long-term), or null if not clear
- tags: array of relevant labels from this list only: ["buyer", "seller", "investor", "landlord", "tenant", "developer", "referral_source"]
- notes: a single string capturing anything useful that does not fit the above fields
  (e.g. motivations, referral source, timing, property preferences, family situation)

Rules:
- Return ONLY a valid JSON object with exactly these keys. No explanation, no markdown.
- If a field cannot be determined, use null (or [] for tags).
- For tier: infer from urgency cues — "looking now" / "ready to go" → A; "thinking about it" → B; "long term" / "one day" → C.
- For tags: "buyer" if looking to purchase, "seller" if selling, "investor" if investment focus, etc.
- notes should be a concise plain-text sentence or two — not a dump of everything.
- Do not invent information not present in the transcription.
"""

_USER_TEMPLATE = 'Transcription: "{transcription}"\n\nExtract the contact fields now.'

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def parse_voice_to_contact(transcription: str) -> dict:
    """Extract structured contact fields from a voice transcription.

    Returns a dict with keys:
        first_name, last_name, phone, email, suburb, tier, tags, notes
    All values may be None / [] if not found.
    Raises RuntimeError if the API key is missing or the model returns unparseable JSON.
    """
    client = _get_client()

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=400,
        temperature=0.1,          # low temp for deterministic extraction
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_TEMPLATE.format(transcription=transcription)},
        ],
    )

    raw = (response.choices[0].message.content or "").strip()
    logger.debug("parse_voice raw response: %s", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("parse_voice JSON decode error: %s | raw=%s", exc, raw)
        raise RuntimeError("Model returned invalid JSON") from exc

    # Normalise — ensure all expected keys are present with safe defaults
    return {
        "first_name": data.get("first_name") or None,
        "last_name":  data.get("last_name")  or None,
        "phone":      data.get("phone")       or None,
        "email":      data.get("email")       or None,
        "suburb":     data.get("suburb")      or None,
        "tier":       data.get("tier")        or None,
        "tags":       data.get("tags")        if isinstance(data.get("tags"), list) else [],
        "notes":      data.get("notes")       or None,
    }
