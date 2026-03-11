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
    CommunityEntity,
    InteractionType,
    TierEnum,
    CadenceStatus,
    RapportAnchor,
    AnchorStatus,
    RelationshipSummary,
    SummaryStatus,
    Signal,
    SuggestedOutreach,
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
    BriefingContact,
    BriefingAnchor,
    BriefingSignal,
    BriefingResponse,
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

    # Create open_home_attendance activity with due_date = 24h from now
    now = datetime.now(timezone.utc)
    activity = Activity(
        user_id=current_user.id,
        person_id=person.id,
        property_id=payload.property_id,
        interaction_type=InteractionType.open_home_attendance,
        date=now,
        due_date=now + timedelta(hours=24),
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
    needs_attention_count = 0
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

        # needs_attention: contacts overdue by their tier cadence window
        # Reference date = max(last_activity_date, created_at) so new contacts
        # are not immediately counted as overdue.
        # A-tier: overdue if reference_date > 30 days ago
        # B-tier: overdue if reference_date > 60 days ago
        # C-tier: overdue if reference_date > 90 days ago
        window = get_cadence_window(person.tier)
        created_aware = person.created_at if person.created_at.tzinfo else person.created_at.replace(tzinfo=timezone.utc)
        if last_m is None:
            reference_date = created_aware
        else:
            last_m_aware = last_m if last_m.tzinfo else last_m.replace(tzinfo=timezone.utc)
            reference_date = max(last_m_aware, created_aware)
        if (now - reference_date).days > window:
            needs_attention_count += 1

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

    # Build property address lookup for callbacks
    property_ids_needed = set(att.property_id for att in recent_attendances if att.property_id)
    property_address_map: dict[int, str] = {}
    if property_ids_needed:
        props_result = await db.execute(
            select(Property.id, Property.address).where(Property.id.in_(property_ids_needed))
        )
        for row in props_result.all():
            property_address_map[row[0]] = row[1]

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
                    property_address=property_address_map.get(att.property_id) if att.property_id else None,
                    attendance_date=att.date,
                    due_date=att.due_date,
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

    # ── QUERY 7: Active listings count ──
    listings_result = await db.execute(
        select(func.count(Property.id)).where(Property.user_id == uid)
    )
    active_listings_count = listings_result.scalar() or 0

    # ── QUERY 8: Active appraisals count ──
    appraisals_result = await db.execute(
        select(func.count(Property.id)).where(
            Property.user_id == uid,
            Property.appraisal_status.in_(["booked", "completed"]),
        )
    )
    active_appraisals_count = appraisals_result.scalar() or 0

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
            needs_attention=needs_attention_count,
        ),
        tier_breakdown=TierBreakdown(
            tier_a=tier_counts["A"],
            tier_b=tier_counts["B"],
            tier_c=tier_counts["C"],
            tier_d=tier_counts["D"],
            total=len(all_people),
        ),
        active_listings=active_listings_count,
        active_appraisals=active_appraisals_count,
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


# ── Enriched Briefing ────────────────────────────────────────────────────────


