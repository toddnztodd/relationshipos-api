"""People (Person) CRUD routes with search, filtering, health status, and next-best."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, Activity, TierEnum, InteractionType
from app.schemas.person import (
    PersonCreate,
    PersonUpdate,
    PersonResponse,
    PersonWithCadence,
    PersonSearchByPhone,
    NextBestContact,
)
from app.services.auth import get_current_user
from app.services.cadence import compute_cadence_status, get_cadence_window, CADENCE_WINDOWS
from app.services import dashboard_cache
from app.services.parse_voice import parse_voice_to_contact

router = APIRouter(prefix="/people", tags=["People"])

# ── Interaction type → channel mapping ──────────────────────────────────────
INTERACTION_CHANNEL_MAP = {
    "phone_call": "call",
    "text_message": "text",
    "email_conversation": "email",
    "coffee_meeting": "call",       # face-to-face, closest channel
    "door_knock": "call",           # in-person
    "open_home_attendance": "call",  # in-person
    "open_home_callback": "call",   # follow-up call
}


def _compute_health(tier: TierEnum, reference_date: datetime | None, now: datetime | None = None) -> tuple[str, int | None, int]:
    """
    Compute health_status, days_since_contact, and cadence_limit.
    Uses reference_date = max(last_interaction_at, created_at).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    cadence_limit = get_cadence_window(tier)

    if reference_date is None:
        return "Overdue", None, cadence_limit

    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)

    days_since = (now - reference_date).days

    if days_since > cadence_limit:
        health = "Overdue"
    elif days_since >= cadence_limit - 14:
        health = "At Risk"
    else:
        health = "Healthy"

    return health, days_since, cadence_limit


async def _update_last_interaction(db: AsyncSession, person_id: int, interaction_type: str, interaction_date: datetime | None = None):
    """Update last_interaction_at and last_interaction_channel on a person record."""
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        return

    ts = interaction_date or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    # Only update if this interaction is more recent
    if person.last_interaction_at is None or ts >= person.last_interaction_at:
        person.last_interaction_at = ts
        channel = INTERACTION_CHANNEL_MAP.get(interaction_type if isinstance(interaction_type, str) else interaction_type.value, "call")
        person.last_interaction_channel = channel
        await db.flush()


# ── Voice-to-form contact parsing ────────────────────────────────────────────

class ParseVoiceRequest(BaseModel):
    transcription: str


class ParseVoiceResponse(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    suburb: Optional[str] = None
    tier: Optional[str] = None
    tags: list[str] = []
    notes: Optional[str] = None


@router.post("/parse-voice", response_model=ParseVoiceResponse)
async def parse_voice(
    payload: ParseVoiceRequest,
    current_user: User = Depends(get_current_user),
):
    """Extract structured contact fields from a voice transcription.

    Accepts a free-form transcription (e.g. from a voice note recorded in the
    field) and returns a structured object ready to pre-fill a contact creation
    form. No contact is created — this is a parsing-only endpoint.
    """
    if not payload.transcription or not payload.transcription.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="transcription must not be empty",
        )
    try:
        result = await parse_voice_to_contact(payload.transcription.strip())
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    return result


# ── Contact Vault endpoints ──────────────────────────────────────────────────


class VaultRequest(BaseModel):
    vault_note: Optional[str] = None


class BulkVaultRequest(BaseModel):
    ids: list[int]
    vault_note: Optional[str] = None


class BulkVaultResponse(BaseModel):
    vaulted: int


class CheckDuplicateRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


class CheckDuplicateResponse(BaseModel):
    match: Optional[PersonResponse] = None
    match_type: Optional[str] = None  # 'phone' | 'email' | 'name' | null


async def _create_vault_activity(
    db: AsyncSession, user_id: int, person_id: int,
    interaction_type: InteractionType, notes: str,
):
    """Create an activity log entry for vault/restore actions."""
    activity = Activity(
        user_id=user_id,
        person_id=person_id,
        interaction_type=interaction_type,
        notes=notes,
        is_meaningful=False,
        source="system",
    )
    db.add(activity)


