"""Dashboard aggregation, Open Home Kiosk, and AI suggestion endpoints."""

from datetime import datetime, timedelta, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, and_, or_
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
    Designed to complete in < 5 seconds.
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
        # Update name if provided and person had empty fields
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

    return OpenHomeCheckinResponse(
        person_id=person.id,
        activity_id=activity.id,
        is_new_person=is_new,
        message=f"{'New person created' if is_new else 'Existing person found'} and open home attendance recorded.",
    )


# ── Dashboard Aggregation ─────────────────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardResponse, tags=["Dashboard"])
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Main execution dashboard. Returns aggregated intelligence:
    - A-tier drifting relationships (no meaningful interaction in 30+ days)
    - People due for contact this week (approaching cadence deadline within 7 days)
    - Open home attendees needing callbacks (attended in last 7 days, no callback logged)
    - Repeat open home attendees
    - Cadence status (green/amber/red) for each person
    """
    now = datetime.now(timezone.utc)

    # ── Fetch all people for this user ──
    people_result = await db.execute(
        select(Person).where(Person.user_id == current_user.id)
    )
    all_people = people_result.scalars().all()

    # ── Pre-compute last meaningful interaction for each person ──
    last_meaningful_map: dict[int, datetime | None] = {}
    for person in all_people:
        act_result = await db.execute(
            select(func.max(Activity.date)).where(
                Activity.person_id == person.id,
                Activity.is_meaningful == True,
            )
        )
        last_meaningful_map[person.id] = act_result.scalar_one_or_none()

    # ── 1. A-tier drifting relationships ──
    a_tier_drifting: list[DriftingRelationship] = []
    for person in all_people:
        if person.tier != TierEnum.A:
            continue
        last_m = last_meaningful_map.get(person.id)
        cadence_st, days_since = compute_cadence_status(person.tier, last_m, now)
        if cadence_st == CadenceStatus.red:
            a_tier_drifting.append(DriftingRelationship(
                person_id=person.id,
                first_name=person.first_name,
                last_name=person.last_name,
                phone=person.phone,
                tier=person.tier.value,
                days_since_last_meaningful=days_since if days_since is not None else 9999,
                cadence_window_days=get_cadence_window(person.tier),
            ))

    # ── 2. People due for contact this week (approaching deadline within 7 days) ──
    due_for_contact: list[DueForContact] = []
    for person in all_people:
        last_m = last_meaningful_map.get(person.id)
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

    # ── 3. Open home attendees needing callbacks ──
    seven_days_ago = now - timedelta(days=7)

    # Get all open_home_attendance in last 7 days
    attendance_result = await db.execute(
        select(Activity).where(
            Activity.user_id == current_user.id,
            Activity.interaction_type == InteractionType.open_home_attendance,
            Activity.date >= seven_days_ago,
        )
    )
    recent_attendances = attendance_result.scalars().all()

    # Get all open_home_callback person_ids in last 7 days
    callback_result = await db.execute(
        select(Activity.person_id).where(
            Activity.user_id == current_user.id,
            Activity.interaction_type == InteractionType.open_home_callback,
            Activity.date >= seven_days_ago,
        )
    )
    callback_person_ids = set(row[0] for row in callback_result.all())

    callbacks_needed: list[OpenHomeCallback] = []
    seen_callback_persons = set()
    for att in recent_attendances:
        if att.person_id not in callback_person_ids and att.person_id not in seen_callback_persons:
            seen_callback_persons.add(att.person_id)
            # Find person info
            person = next((p for p in all_people if p.id == att.person_id), None)
            if person:
                callbacks_needed.append(OpenHomeCallback(
                    person_id=person.id,
                    first_name=person.first_name,
                    last_name=person.last_name,
                    phone=person.phone,
                    property_id=att.property_id,
                    attendance_date=att.date,
                ))

    # ── 4. Repeat open home attendees ──
    repeat_result = await db.execute(
        select(
            Activity.person_id,
            func.count(Activity.id).label("cnt"),
        )
        .where(
            Activity.user_id == current_user.id,
            Activity.interaction_type == InteractionType.open_home_attendance,
        )
        .group_by(Activity.person_id)
        .having(func.count(Activity.id) > 1)
    )
    repeat_rows = repeat_result.all()

    repeat_attendees: list[RepeatAttendee] = []
    for row in repeat_rows:
        person_id, count = row[0], row[1]
        person = next((p for p in all_people if p.id == person_id), None)
        if person:
            # Get distinct property IDs visited
            props_result = await db.execute(
                select(Activity.property_id)
                .where(
                    Activity.person_id == person_id,
                    Activity.interaction_type == InteractionType.open_home_attendance,
                    Activity.property_id.isnot(None),
                )
                .distinct()
            )
            property_ids = [r[0] for r in props_result.all()]
            repeat_attendees.append(RepeatAttendee(
                person_id=person.id,
                first_name=person.first_name,
                last_name=person.last_name,
                phone=person.phone,
                attendance_count=count,
                properties_visited=property_ids,
            ))

    # ── 5. Cadence status for all people ──
    cadence_statuses: list[PersonCadenceStatus] = []
    for person in all_people:
        last_m = last_meaningful_map.get(person.id)
        cadence_st, days_since = compute_cadence_status(person.tier, last_m, now)
        cadence_statuses.append(PersonCadenceStatus(
            person_id=person.id,
            first_name=person.first_name,
            last_name=person.last_name,
            tier=person.tier.value,
            cadence_status=cadence_st.value,
            days_since_last_meaningful=days_since,
            cadence_window_days=get_cadence_window(person.tier),
        ))

    return DashboardResponse(
        a_tier_drifting=a_tier_drifting,
        due_for_contact_this_week=due_for_contact,
        open_home_callbacks_needed=callbacks_needed,
        repeat_open_home_attendees=repeat_attendees,
        cadence_statuses=cadence_statuses,
    )


# ── Dashboard Summary Alias (frontend compatibility) ─────────────────────────


@router.get("/dashboard/summary", response_model=DashboardResponse, tags=["Dashboard"])
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Alias for /dashboard — the frontend calls this path.
    Returns the same aggregated dashboard data.
    """
    return await get_dashboard(db=db, current_user=current_user)


# ── AI Suggestions (Stub) ─────────────────────────────────────────────────────


@router.get("/ai/suggestions", response_model=AISuggestionsResponse, tags=["AI Intelligence"])
async def get_ai_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI Intelligence Layer — stub endpoint returning mock suggestions.

    In production, this would analyse interaction patterns, email threads,
    and behavioural signals to surface actionable insights.
    """
    # Fetch a few people to make mock suggestions more realistic
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
