"""Dashboard aggregation, Open Home Kiosk, and AI suggestion endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    User,
    Person,
    Property,
    Activity,
    InteractionType,
    TierEnum,
    CadenceStatus,
)
from app.schemas.dashboard import (
    OpenHomeCheckin,
    OpenHomeCheckinResponse,
    DashboardResponse,
    DriftingRelationship,
    DueForContact,
    OpenHomeCallback,
    RepeatAttendee,
    PersonCadenceStatus,
    CadenceSummary,
    TierBreakdown,
    AISuggestion,
    AISuggestionsResponse,
)
from app.services.auth import get_current_user
from app.services.cadence import (
    compute_cadence_status,
    get_cadence_window,
    days_until_deadline,
    AMBER_THRESHOLD_DAYS,
)
from app.services import dashboard_cache

router = APIRouter(tags=["Dashboard & Kiosk"])


# ── Open Home Kiosk ───────────────────────────────────────────────────────────


@router.post(
    "/open-home/checkin",
    response_model=OpenHomeCheckinResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Open Home Kiosk"],
)
async def open_home_checkin(
    payload: OpenHomeCheckin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Kiosk-style check-in for open home events.

    Accepts phone + name + property_id. Finds or creates the person,
    then auto-creates an open_home_attendance activity linked to the property.
    """
    # Validate property
    prop_result = await db.execute(
        select(Property).where(Property.id == payload.property_id, Property.user_id == current_user.id)
    )
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    # Find or create person by phone
    is_new = False
    result = await db.execute(
        select(Person).where(Person.user_id == current_user.id, Person.phone == payload.phone)
    )
    person = result.scalar_one_or_none()

    if person is None:
        person = Person(
            user_id=current_user.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=payload.phone,
            lead_source="open_home",
            tier=TierEnum.C,
        )
        db.add(person)
        await db.flush()
        await db.refresh(person)
        is_new = True
    else:
        if payload.first_name and not person.first_name:
            person.first_name = payload.first_name
        if payload.last_name and not person.last_name:
            person.last_name = payload.last_name
        await db.flush()

    # Create open_home_attendance activity
    activity = Activity(
        user_id=current_user.id,
        person_id=person.id,
        property_id=payload.property_id,
        interaction_type=InteractionType.open_home_attendance,
        date=datetime.now(timezone.utc),
        notes=f"Open home check-in at {prop.address}",
        is_meaningful=True,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)

    # Invalidate dashboard cache for this user
    dashboard_cache.invalidate(current_user.id)

    return OpenHomeCheckinResponse(
        person_id=person.id,
        activity_id=activity.id,
        is_new_person=is_new,
        message=f"{'New person created' if is_new else 'Existing person found'} and open home attendance recorded.",
    )


# ── Dashboard Aggregation (OPTIMISED — batch queries + TTL cache) ────────────


