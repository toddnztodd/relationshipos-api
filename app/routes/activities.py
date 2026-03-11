"""Activity / Interaction Logging routes with CRUD, quick-log, and screenshot analysis."""

import base64
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, Property, Activity, InteractionType
from app.schemas.activity import (
    ActivityCreate,
    ActivityQuickLog,
    ActivityUpdate,
    ActivityResponse,
    ScreenshotAnalysisResponse,
    TranscriptionResponse,
)
from app.services.auth import get_current_user
from app.services import dashboard_cache
from app.routes.people import _update_last_interaction

router = APIRouter(prefix="/activities", tags=["Activities"])

# Lazy-initialised OpenAI async client
_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI API key not configured on server.",
            )
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _validate_person(db: AsyncSession, person_id: int, user_id: int) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


async def _validate_property(db: AsyncSession, property_id: int, user_id: int) -> Property:
    result = await db.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user_id)
    )
    prop = result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    return prop


# ── Voice Transcription ────────────────────────────────────────────────────────


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    summary="Transcribe an audio recording with OpenAI Whisper",
    description=(
        "Upload an audio file (WebM, MP4, WAV, or M4A). "
        "The audio is sent to OpenAI Whisper for speech-to-text transcription "
        "and immediately discarded — it is never stored on disk or in the database. "
        "Returns the transcription text."
    ),
)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (WebM, MP4, WAV, or M4A)"),
    current_user: User = Depends(get_current_user),
):
    """Transcribe an audio recording and return the text."""
    # Validate content type
    allowed_types = {
        "audio/webm", "audio/mp4", "audio/wav", "audio/x-wav",
        "audio/mpeg", "audio/m4a", "audio/x-m4a", "audio/mp4a-latm",
        "video/webm", "video/mp4",  # browsers sometimes label audio-only WebM/MP4 as video/*
    }
    content_type = (audio.content_type or "").lower()
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported audio type '{content_type}'. Allowed: WebM, MP4, WAV, M4A.",
        )

    # Read audio bytes (max 25 MB — Whisper API limit)
    audio_bytes = await audio.read()
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file must be smaller than 25 MB.",
        )

    # Determine a safe filename extension for the Whisper API
    ext_map = {
        "audio/webm": "webm", "video/webm": "webm",
        "audio/mp4": "mp4", "video/mp4": "mp4",
        "audio/wav": "wav", "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/m4a": "m4a", "audio/x-m4a": "m4a", "audio/mp4a-latm": "m4a",
    }
    ext = ext_map.get(content_type, "webm")
    filename = f"voice_note.{ext}"

    # Call OpenAI Whisper API
    client = _get_openai_client()
    try:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, audio_bytes),
            response_format="text",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI Whisper API error: {exc}",
        )

    return TranscriptionResponse(transcription=transcript.strip() if isinstance(transcript, str) else str(transcript).strip())


# ── Screenshot Analysis ────────────────────────────────────────────────────────

_ANALYSIS_PROMPT = """You are a real-estate CRM assistant. Analyse the conversation screenshot and extract the following information in JSON format only (no markdown, no explanation):

{
  "summary": "<one or two sentence plain-English summary of what the conversation is about>",
  "participants": ["<name or phone number of each participant, as a list>"],
  "property": "<property address or description if mentioned, otherwise null>",
  "datetime": "<ISO-8601 datetime string if a date/time is visible in the conversation, otherwise null>"
}

Rules:
- Return ONLY valid JSON, nothing else.
- If a field cannot be determined, use null (for strings) or [] (for participants).
- Do not include any personally sensitive information beyond what is visible in the screenshot.
- Keep the summary concise and professional.
"""


