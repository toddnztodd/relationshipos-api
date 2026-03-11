"""Open Home endpoints.

- POST /open-homes/{open_home_id}/vendor-update — generate channel-specific vendor update messages
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    User,
    Person,
    Property,
    Activity,
    InteractionType,
    PropertyPerson,
)
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/open-homes", tags=["Open Homes"])

_client: Optional[AsyncOpenAI] = None


def _get_client() -> Optional[AsyncOpenAI]:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        _client = AsyncOpenAI(api_key=api_key)
    return _client


# ── Schemas ──────────────────────────────────────────────────────────────────


class VendorUpdateRequest(BaseModel):
    channel: Optional[str] = None  # text | whatsapp | messenger | email | null


class ChannelMessages(BaseModel):
    text: str
    whatsapp: str
    messenger: str
    email: str


class VendorUpdateResponse(BaseModel):
    vendor_name: str
    preferred_channel: Optional[str] = None
    messages: ChannelMessages


# ── Prompt ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a real-estate agent's assistant. Generate vendor update messages after an open home.
You must generate exactly 4 message variants — one for each channel.
Return ONLY valid JSON with this exact structure (no markdown, no code fences):
{"text": "...", "whatsapp": "...", "messenger": "...", "email": "..."}
"""

_USER_PROMPT = """\
Generate 4 channel-specific vendor update messages for the following open home:

Vendor name: {vendor_name}
Property address: {property_address}
Attendance count: {attendance_count}
Buyer interest notes: {buyer_notes}

Channel rules:
- text: short, natural, conversational, no formal opener, mate-style NZ tone, 1-2 sentences max
- whatsapp: slightly fuller, conversational, casual, 2-3 sentences
- messenger: similar to whatsapp, conversational, 2-3 sentences
- email: structured, warm but professional, include greeting ("Hi {vendor_first_name},") and sign-off ("Cheers, [Agent]"), 3-5 sentences

All messages should:
- Summarise how the open home went
- Mention attendance if available
- Note any buyer interest if available
- Sound natural and genuine, not robotic

Return ONLY the JSON object with keys: text, whatsapp, messenger, email
"""


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.post(
    "/{open_home_id}/vendor-update",
    response_model=VendorUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_vendor_update(
    open_home_id: int,
    payload: VendorUpdateRequest = VendorUpdateRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate channel-specific vendor update messages for an open home.

    `open_home_id` is the property_id for the open home.
    Reads vendor contact, attendance count, and buyer interest notes,
    then generates text/whatsapp/messenger/email message variants via OpenAI.
    """
    client = _get_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured",
        )

    uid = current_user.id

    # 1. Get the property
    prop_result = await db.execute(
        select(Property).where(Property.id == open_home_id, Property.user_id == uid)
    )
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found",
        )

    property_address = prop.address or "Unknown address"

    # 2. Find the vendor contact via property_people (role = Vendor)
    vendor_name = "the vendor"
    vendor_first_name = "there"
    preferred_channel = None

    vendor_link_result = await db.execute(
        select(PropertyPerson)
        .where(
            PropertyPerson.property_id == open_home_id,
            PropertyPerson.owner_id == uid,
        )
    )
    vendor_links = vendor_link_result.scalars().all()

    # Look for a vendor role (case-insensitive)
    vendor_person = None
    for link in vendor_links:
        if link.role and link.role.lower() in ("vendor", "owner", "seller"):
            person_result = await db.execute(
                select(Person).where(Person.id == link.person_id)
            )
            vendor_person = person_result.scalar_one_or_none()
            if vendor_person:
                break

    if vendor_person:
        vendor_name = f"{vendor_person.first_name} {vendor_person.last_name or ''}".strip()
        vendor_first_name = vendor_person.first_name
        preferred_channel = getattr(vendor_person, "preferred_contact_channel", None)

    # 3. Count attendance (open_home_attendance activities for this property)
    count_result = await db.execute(
        select(func.count(Activity.id))
        .where(
            Activity.property_id == open_home_id,
            Activity.user_id == uid,
            Activity.interaction_type == InteractionType.open_home_attendance,
        )
    )
    attendance_count = count_result.scalar() or 0
    attendance_text = f"{attendance_count} groups through" if attendance_count > 0 else "No attendance data available"

    # 4. Get buyer interest notes from recent activities on this property
    notes_result = await db.execute(
        select(Activity.notes, Activity.feedback)
        .where(
            Activity.property_id == open_home_id,
            Activity.user_id == uid,
            Activity.notes.isnot(None),
        )
        .order_by(Activity.date.desc())
        .limit(5)
    )
    buyer_notes_parts = []
    for row in notes_result.all():
        if row[0]:
            buyer_notes_parts.append(row[0])
        if row[1]:
            buyer_notes_parts.append(f"Feedback: {row[1]}")
    buyer_notes = "\n".join(buyer_notes_parts[:5]) if buyer_notes_parts else "No specific buyer interest notes available"

    # 5. Call OpenAI
    prompt = _USER_PROMPT.format(
        vendor_name=vendor_name,
        vendor_first_name=vendor_first_name,
        property_address=property_address,
        attendance_count=attendance_text,
        buyer_notes=buyer_notes,
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=800,
            temperature=0.7,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        raw = (response.choices[0].message.content or "").strip()

        # Parse JSON response — strip markdown code fences if present
        import json
        cleaned = raw
        if cleaned.startswith("```"):
            # Remove opening fence
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        messages_dict = json.loads(cleaned)

        return VendorUpdateResponse(
            vendor_name=vendor_name,
            preferred_channel=preferred_channel,
            messages=ChannelMessages(
                text=messages_dict.get("text", ""),
                whatsapp=messages_dict.get("whatsapp", ""),
                messenger=messages_dict.get("messenger", ""),
                email=messages_dict.get("email", ""),
            ),
        )

    except json.JSONDecodeError:
        logger.error("Failed to parse OpenAI response as JSON: %s", raw)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse generated messages. Please try again.",
        )
    except Exception as e:
        logger.exception("Vendor update generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Message generation failed: {str(e)}",
        )