@router.get("/dashboard/briefing", response_model=BriefingResponse, tags=["Dashboard"])
async def get_briefing(
    limit: int = Query(20, ge=1, le=100, description="Max contacts to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enriched Daily Relationship Briefing.

    Returns contacts sorted by urgency (red → amber → green) with:
    - relationship_summary: accepted summary text (or null)
    - rapport_anchors: up to 2 accepted anchors
    - suggested_outreach: current outreach message (or null)
    """
    uid = current_user.id
    now = datetime.now(timezone.utc)

    # ── 1. Fetch all people ──
    people_result = await db.execute(
        select(Person).where(Person.user_id == uid)
    )
    all_people = people_result.scalars().all()

    if not all_people:
        return BriefingResponse(contacts=[], total=0)

    person_ids = [p.id for p in all_people]

    # ── 2. Batch last meaningful interaction per person ──
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

    # ── 3. Compute cadence for all people and sort by urgency ──
    status_order = {"red": 0, "amber": 1, "green": 2}
    scored_people = []
    for person in all_people:
        last_m = last_meaningful_map.get(person.id)
        cadence_st, days_since = compute_cadence_status(person.tier, last_m, now)
        scored_people.append((person, cadence_st, days_since))

    scored_people.sort(
        key=lambda x: (status_order.get(x[1].value, 3), -(x[2] or 0))
    )

    # Limit to requested count
    top_people = scored_people[:limit]
    top_person_ids = [p.id for p, _, _ in top_people]

    # ── 4. Batch fetch accepted relationship summaries ──
    summary_map: dict[int, str] = {}
    if top_person_ids:
        summary_result = await db.execute(
            select(RelationshipSummary)
            .where(
                RelationshipSummary.user_id == uid,
                RelationshipSummary.person_id.in_(top_person_ids),
                RelationshipSummary.status == SummaryStatus.accepted,
            )
        )
        for s in summary_result.scalars().all():
            summary_map[s.person_id] = s.summary_text

    # ── 5. Batch fetch accepted rapport anchors (up to 2 per person) ──
    anchor_map: dict[int, list[BriefingAnchor]] = {}
    if top_person_ids:
        anchor_result = await db.execute(
            select(RapportAnchor)
            .where(
                RapportAnchor.user_id == uid,
                RapportAnchor.person_id.in_(top_person_ids),
                RapportAnchor.status == AnchorStatus.accepted,
            )
            .order_by(RapportAnchor.created_at.desc())
        )
        for a in anchor_result.scalars().all():
            lst = anchor_map.setdefault(a.person_id, [])
            if len(lst) < 2:
                lst.append(BriefingAnchor(
                    id=a.id,
                    anchor_text=a.anchor_text,
                    anchor_type=a.anchor_type,
                ))

    # ── 6. Batch fetch current suggested outreach ──
    outreach_map: dict[int, str] = {}
    if top_person_ids:
        outreach_result = await db.execute(
            select(SuggestedOutreach)
            .where(
                SuggestedOutreach.user_id == uid,
                SuggestedOutreach.person_id.in_(top_person_ids),
                SuggestedOutreach.is_current == True,
            )
        )
        for o in outreach_result.scalars().all():
            outreach_map[o.person_id] = o.message_text

    # ── 7. Build response ──
    contacts = []
    for person, cadence_st, days_since in top_people:
        contacts.append(BriefingContact(
            person_id=person.id,
            first_name=person.first_name,
            last_name=person.last_name,
            phone=person.phone,
            tier=person.tier.value if person.tier else "C",
            cadence_status=cadence_st.value,
            days_since_last_meaningful=days_since,
            cadence_window_days=get_cadence_window(person.tier),
            relationship_summary=summary_map.get(person.id),
            rapport_anchors=anchor_map.get(person.id, []),
            suggested_outreach=outreach_map.get(person.id),
        ))

    # ── 8. Fetch top active signals (max 5, sorted by confidence desc) ──
    sig_result = await db.execute(
        select(Signal)
        .where(Signal.user_id == uid, Signal.is_active == True)
        .order_by(Signal.confidence.desc())
        .limit(5)
    )
    briefing_signals = []
    for sig in sig_result.scalars().all():
        entity_name = None
        if sig.entity_type == "person":
            p_res = await db.execute(select(Person).where(Person.id == sig.entity_id))
            p_obj = p_res.scalar_one_or_none()
            if p_obj:
                entity_name = f"{p_obj.first_name} {p_obj.last_name or ''}".strip()
        elif sig.entity_type == "property":
            pr_res = await db.execute(select(Property).where(Property.id == sig.entity_id))
            pr_obj = pr_res.scalar_one_or_none()
            if pr_obj:
                entity_name = pr_obj.address
        elif sig.entity_type == "community":
            ce_res = await db.execute(select(CommunityEntity).where(CommunityEntity.id == sig.entity_id))
            ce_obj = ce_res.scalar_one_or_none()
            if ce_obj:
                entity_name = ce_obj.name
        briefing_signals.append(BriefingSignal(
            id=sig.id,
            signal_type=sig.signal_type.value,
            entity_type=sig.entity_type,
            entity_id=sig.entity_id,
            entity_name=entity_name,
            confidence=sig.confidence,
            description=sig.description,
        ))

    return BriefingResponse(
        contacts=contacts,
        signals=briefing_signals,
        total=len(all_people),
    )