@router.post(
    "/analyze-screenshot",
    response_model=ScreenshotAnalysisResponse,
    summary="Analyse a conversation screenshot with OpenAI Vision",
    description=(
        "Upload a screenshot of a conversation (WhatsApp, SMS, email, etc.). "
        "The image is sent to OpenAI Vision for analysis and immediately discarded — "
        "it is never stored on disk or in the database. "
        "Returns extracted summary, participants, property reference, and datetime."
    ),
)
async def analyze_screenshot(
    image: UploadFile = File(..., description="Screenshot image file (JPEG, PNG, WEBP, GIF)"),
    current_user: User = Depends(get_current_user),
):
    """Analyse a conversation screenshot and return structured data."""
    # Validate content type
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
    content_type = (image.content_type or "").lower()
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported image type '{content_type}'. Allowed: JPEG, PNG, WEBP, GIF.",
        )

    # Read image bytes (max 20 MB guard)
    image_bytes = await image.read()
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be smaller than 20 MB.",
        )

    # Encode to base64 data URL for OpenAI Vision
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{content_type};base64,{b64_image}"

    # Call OpenAI Vision API
    client = _get_openai_client()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _ANALYSIS_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
                    ],
                }
            ],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI Vision API error: {exc}",
        )

    # Parse the JSON response
    raw_text = (response.choices[0].message.content or "").strip()

    import json

    try:
        # Strip markdown code fences if model wraps the JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Return best-effort partial result
        return ScreenshotAnalysisResponse(
            summary=raw_text[:500] if raw_text else None,
            participants=[],
            property=None,
            datetime=None,
        )

    return ScreenshotAnalysisResponse(
        summary=parsed.get("summary"),
        participants=parsed.get("participants") or [],
        property=parsed.get("property"),
        datetime=parsed.get("datetime"),
    )


# ── Standard CRUD ──────────────────────────────────────────────────────────────


@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    payload: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new activity/interaction record."""
    if payload.person_id:
        await _validate_person(db, payload.person_id, current_user.id)
    if payload.property_id:
        await _validate_property(db, payload.property_id, current_user.id)

    activity_date = payload.date or datetime.now(timezone.utc)
    activity = Activity(
        user_id=current_user.id,
        person_id=payload.person_id,
        property_id=payload.property_id,
        interaction_type=payload.interaction_type,
        date=activity_date,
        notes=payload.notes,
        is_meaningful=payload.is_meaningful,
        source=payload.source,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)

    # Update last_interaction on the contact (only if a person is linked)
    if payload.person_id:
        await _update_last_interaction(
            db, payload.person_id,
            payload.interaction_type.value if hasattr(payload.interaction_type, "value") else payload.interaction_type,
            activity_date,
        )

    dashboard_cache.invalidate(current_user.id)
    return activity


@router.post("/quick-log", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def quick_log_activity(
    payload: ActivityQuickLog,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quick-log an interaction — optimised for speed (< 10 seconds on mobile)."""
    if payload.person_id:
        await _validate_person(db, payload.person_id, current_user.id)

    now = datetime.now(timezone.utc)
    activity = Activity(
        user_id=current_user.id,
        person_id=payload.person_id,
        interaction_type=payload.interaction_type,
        date=now,
        notes=payload.notes,
        is_meaningful=payload.is_meaningful,
        source=payload.source,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)

    # Update last_interaction on the contact (only if a person is linked)
    if payload.person_id:
        await _update_last_interaction(
            db, payload.person_id,
            payload.interaction_type.value if hasattr(payload.interaction_type, "value") else payload.interaction_type,
            now,
        )

    dashboard_cache.invalidate(current_user.id)
    return activity


@router.get("/", response_model=list[ActivityResponse])
async def list_activities(
    person_id: Optional[int] = Query(None),
    property_id: Optional[int] = Query(None),
    interaction_type: Optional[InteractionType] = Query(None),
    is_meaningful: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List activities with optional filtering and pagination."""
    query = select(Activity).where(Activity.user_id == current_user.id)

    if person_id is not None:
        query = query.where(Activity.person_id == person_id)
    if property_id is not None:
        query = query.where(Activity.property_id == property_id)
    if interaction_type is not None:
        query = query.where(Activity.interaction_type == interaction_type)
    if is_meaningful is not None:
        query = query.where(Activity.is_meaningful == is_meaningful)

    query = query.order_by(Activity.date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single activity by ID."""
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


@router.put("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an activity record."""
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "person_id" in update_data:
        await _validate_person(db, update_data["person_id"], current_user.id)
    if "property_id" in update_data and update_data["property_id"] is not None:
        await _validate_property(db, update_data["property_id"], current_user.id)

    for key, value in update_data.items():
        setattr(activity, key, value)

    await db.flush()
    await db.refresh(activity)
    dashboard_cache.invalidate(current_user.id)
    return activity


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an activity record."""
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    await db.delete(activity)
    await db.flush()
    dashboard_cache.invalidate(current_user.id)