async def _build_dashboard(
    uid: int,
    db: AsyncSession,
    cadence_limit: int,
) -> dict:
    """Build the full dashboard response from database queries."""
    now = datetime.now(timezone.utc)

    # ── QUERY 1: Fetch all people for this user ──
    people_result = await db.execute(
        select(Person).where(Person.user_id == uid)
    )
    all_people = people_result.scalars().all()

    if not all_people:
        return DashboardResponse(
            a_tier_drifting=[],
            due_for_contact_this_week=[],
            open_home_callbacks_needed=[],
            repeat_open_home_attendees=[],
            cadence_statuses=[],
            cadence_summary=CadenceSummary(),
            tier_breakdown=TierBreakdown(),
            cached=False,
        ).model_dump()

    people_by_id = {p.id: p for p in all_people}
    person_ids = list(people_by_id.keys())

    # ── QUERY 2: Batch last meaningful interaction per person ──
    last_meaningful_result = await db.execute(
        select(
            Activity.person_id,
            func.max(Activity.date).label("last_date"),
        )
        .where(
            Activity.user_id == uid,
            Activity.is_meaningful == True,
            Activity.person_id.in_(person_ids),
        )
        .group_by(Activity.person_id)
    )
    last_meaningful_map: dict[int, datetime | None] = {}
    for row in last_meaningful_result.all():
        last_meaningful_map[row[0]] = row[1]

    # ── Compute cadence for all people (in-memory) ──
    a_tier_drifting: list[DriftingRelationship] = []
    due_for_contact: list[DueForContact] = []
    all_cadence_statuses: list[PersonCadenceStatus] = []
    green_count = 0
    amber_count = 0
    red_count = 0
    tier_counts: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}

    for person in all_people:
        last_m = last_meaningful_map.get(person.id)
        cadence_st, days_since = compute_cadence_status(person.tier, last_m, now)

        # Count for cadence summary
        if cadence_st == CadenceStatus.green:
            green_count += 1
        elif cadence_st == CadenceStatus.amber:
            amber_count += 1
        else:
            red_count += 1

        # Count for tier breakdown
        tier_val = person.tier.value if person.tier else "C"
        if tier_val in tier_counts:
            tier_counts[tier_val] += 1

        # Build cadence status entry (we'll limit later)
        all_cadence_statuses.append(PersonCadenceStatus(
            person_id=person.id,
            first_name=person.first_name,
            last_name=person.last_name,
            tier=person.tier.value,
            cadence_status=cadence_st.value,
            days_since_last_meaningful=days_since,
            cadence_window_days=get_cadence_window(person.tier),
        ))

        # A-tier drifting
        if person.tier == TierEnum.A and cadence_st == CadenceStatus.red:
            a_tier_drifting.append(DriftingRelationship(
                person_id=person.id,
                first_name=person.first_name,
                last_name=person.last_name,
                phone=person.phone,
                tier=person.tier.value,
                days_since_last_meaningful=days_since if days_since is not None else 9999,
                cadence_window_days=get_cadence_window(person.tier),
            ))

        # Due for contact this week
        dtd = days_until_deadline(person.tier, last_m, now)
        if dtd is not None and 0 < dtd <= AMBER_THRESHOLD_DAYS:
            due_for_contact.append(DueForContact(
                person_id=person.id,
                first_name=person.first_name,
                last_name=person.last_name,
                phone=person.phone,
                tier=person.tier.value,
                days_until_deadline=dtd,
                cadence_window_days=get_cadence_window(person.tier),
            ))

    # Sort cadence statuses: red first, then amber, then green — most urgent on top
    status_order = {"red": 0, "amber": 1, "green": 2}
    all_cadence_statuses.sort(key=lambda x: (status_order.get(x.cadence_status, 3), -(x.days_since_last_meaningful or 0)))

    # Limit cadence_statuses to requested amount
    limited_cadence = all_cadence_statuses[:cadence_limit]

    # ── QUERY 3: Open home callbacks needed (last 7 days) ──
    seven_days_ago = now - timedelta(days=7)

    attendance_result = await db.execute(
        select(Activity).where(
            Activity.user_id == uid,
            Activity.interaction_type == InteractionType.open_home_attendance,
            Activity.date >= seven_days_ago,
        )
    )
    recent_attendances = attendance_result.scalars().all()

    # QUERY 4: Callback person_ids in last 7 days
    callback_result = await db.execute(
        select(Activity.person_id).where(
            Activity.user_id == uid,
            Activity.interaction_type == InteractionType.open_home_callback,
            Activity.date >= seven_days_ago,
        )
    )
    callback_person_ids = set(row[0] for row in callback_result.all())

    callbacks_needed: list[OpenHomeCallback] = []
    seen_callback_persons: set[int] = set()
    for att in recent_attendances:
        if att.person_id not in callback_person_ids and att.person_id not in seen_callback_persons:
            seen_callback_persons.add(att.person_id)
            person = people_by_id.get(att.person_id)
            if person:
                callbacks_needed.append(OpenHomeCallback(
                    person_id=person.id,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    phone=person.phone,
                    property_id=att.property_id,
                    attendance_date=att.date,
                ))

    # ── QUERY 5: Repeat open home attendees ──
    repeat_result = await db.execute(
        select(
            Activity.person_id,
            func.count(Activity.id).label("cnt"),
        )
        .where(
            Activity.user_id == uid,
            Activity.interaction_type == InteractionType.open_home_attendance,
        )
        .group_by(Activity.person_id)
        .having(func.count(Activity.id) > 1)
    )
    repeat_rows = repeat_result.all()

    repeat_attendees: list[RepeatAttendee] = []
    if repeat_rows:
        repeat_person_ids = [row[0] for row in repeat_rows]
        repeat_count_map = {row[0]: row[1] for row in repeat_rows}

        # QUERY 6: Batch distinct property_ids per repeat attendee
        props_result = await db.execute(
            select(
                Activity.person_id,
                Activity.property_id,
            )
            .where(
                Activity.person_id.in_(repeat_person_ids),
                Activity.interaction_type == InteractionType.open_home_attendance,
                Activity.property_id.isnot(None),
            )
            .distinct()
        )
        person_props_map: dict[int, list[int]] = {}
        for row in props_result.all():
            person_props_map.setdefault(row[0], []).append(row[1])

        for pid in repeat_person_ids:
            person = people_by_id.get(pid)
            if person:
                repeat_attendees.append(RepeatAttendee(
                    person_id=person.id,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    phone=person.phone,
                    attendance_count=repeat_count_map[pid],
                    properties_visited=person_props_map.get(pid, []),
                ))

    response = DashboardResponse(
        a_tier_drifting=a_tier_drifting,
        due_for_contact_this_week=due_for_contact,
        open_home_callbacks_needed=callbacks_needed,
        repeat_open_home_attendees=repeat_attendees,
        cadence_statuses=limited_cadence,
        cadence_summary=CadenceSummary(
            total_people=len(all_people),
            green=green_count,
            amber=amber_count,
            red=red_count,
        ),
        tier_breakdown=TierBreakdown(
            A=tier_counts["A"],
            B=tier_counts["B"],
            C=tier_counts["C"],
            D=tier_counts["D"],
            total=len(all_people),
        ),
        cached=False,
    )
    return response.model_dump()


