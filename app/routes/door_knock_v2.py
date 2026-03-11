"""Door Knock Workflow V2 — Sessions, Entries, Follow-Up Tasks, and 10-10-20 Nearby."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    CoverageActivity,
    DoorKnockEntry,
    DoorKnockSession,
    FollowUpTask,
    Person,
    Property,
    Signal,
    Territory,
)
from app.schemas.door_knock import (
    DoorKnockEntryCreate,
    DoorKnockEntryResponse,
    DoorKnockSessionCreate,
    DoorKnockSessionDetailResponse,
    DoorKnockSessionResponse,
    FollowUpTaskCreate,
    FollowUpTaskResponse,
    FollowUpTaskUpdate,
)
from app.services.auth import get_current_user


# ── Door Knock Sessions ──────────────────────────────────────────────────────

session_router = APIRouter(prefix="/door-knock/sessions", tags=["Door Knock"])


@session_router.post("/", response_model=DoorKnockSessionResponse, status_code=201)
async def start_session(
    data: DoorKnockSessionCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new door knock session."""
    if data.territory_id:
        t = await db.get(Territory, data.territory_id)
        if not t or t.user_id != user.id:
            raise HTTPException(status_code=404, detail="Territory not found")

    session = DoorKnockSession(
        user_id=user.id,
        territory_id=data.territory_id,
        notes=data.notes,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return DoorKnockSessionResponse.model_validate(session)


@session_router.get("/", response_model=list[DoorKnockSessionResponse])
async def list_sessions(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List sessions from the last 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.execute(
        select(DoorKnockSession)
        .where(
            DoorKnockSession.user_id == user.id,
            DoorKnockSession.created_at >= cutoff,
        )
        .order_by(DoorKnockSession.created_at.desc())
    )
    return [DoorKnockSessionResponse.model_validate(s) for s in result.scalars().all()]


@session_router.get("/{session_id}", response_model=DoorKnockSessionDetailResponse)
async def get_session(
    session_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get session with all entries."""
    result = await db.execute(
        select(DoorKnockSession).where(
            DoorKnockSession.id == session_id,
            DoorKnockSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    entries_result = await db.execute(
        select(DoorKnockEntry)
        .where(DoorKnockEntry.session_id == session_id)
        .order_by(DoorKnockEntry.knocked_at.asc())
    )
    entries = entries_result.scalars().all()

    detail = DoorKnockSessionDetailResponse.model_validate(session)
    detail.entries = [DoorKnockEntryResponse.model_validate(e) for e in entries]
    return detail


@session_router.put("/{session_id}/end", response_model=DoorKnockSessionResponse)
async def end_session(
    session_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """End a door knock session."""
    result = await db.execute(
        select(DoorKnockSession).where(
            DoorKnockSession.id == session_id,
            DoorKnockSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return DoorKnockSessionResponse.model_validate(session)


@session_router.get("/{session_id}/entries", response_model=list[DoorKnockEntryResponse])
async def list_session_entries(
    session_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all entries for a session."""
    result = await db.execute(
        select(DoorKnockSession).where(
            DoorKnockSession.id == session_id,
            DoorKnockSession.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    entries_result = await db.execute(
        select(DoorKnockEntry)
        .where(DoorKnockEntry.session_id == session_id)
        .order_by(DoorKnockEntry.knocked_at.asc())
    )
    return [DoorKnockEntryResponse.model_validate(e) for e in entries_result.scalars().all()]


# ── Door Knock Entries ───────────────────────────────────────────────────────

entry_router = APIRouter(prefix="/door-knock/entries", tags=["Door Knock"])


@entry_router.post("/", response_model=DoorKnockEntryResponse, status_code=201)
async def log_entry(
    data: DoorKnockEntryCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log a door knock entry.

    Side effects:
    - If session has a territory_id: auto-creates a coverage_activity of type 'door_knock'
    - Increments session.total_knocks
    """
    # Verify session belongs to user
    session_result = await db.execute(
        select(DoorKnockSession).where(
            DoorKnockSession.id == data.session_id,
            DoorKnockSession.user_id == user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    entry = DoorKnockEntry(
        session_id=data.session_id,
        property_id=data.property_id,
        property_address=data.property_address,
        knock_result=data.knock_result,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        interest_level=data.interest_level,
        voice_note_transcript=data.voice_note_transcript,
        notes=data.notes,
    )
    db.add(entry)

    # Increment total_knocks on session
    session.total_knocks = (session.total_knocks or 0) + 1

    # Auto-create coverage activity if session has a territory
    if session.territory_id:
        coverage = CoverageActivity(
            user_id=user.id,
            territory_id=session.territory_id,
            property_id=data.property_id,
            activity_type="door_knock",
            notes=data.notes or f"Door knock at {data.property_address} — {data.knock_result}",
        )
        db.add(coverage)

    await db.commit()
    await db.refresh(entry)
    return DoorKnockEntryResponse.model_validate(entry)


@entry_router.post("/{entry_id}/create-contact")
async def create_contact_from_entry(
    entry_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a contact from a door knock entry.

    Extracts first/last name from contact_name, phone from contact_phone,
    notes from voice_note_transcript, and suburb from property_address.
    Updates entry.created_contact_id.
    """
    # Verify entry belongs to user (via session)
    entry_result = await db.execute(
        select(DoorKnockEntry)
        .join(DoorKnockSession, DoorKnockEntry.session_id == DoorKnockSession.id)
        .where(
            DoorKnockEntry.id == entry_id,
            DoorKnockSession.user_id == user.id,
        )
    )
    entry = entry_result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if entry.created_contact_id:
        raise HTTPException(status_code=409, detail="Contact already created from this entry")

    if not entry.contact_name and not entry.contact_phone:
        raise HTTPException(status_code=422, detail="Entry has no contact_name or contact_phone to create a contact from")

    # Parse first/last name
    name_parts = (entry.contact_name or "").strip().split(" ", 1)
    first_name = name_parts[0] if name_parts else "Unknown"
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Extract suburb from property address (last word before comma or end)
    suburb = None
    if entry.property_address:
        parts = [p.strip() for p in entry.property_address.split(",")]
        if len(parts) >= 2:
            suburb = parts[-2].strip()  # e.g. "12 Main St, Papamoa, Tauranga" → "Papamoa"
        elif len(parts) == 1:
            suburb = None

    # Build notes
    notes_parts = []
    if entry.voice_note_transcript:
        notes_parts.append(f"Voice note: {entry.voice_note_transcript}")
    if entry.notes:
        notes_parts.append(entry.notes)
    if entry.interest_level:
        notes_parts.append(f"Interest level: {entry.interest_level}")
    notes_parts.append(f"Met via door knock at {entry.property_address}")
    notes = " | ".join(notes_parts)

    # Phone is required on Person — use placeholder if missing
    phone = entry.contact_phone or f"dk-{entry_id}"

    person = Person(
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        suburb=suburb,
        notes=notes,
        contact_status="active",
        original_source="door_knock",
    )
    db.add(person)
    await db.flush()  # get person.id

    entry.created_contact_id = person.id
    await db.commit()
    await db.refresh(person)

    return {
        "id": person.id,
        "first_name": person.first_name,
        "last_name": person.last_name,
        "phone": person.phone,
        "suburb": person.suburb,
        "notes": person.notes,
        "contact_status": person.contact_status,
    }


# ── Follow-Up Tasks ──────────────────────────────────────────────────────────

task_router = APIRouter(prefix="/follow-up-tasks", tags=["Follow-Up Tasks"])


@task_router.post("/", response_model=FollowUpTaskResponse, status_code=201)
async def create_task(
    data: FollowUpTaskCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a follow-up task."""
    task = FollowUpTask(
        user_id=user.id,
        title=data.title,
        description=data.description,
        related_property_id=data.related_property_id,
        related_person_id=data.related_person_id,
        related_session_id=data.related_session_id,
        due_date=data.due_date,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return FollowUpTaskResponse.model_validate(task)


@task_router.get("/", response_model=list[FollowUpTaskResponse])
async def list_tasks(
    include_completed: bool = False,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List follow-up tasks. Defaults to incomplete only."""
    q = select(FollowUpTask).where(FollowUpTask.user_id == user.id)
    if not include_completed:
        q = q.where(FollowUpTask.is_completed == False)
    q = q.order_by(FollowUpTask.due_date.asc().nullslast(), FollowUpTask.created_at.asc())
    result = await db.execute(q)
    return [FollowUpTaskResponse.model_validate(t) for t in result.scalars().all()]


@task_router.put("/{task_id}", response_model=FollowUpTaskResponse)
async def update_task(
    task_id: int,
    data: FollowUpTaskUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a follow-up task (mark complete, update due date, etc.)."""
    result = await db.execute(
        select(FollowUpTask).where(
            FollowUpTask.id == task_id,
            FollowUpTask.user_id == user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    # Set completed_at when marking complete
    if data.is_completed is True and not task.completed_at:
        task.completed_at = datetime.now(timezone.utc)
    elif data.is_completed is False:
        task.completed_at = None

    await db.commit()
    await db.refresh(task)
    return FollowUpTaskResponse.model_validate(task)


# ── 10-10-20 Nearby Properties ───────────────────────────────────────────────

nearby_router = APIRouter(prefix="/properties", tags=["Property Intelligence"])


@nearby_router.get("/{property_id}/nearby")
async def get_nearby_properties(
    property_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return 10-10-20 nearby property suggestions.

    Given a property, returns other properties in the same suburb.
    Sorted: properties with active signals first, then by sellability desc.
    Split into: left (10), right (10), across (20).
    """
    # Get the anchor property
    anchor_result = await db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.user_id == user.id,
        )
    )
    anchor = anchor_result.scalar_one_or_none()
    if not anchor:
        raise HTTPException(status_code=404, detail="Property not found")

    if not anchor.suburb:
        return {"left": [], "right": [], "across": [], "total": 0, "suburb": None}

    # Get other properties in same suburb (exclude anchor)
    suburb_result = await db.execute(
        select(Property)
        .where(
            Property.user_id == user.id,
            Property.id != property_id,
            Property.suburb == anchor.suburb,
        )
        .limit(100)
    )
    candidates = suburb_result.scalars().all()

    if not candidates:
        return {"left": [], "right": [], "across": [], "total": 0, "suburb": anchor.suburb}

    # Get property IDs with active signals
    candidate_ids = [p.id for p in candidates]
    signal_result = await db.execute(
        select(Signal.entity_id)
        .where(
            Signal.user_id == user.id,
            Signal.entity_type == "property",
            Signal.entity_id.in_(candidate_ids),
            Signal.is_active == True,
        )
        .distinct()
    )
    signal_property_ids = {row[0] for row in signal_result.fetchall()}

    # Sort: has signal first, then sellability desc, then id
    def sort_key(p):
        has_signal = 1 if p.id in signal_property_ids else 0
        sellability = p.sellability or 0
        return (-has_signal, -sellability, p.id)

    sorted_props = sorted(candidates, key=sort_key)

    def prop_to_dict(p):
        return {
            "id": p.id,
            "address": p.address,
            "suburb": p.suburb,
            "sellability": p.sellability,
            "has_signal": p.id in signal_property_ids,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "cv": p.cv,
            "last_listing_result": p.last_listing_result.value if p.last_listing_result else None,
        }

    # Split into left (10), right (10), across (20)
    left = [prop_to_dict(p) for p in sorted_props[:10]]
    right = [prop_to_dict(p) for p in sorted_props[10:20]]
    across = [prop_to_dict(p) for p in sorted_props[20:40]]

    return {
        "left": left,
        "right": right,
        "across": across,
        "total": len(sorted_props),
        "suburb": anchor.suburb,
    }
