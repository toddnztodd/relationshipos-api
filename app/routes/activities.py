"""Activity / Interaction Logging routes with CRUD, quick-log, and screenshot analysis."""

import asyncio
import base64
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from openai import AsyncOpenAI
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import User, Person, Property, Activity, ActivityPerson, InteractionType
from app.schemas.activity import (
    ActivityCreate,
    ActivityQuickLog,
    ActivityUpdate,
    ActivityResponse,
    ParticipantInfo,
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


def _resolve_people_ids(person_id: Optional[int], people_ids: Optional[list[int]]) -> list[int]:
    """Merge person_id and people_ids into a deduplicated list."""
    ids: set[int] = set()
    if people_ids:
        ids.update(people_ids)
    if person_id:
        ids.add(person_id)
    return sorted(ids)


async def _create_activity_people(db: AsyncSession, activity_id: int, person_ids: list[int]) -> None:
    """Insert activity_people join records for each person."""
    for pid in person_ids:
        db.add(ActivityPerson(activity_id=activity_id, person_id=pid))
    await db.flush()


def _build_activity_dict(activity: Activity, participants: list) -> dict:
    """Build the response dict for an Activity with a given participants list."""
    return {
        "id": activity.id,
        "user_id": activity.user_id,
        "person_id": activity.person_id,
        "property_id": activity.property_id,
        "interaction_type": activity.interaction_type,
        "date": activity.date,
        "notes": activity.notes,
        "is_meaningful": activity.is_meaningful,
        "due_date": activity.due_date,
        "feedback": activity.feedback,
        "price_indication": activity.price_indication,
        "scheduled_date": activity.scheduled_date,
        "scheduled_time": activity.scheduled_time,
        "source": activity.source,
        "created_at": activity.created_at,
        "participants": participants,
    }


def _activity_to_response(activity: Activity) -> dict:
    """Convert an Activity ORM object to a dict with participants (from loaded relationships)."""
    participants = []
    if activity.activity_people:
        for ap in activity.activity_people:
            if ap.person:
                participants.append(ParticipantInfo(
                    id=ap.person.id,
                    first_name=ap.person.first_name,
                    last_name=ap.person.last_name,
                ))
    return _build_activity_dict(activity, participants)


def _activity_to_response_with_persons(activity: Activity, persons: dict[int, Person]) -> dict:
    """Build response using pre-validated Person objects — bypasses ORM relationship loading."""
    participants = [
        ParticipantInfo(id=p.id, first_name=p.first_name, last_name=p.last_name)
        for p in persons.values()
    ]
    return _build_activity_dict(activity, participants)


def _trigger_background_tasks(activity: Activity, all_person_ids: list[int], user_id: int):
    """Fire background extraction tasks for voice_note and conversation_update activities."""
    if not activity.notes:
        return

    is_voice_note = activity.interaction_type == InteractionType.voice_note
    is_conversation = activity.interaction_type == InteractionType.conversation_update

    if not (is_voice_note or is_conversation):
        return

    from app.services.anchor_extraction import extract_anchors_background
    from app.services.summary_generation import generate_summary_background
    from app.services.context_extraction import extract_context_nodes_background

    for pid in all_person_ids:
        # Anchor extraction and summary generation — voice notes only
        if is_voice_note:
            asyncio.ensure_future(extract_anchors_background(
                activity_id=activity.id,
                user_id=user_id,
                person_id=pid,
                transcription=activity.notes,
            ))
            asyncio.ensure_future(generate_summary_background(
                person_id=pid,
                user_id=user_id,
            ))

        # Context node extraction — both voice notes and conversation updates
        asyncio.ensure_future(extract_context_nodes_background(
            activity_id=activity.id,
            user_id=user_id,
            person_id=pid,
            transcription=activity.notes,
        ))

    # Also fire for person_id=None case (property-only)
    if not all_person_ids:
        if is_voice_note:
            asyncio.ensure_future(extract_anchors_background(
                activity_id=activity.id,
                user_id=user_id,
                person_id=None,
                transcription=activity.notes,
            ))
        asyncio.ensure_future(extract_context_nodes_background(
            activity_id=activity.id,
            user_id=user_id,
            person_id=None,
            transcription=activity.notes,
        ))


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
    allowed_types = {
        "audio/webm", "audio/mp4", "audio/wav", "audio/x-wav",
        "audio/mpeg", "audio/m4a", "audio/x-m4a", "audio/mp4a-latm",
        "video/webm", "video/mp4",
    }
    content_type = (audio.content_type or "").lower()
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported audio type '{content_type}'. Allowed: WebM, MP4, WAV, M4A.",
        )

    audio_bytes = await audio.read()
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file must be smaller than 25 MB.",
        )

    ext_map = {
        "audio/webm": "webm", "video/webm": "webm",
        "audio/mp4": "mp4", "video/mp4": "mp4",
        "audio/wav": "wav", "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/m4a": "m4a", "audio/x-m4a": "m4a", "audio/mp4a-latm": "m4a",
    }
    ext = ext_map.get(content_type, "webm")
    filename = f"voice_note.{ext}"

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
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
    content_type = (image.content_type or "").lower()
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported image type '{content_type}'. Allowed: JPEG, PNG, WEBP, GIF.",
        )

    image_bytes = await image.read()
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be smaller than 20 MB.",
        )

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{content_type};base64,{b64_image}"

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

    raw_text = (response.choices[0].message.content or "").strip()

    import json

    try:
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
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
    # Resolve all person IDs (merge person_id + people_ids)
    all_person_ids = _resolve_people_ids(payload.person_id, payload.people_ids)

    # Validate all people belong to user — collect Person objects for response
    validated_persons: dict[int, Person] = {}
    for pid in all_person_ids:
        validated_persons[pid] = await _validate_person(db, pid, current_user.id)
    if payload.property_id:
        await _validate_property(db, payload.property_id, current_user.id)

    # Set person_id for backward compatibility: first person or explicit person_id
    compat_person_id = payload.person_id
    if not compat_person_id and len(all_person_ids) == 1:
        compat_person_id = all_person_ids[0]

    activity_date = payload.date or datetime.now(timezone.utc)
    activity = Activity(
        user_id=current_user.id,
        person_id=compat_person_id,
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

    # Create activity_people join records
    if all_person_ids:
        await _create_activity_people(db, activity.id, all_person_ids)

    # Update last_interaction on all linked contacts
    for pid in all_person_ids:
        await _update_last_interaction(
            db, pid,
            payload.interaction_type.value if hasattr(payload.interaction_type, "value") else payload.interaction_type,
            activity_date,
        )

    dashboard_cache.invalidate(current_user.id)

    # Background tasks for all participants
    _trigger_background_tasks(activity, all_person_ids, current_user.id)

    # Build response directly from validated persons — avoids ORM identity-map cache issues
    return _activity_to_response_with_persons(activity, validated_persons)


@router.post("/quick-log", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def quick_log_activity(
    payload: ActivityQuickLog,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quick-log an interaction — optimised for speed (< 10 seconds on mobile)."""
    all_person_ids = _resolve_people_ids(payload.person_id, payload.people_ids)

    validated_persons: dict[int, Person] = {}
    for pid in all_person_ids:
        validated_persons[pid] = await _validate_person(db, pid, current_user.id)

    compat_person_id = payload.person_id
    if not compat_person_id and len(all_person_ids) == 1:
        compat_person_id = all_person_ids[0]

    now = datetime.now(timezone.utc)
    activity = Activity(
        user_id=current_user.id,
        person_id=compat_person_id,
        interaction_type=payload.interaction_type,
        date=now,
        notes=payload.notes,
        is_meaningful=payload.is_meaningful,
        source=payload.source,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)

    if all_person_ids:
        await _create_activity_people(db, activity.id, all_person_ids)

    for pid in all_person_ids:
        await _update_last_interaction(
            db, pid,
            payload.interaction_type.value if hasattr(payload.interaction_type, "value") else payload.interaction_type,
            now,
        )

    dashboard_cache.invalidate(current_user.id)

    _trigger_background_tasks(activity, all_person_ids, current_user.id)

    # Build response directly from validated persons — avoids ORM identity-map cache issues
    return _activity_to_response_with_persons(activity, validated_persons)


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
    """List activities with optional filtering and pagination.

    When filtering by person_id, returns activities linked via the
    activity_people join table OR via the legacy activities.person_id column.
    """
    query = (
        select(Activity)
        .options(selectinload(Activity.activity_people).selectinload(ActivityPerson.person))
        .where(Activity.user_id == current_user.id)
    )

    if person_id is not None:
        # Include activities linked via join table OR legacy person_id
        subq = select(ActivityPerson.activity_id).where(ActivityPerson.person_id == person_id)
        query = query.where(
            or_(
                Activity.person_id == person_id,
                Activity.id.in_(subq),
            )
        )
    if property_id is not None:
        query = query.where(Activity.property_id == property_id)
    if interaction_type is not None:
        query = query.where(Activity.interaction_type == interaction_type)
    if is_meaningful is not None:
        query = query.where(Activity.is_meaningful == is_meaningful)

    query = query.order_by(Activity.date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    activities = result.scalars().unique().all()
    return [_activity_to_response(a) for a in activities]


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single activity by ID."""
    result = await db.execute(
        select(Activity)
        .options(selectinload(Activity.activity_people).selectinload(ActivityPerson.person))
        .where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return _activity_to_response(activity)


@router.put("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an activity record."""
    result = await db.execute(
        select(Activity)
        .options(selectinload(Activity.activity_people).selectinload(ActivityPerson.person))
        .where(Activity.id == activity_id, Activity.user_id == current_user.id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle people_ids update
    new_people_ids = update_data.pop("people_ids", None)
    if new_people_ids is not None:
        # Validate all people
        for pid in new_people_ids:
            await _validate_person(db, pid, current_user.id)
        # Remove existing join records
        for ap in list(activity.activity_people):
            await db.delete(ap)
        await db.flush()
        # Create new join records
        await _create_activity_people(db, activity.id, new_people_ids)
        # Update compat person_id
        if len(new_people_ids) == 1:
            activity.person_id = new_people_ids[0]
        elif len(new_people_ids) == 0:
            activity.person_id = None

    if "person_id" in update_data and update_data["person_id"] is not None:
        await _validate_person(db, update_data["person_id"], current_user.id)
    if "property_id" in update_data and update_data["property_id"] is not None:
        await _validate_property(db, update_data["property_id"], current_user.id)

    for key, value in update_data.items():
        setattr(activity, key, value)

    await db.flush()

    # Reload for response
    result = await db.execute(
        select(Activity)
        .options(selectinload(Activity.activity_people).selectinload(ActivityPerson.person))
        .where(Activity.id == activity.id)
    )
    activity = result.scalar_one()
    dashboard_cache.invalidate(current_user.id)
    return _activity_to_response(activity)


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
