"""Voice-to-property field extraction using OpenAI gpt-4o-mini.

Called by POST /api/v1/properties/parse-voice.
Returns a structured dict of property fields extracted from a free-form
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
Your job is to extract structured property information from a spoken transcription.

Extract the following fields where present:
- cv: council valuation / capital value (e.g. "1.12M", "850K", "$1,200,000")
- last_sold_amount: last sale price (e.g. "980K", "$1,050,000")
- last_sold_date: date of last sale (ISO format YYYY-MM-DD if possible, otherwise best guess)
- bedrooms: number of bedrooms (integer)
- bathrooms: number of bathrooms (integer)
- land_size: section / land size (e.g. "612 sqm", "1/4 acre")
- last_listed_date: when it was last listed (ISO format YYYY-MM-DD if possible)
- last_listing_result: outcome of last listing — one of: sold, withdrawn, expired, private_sale, unknown
- listing_agent: name of the listing agent
- listing_agency: name of the agency
- current_listing_price: current asking price if on market

Rules:
- Return ONLY a valid JSON object with exactly these keys. No explanation, no markdown.
- If a field cannot be determined, use null.
- Preserve monetary amounts in the format spoken (e.g. "1.2M", "850K").
- For dates, use ISO format YYYY-MM-DD where possible. If only a year or month is given, use the first of the month/year.
- Do not invent information not present in the transcription.
- NZ context: CV = council valuation, RV = rateable value (treat as CV).
"""

_USER_TEMPLATE = 'Transcription: "{transcription}"\n\nExtract the property fields now.'

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def parse_property_voice(transcription: str) -> dict:
    """Extract structured property fields from a voice transcription."""
    client = _get_client()

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=400,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_TEMPLATE.format(transcription=transcription)},
        ],
    )

    raw = (response.choices[0].message.content or "").strip()
    logger.debug("parse_property_voice raw response: %s", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("parse_property_voice JSON decode error: %s | raw=%s", exc, raw)
        raise RuntimeError("Model returned invalid JSON") from exc

    return {
        "cv": data.get("cv") or None,
        "last_sold_amount": data.get("last_sold_amount") or None,
        "last_sold_date": data.get("last_sold_date") or None,
        "bedrooms": data.get("bedrooms") if isinstance(data.get("bedrooms"), int) else None,
        "bathrooms": data.get("bathrooms") if isinstance(data.get("bathrooms"), int) else None,
        "land_size": data.get("land_size") or None,
        "last_listed_date": data.get("last_listed_date") or None,
        "last_listing_result": data.get("last_listing_result") or None,
        "listing_agent": data.get("listing_agent") or None,
        "listing_agency": data.get("listing_agency") or None,
        "current_listing_price": data.get("current_listing_price") or None,
    }