@router.get("/dashboard", response_model=DashboardResponse, tags=["Dashboard"])
async def get_dashboard(
    cadence_limit: int = Query(20, ge=1, le=2000, description="Max cadence statuses to return (default 20)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Main execution dashboard with per-user 5-minute TTL cache.

    Returns aggregated intelligence:
    - A-tier drifting relationships
    - People due for contact this week
    - Open home attendees needing callbacks
    - Repeat open home attendees
    - Top N cadence statuses (sorted by urgency)
    - Summary counts (total, green, amber, red)
    """
    # Check cache first
    cached = dashboard_cache.get(current_user.id)
    if cached is not None:
        # Return cached data but override cadence_limit
        result = dict(cached)
        result["cached"] = True
        # Re-slice cadence_statuses to respect the requested limit
        result["cadence_statuses"] = result.get("_all_cadence_statuses", result["cadence_statuses"])[:cadence_limit]
        return result

    # Build fresh dashboard
    data = await _build_dashboard(current_user.id, db, cadence_limit)

    # Store in cache — keep full cadence list for re-slicing on cache hits
    cache_data = dict(data)
    cache_data["_all_cadence_statuses"] = data["cadence_statuses"]
    dashboard_cache.put(current_user.id, cache_data)

    return data


@router.get("/dashboard/summary", response_model=DashboardResponse, tags=["Dashboard"])
async def get_dashboard_summary(
    cadence_limit: int = Query(20, ge=1, le=2000, description="Max cadence statuses to return (default 20)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Alias for /dashboard — the frontend calls this path.
    Returns the same aggregated dashboard data.
    """
    return await get_dashboard(cadence_limit=cadence_limit, db=db, current_user=current_user)


# ── AI Suggestions (Stub) ────────────────────────────────────────────────────


@router.get("/ai/suggestions", response_model=AISuggestionsResponse, tags=["AI Intelligence"])
async def get_ai_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI Intelligence Layer — stub endpoint returning mock suggestions.
    """
    result = await db.execute(
        select(Person)
        .where(Person.user_id == current_user.id)
        .order_by(Person.influence_score.desc())
        .limit(5)
    )
    top_people = result.scalars().all()

    suggestions: list[AISuggestion] = []

    if len(top_people) >= 1:
        p = top_people[0]
        suggestions.append(AISuggestion(
            suggestion_type="tier_promotion",
            person_id=p.id,
            title=f"Consider promoting {p.first_name} {p.last_name or ''} to A-tier",
            description=f"{p.first_name} has shown consistent engagement. Their interaction pattern suggests they should be elevated to A-tier for closer relationship management.",
            confidence=0.85,
        ))

    if len(top_people) >= 2:
        p = top_people[1]
        suggestions.append(AISuggestion(
            suggestion_type="call_preparation",
            person_id=p.id,
            title=f"Call prep summary for {p.first_name} {p.last_name or ''}",
            description=f"Before your next call with {p.first_name}, note: they have attended multiple open homes and may be ready to make a decision. Focus on understanding their timeline.",
            confidence=0.72,
        ))

    suggestions.append(AISuggestion(
        suggestion_type="general_insight",
        person_id=None,
        title="Suburb activity trend detected",
        description="There has been increased open home attendance from people in the Papamoa Beach area. Consider targeted outreach to your contacts in this suburb.",
        confidence=0.68,
    ))

    suggestions.append(AISuggestion(
        suggestion_type="email_summary",
        person_id=top_people[0].id if top_people else None,
        title="Email thread summary available",
        description="You have several long email threads that could benefit from AI summarisation. Enable email sync on key relationship assets to unlock this feature.",
        confidence=0.60,
    ))

    if len(top_people) >= 3:
        p = top_people[2]
        suggestions.append(AISuggestion(
            suggestion_type="repeat_buyer_signal",
            person_id=p.id,
            title=f"Repeat buyer signal for {p.first_name} {p.last_name or ''}",
            description=f"{p.first_name} has attended open homes for multiple properties. This pattern often indicates active buyer intent. Prioritise a coffee meeting.",
            confidence=0.78,
        ))

    return AISuggestionsResponse(suggestions=suggestions)