@router.patch("/{person_id}/vault", response_model=PersonResponse)
async def vault_contact(
    person_id: int,
    payload: VaultRequest = VaultRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a contact to the vault."""
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    person.contact_status = "vaulted"
    person.vaulted_at = datetime.now(timezone.utc)
    if payload.vault_note:
        person.vault_note = payload.vault_note

    await _create_vault_activity(
        db, current_user.id, person.id,
        InteractionType.vault,
        payload.vault_note or "Contact vaulted",
    )

    await db.flush()
    await db.refresh(person)
    dashboard_cache.invalidate(current_user.id)
    return person


@router.patch("/{person_id}/restore", response_model=PersonResponse)
async def restore_contact(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore a contact from the vault."""
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    person.contact_status = "active"
    person.vaulted_at = None
    person.vault_note = None

    await _create_vault_activity(
        db, current_user.id, person.id,
        InteractionType.restore,
        "Contact restored from vault",
    )

    await db.flush()
    await db.refresh(person)
    dashboard_cache.invalidate(current_user.id)
    return person


@router.patch("/{person_id}/make-private", response_model=PersonResponse)
async def make_private(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a contact as private."""
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    person.contact_status = "private"
    await db.flush()
    await db.refresh(person)
    dashboard_cache.invalidate(current_user.id)
    return person


@router.post("/bulk-vault", response_model=BulkVaultResponse)
async def bulk_vault(
    payload: BulkVaultRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Vault multiple contacts at once."""
    result = await db.execute(
        select(Person).where(
            Person.id.in_(payload.ids),
            Person.user_id == current_user.id,
            Person.contact_status == "active",
        )
    )
    people = result.scalars().all()
    now = datetime.now(timezone.utc)
    count = 0
    for person in people:
        person.contact_status = "vaulted"
        person.vaulted_at = now
        if payload.vault_note:
            person.vault_note = payload.vault_note
        await _create_vault_activity(
            db, current_user.id, person.id,
            InteractionType.vault,
            payload.vault_note or "Contact vaulted (bulk)",
        )
        count += 1

    await db.flush()
    dashboard_cache.invalidate(current_user.id)
    return BulkVaultResponse(vaulted=count)


@router.get("/vaulted", response_model=list[PersonResponse])
async def list_vaulted(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all vaulted contacts."""
    result = await db.execute(
        select(Person).where(
            Person.user_id == current_user.id,
            Person.contact_status == "vaulted",
        ).order_by(Person.vaulted_at.desc())
    )
    return result.scalars().all()


@router.post("/check-duplicate", response_model=CheckDuplicateResponse)
async def check_duplicate(
    payload: CheckDuplicateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check vaulted contacts for duplicate matches.

    Priority: 1) phone exact match, 2) email exact match, 3) name similarity.
    """
    # 1. Phone exact match
    if payload.phone:
        result = await db.execute(
            select(Person).where(
                Person.user_id == current_user.id,
                Person.contact_status == "vaulted",
                Person.phone == payload.phone,
            )
        )
        match = result.scalar_one_or_none()
        if match:
            return CheckDuplicateResponse(match=PersonResponse.model_validate(match), match_type="phone")

    # 2. Email exact match
    if payload.email:
        result = await db.execute(
            select(Person).where(
                Person.user_id == current_user.id,
                Person.contact_status == "vaulted",
                Person.email == payload.email,
            )
        )
        match = result.scalar_one_or_none()
        if match:
            return CheckDuplicateResponse(match=PersonResponse.model_validate(match), match_type="email")

    # 3. Name similarity (case-insensitive contains)
    if payload.name:
        pattern = f"%{payload.name}%"
        result = await db.execute(
            select(Person).where(
                Person.user_id == current_user.id,
                Person.contact_status == "vaulted",
                (Person.first_name.ilike(pattern)) | (Person.last_name.ilike(pattern)),
            ).limit(1)
        )
        match = result.scalar_one_or_none()
        if match:
            return CheckDuplicateResponse(match=PersonResponse.model_validate(match), match_type="name")

    return CheckDuplicateResponse(match=None, match_type=None)


@router.post("/", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person(
    payload: PersonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new person record."""
    existing = await db.execute(
        select(Person).where(Person.user_id == current_user.id, Person.phone == payload.phone)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Person with phone '{payload.phone}' already exists",
        )

    person = Person(user_id=current_user.id, **payload.model_dump())
    db.add(person)
    await db.flush()
    await db.refresh(person)
    dashboard_cache.invalidate(current_user.id)
    return person


@router.get("/next-best", response_model=list[NextBestContact])
async def next_best_contacts(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return top N contacts ranked by urgency for next action.

    Priority:
    1. Overdue contacts first
    2. At Risk contacts
    3. Tier priority (A > B > C)
    4. Longest time since last interaction

    Uses last_interaction_at (falls back to created_at) for efficient single-query ranking.
    """
    now = datetime.now(timezone.utc)

    # Build reference_date as COALESCE(last_interaction_at, created_at)
    ref_date = func.coalesce(Person.last_interaction_at, Person.created_at)

    # Days since reference date
    days_since_expr = func.extract("epoch", func.now() - ref_date) / 86400.0

    # Cadence limit per tier
    cadence_limit_expr = case(
        (Person.tier == TierEnum.A, 30),
        (Person.tier == TierEnum.B, 60),
        else_=90,
    )

    # Tier priority (A=1, B=2, C=3) — lower is higher priority
    tier_priority = case(
        (Person.tier == TierEnum.A, 1),
        (Person.tier == TierEnum.B, 2),
        else_=3,
    )

    # Health status: 3=Overdue, 2=At Risk, 1=Healthy (sort desc for urgency)
    health_priority = case(
        (days_since_expr > cadence_limit_expr, 3),
        (days_since_expr >= cadence_limit_expr - 14, 2),
        else_=1,
    )

    query = (
        select(Person)
        .where(Person.user_id == current_user.id, Person.contact_status == "active")
        .order_by(
            health_priority.desc(),       # Overdue first
            tier_priority.asc(),          # A > B > C
            days_since_expr.desc(),       # Longest since contact first
        )
        .limit(limit)
    )

    result = await db.execute(query)
    people = result.scalars().all()

    contacts = []
    for p in people:
        ref = p.last_interaction_at or p.created_at
        health, days_since, cadence = _compute_health(p.tier, ref, now)
        contacts.append(NextBestContact(
            id=p.id,
            first_name=p.first_name,
            last_name=p.last_name,
            nickname=p.nickname,
            phone=p.phone,
            email=p.email,
            tier=p.tier,
            health_status=health,
            days_since_contact=days_since,
            cadence_limit=cadence,
            last_interaction_channel=p.last_interaction_channel,
        ))

    return contacts


@router.get("/", response_model=list[PersonWithCadence])
async def list_people(
    tier: Optional[TierEnum] = Query(None),
    relationship_type: Optional[str] = Query(None),
    suburb: Optional[str] = Query(None),
    is_relationship_asset: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search first_name, last_name, or phone"),
    include_status: Optional[str] = Query(None, description="Filter by contact_status: active (default), vaulted, private, or all"),
    sort_by: str = Query("created_at", regex="^(created_at|first_name|last_name|tier|influence_score|updated_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List people with optional filtering, sorting, and pagination.

    By default returns only active contacts. Use include_status=vaulted,
    include_status=private, or include_status=all to see other statuses.
    """
    now = datetime.now(timezone.utc)
    query = select(Person).where(Person.user_id == current_user.id)

    # Contact status filter — default to active only
    if include_status == "all":
        pass  # no filter
    elif include_status in ("vaulted", "private"):
        query = query.where(Person.contact_status == include_status)
    else:
        query = query.where(Person.contact_status == "active")

    if tier:
        query = query.where(Person.tier == tier)
    if relationship_type:
        query = query.where(Person.relationship_type == relationship_type)
    if suburb:
        query = query.where(Person.suburb.ilike(f"%{suburb}%"))
    if is_relationship_asset is not None:
        query = query.where(Person.is_relationship_asset == is_relationship_asset)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Person.first_name.ilike(pattern))
            | (Person.last_name.ilike(pattern))
            | (Person.phone.ilike(pattern))
        )

    sort_col = getattr(Person, sort_by, Person.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    people = result.scalars().all()

    if not people:
        return []

    # ── Batch fetch last meaningful activity for ALL people in ONE query ──────
    person_ids = [p.id for p in people]
    act_result = await db.execute(
        select(Activity.person_id, func.max(Activity.date).label("last_date"))
        .where(
            Activity.person_id.in_(person_ids),
            Activity.is_meaningful == True,
        )
        .group_by(Activity.person_id)
    )
    last_activity_map: dict = {row.person_id: row.last_date for row in act_result}

    # ── Enrich each person with cadence status and health fields ─────────────
    enriched = []
    for p in people:
        last_meaningful = last_activity_map.get(p.id)
        cadence_status, days_since = compute_cadence_status(p.tier, last_meaningful)
        window = get_cadence_window(p.tier)

        # Health uses max(last_interaction_at, created_at)
        ref = p.last_interaction_at or p.created_at
        health, days_since_contact, cadence_limit = _compute_health(p.tier, ref, now)

        person_data = PersonWithCadence.model_validate(p)
        person_data.cadence_status = cadence_status.value
        person_data.days_since_last_meaningful = days_since
        person_data.cadence_window_days = window
        person_data.health_status = health
        person_data.days_since_contact = days_since_contact
        person_data.cadence_limit = cadence_limit
        enriched.append(person_data)

    return enriched


@router.get("/search", response_model=PersonResponse | None)
async def search_by_phone(
    phone: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search for a person by phone number."""
    result = await db.execute(
        select(Person).where(Person.user_id == current_user.id, Person.phone == phone)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


@router.get("/{person_id}", response_model=PersonWithCadence)
async def get_person(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single person by ID with cadence status and health fields."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    act_result = await db.execute(
        select(func.max(Activity.date))
        .where(Activity.person_id == person.id, Activity.is_meaningful == True)
    )
    last_meaningful = act_result.scalar_one_or_none()
    cadence_status, days_since = compute_cadence_status(person.tier, last_meaningful)
    window = get_cadence_window(person.tier)

    ref = person.last_interaction_at or person.created_at
    health, days_since_contact, cadence_limit = _compute_health(person.tier, ref, now)

    person_data = PersonWithCadence.model_validate(person)
    person_data.cadence_status = cadence_status.value
    person_data.days_since_last_meaningful = days_since
    person_data.cadence_window_days = window
    person_data.health_status = health
    person_data.days_since_contact = days_since_contact
    person_data.cadence_limit = cadence_limit
    return person_data


@router.put("/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: int,
    payload: PersonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a person record."""
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "phone" in update_data and update_data["phone"] != person.phone:
        existing = await db.execute(
            select(Person).where(
                Person.user_id == current_user.id,
                Person.phone == update_data["phone"],
                Person.id != person_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone '{update_data['phone']}' already in use",
            )

    for key, value in update_data.items():
        setattr(person, key, value)

    await db.flush()
    await db.refresh(person)
    dashboard_cache.invalidate(current_user.id)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a person record."""
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    await db.delete(person)
    await db.flush()
    dashboard_cache.invalidate(current_user.id)
