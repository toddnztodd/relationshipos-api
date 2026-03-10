"""Weekly BASICS tracking endpoints and user annual goals."""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, WeeklyTracking, DoorKnockSession
from app.schemas.weekly_tracking import (
    WeeklyTrackingUpsert,
    WeeklyTrackingResponse,
    WeeklySummaryResponse,
    WeeklySummaryTotals,
    UserGoalsUpdate,
    UserGoalsResponse,
)
from app.services.auth import get_current_user

router = APIRouter(tags=["Weekly Tracking"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _current_week_monday() -> date:
    """Return the Monday of the current ISO week (NZ calendar)."""
    today = date.today()
    return today - timedelta(days=today.weekday())  # weekday() 0=Mon


def _ensure_defaults(record: WeeklyTracking) -> None:
    """Ensure JSONB/int fields have sensible defaults after load."""
    if record.phone_calls_daily is None:
        record.phone_calls_daily = []
    for field in (
        "connects_count", "f2f_property_owners", "f2f_influencers",
        "calls_influencers", "new_contacts", "contacts_cleaned",
        "thank_you_cards", "letterbox_drops",
    ):
        if getattr(record, field) is None:
            setattr(record, field, 0)


# ── Weekly Tracking Endpoints ─────────────────────────────────────────────────


@router.get(
    "/weekly-tracking/current",
    response_model=WeeklyTrackingResponse,
    tags=["Weekly Tracking"],
)
async def get_current_week(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get or create the current week's tracking record for the authenticated user.

    'Current week' is defined as the ISO week starting on Monday (NZ calendar).
    If no record exists yet, an empty one is created and returned.
    """
    week_start = _current_week_monday()

    result = await db.execute(
        select(WeeklyTracking).where(
            WeeklyTracking.user_id == current_user.id,
            WeeklyTracking.week_start_date == week_start,
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        record = WeeklyTracking(
            user_id=current_user.id,
            week_start_date=week_start,
            phone_calls_daily=[],
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)

    _ensure_defaults(record)
    return record


@router.get(
    "/weekly-tracking/summary",
    response_model=WeeklySummaryResponse,
    tags=["Weekly Tracking"],
)
async def get_weekly_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get month-to-date and year-to-date totals for the authenticated user.

    Aggregates data from the weekly_tracking table and the door_knock_sessions
    table. Returns the current week's record alongside the aggregated totals.
    """
    now = datetime.now(timezone.utc)
    uid = current_user.id

    # Month-to-date: first day of current month
    month_start = date(now.year, now.month, 1)
    # Year-to-date: first day of current year
    year_start = date(now.year, 1, 1)

    async def _aggregate(from_date: date) -> WeeklySummaryTotals:
        result = await db.execute(
            select(
                func.sum(WeeklyTracking.connects_count),
                func.sum(WeeklyTracking.f2f_property_owners),
                func.sum(WeeklyTracking.f2f_influencers),
                func.sum(WeeklyTracking.calls_influencers),
                func.sum(WeeklyTracking.new_contacts),
                func.sum(WeeklyTracking.contacts_cleaned),
                func.sum(WeeklyTracking.thank_you_cards),
                func.sum(WeeklyTracking.letterbox_drops),
            ).where(
                WeeklyTracking.user_id == uid,
                WeeklyTracking.week_start_date >= from_date,
            )
        )
        row = result.one()

        # Phone calls: sum all daily values across weeks
        calls_result = await db.execute(
            select(WeeklyTracking.phone_calls_daily).where(
                WeeklyTracking.user_id == uid,
                WeeklyTracking.week_start_date >= from_date,
            )
        )
        total_calls = 0
        for (daily,) in calls_result.all():
            if daily:
                total_calls += sum(daily)

        # Door knocks from door_knock_sessions table
        dk_result = await db.execute(
            select(func.count(DoorKnockSession.id)).where(
                DoorKnockSession.user_id == uid,
                func.date(DoorKnockSession.created_at) >= from_date,
            )
        )
        dk_count = dk_result.scalar() or 0

        return WeeklySummaryTotals(
            phone_calls=total_calls,
            connects=int(row[0] or 0),
            f2f_property_owners=int(row[1] or 0),
            f2f_influencers=int(row[2] or 0),
            calls_influencers=int(row[3] or 0),
            new_contacts=int(row[4] or 0),
            contacts_cleaned=int(row[5] or 0),
            thank_you_cards=int(row[6] or 0),
            letterbox_drops=int(row[7] or 0),
            door_knocks=dk_count,
        )

    mtd = await _aggregate(month_start)
    ytd = await _aggregate(year_start)

    # Also fetch the current week record
    week_start = _current_week_monday()
    cw_result = await db.execute(
        select(WeeklyTracking).where(
            WeeklyTracking.user_id == uid,
            WeeklyTracking.week_start_date == week_start,
        )
    )
    current_week = cw_result.scalar_one_or_none()
    if current_week:
        _ensure_defaults(current_week)

    return WeeklySummaryResponse(
        month_to_date=mtd,
        year_to_date=ytd,
        current_week=WeeklyTrackingResponse.model_validate(current_week) if current_week else None,
    )


@router.get(
    "/weekly-tracking/{week_start_date}",
    response_model=WeeklyTrackingResponse,
    tags=["Weekly Tracking"],
)
async def get_week_by_date(
    week_start_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific week's tracking record by its Monday date."""
    result = await db.execute(
        select(WeeklyTracking).where(
            WeeklyTracking.user_id == current_user.id,
            WeeklyTracking.week_start_date == week_start_date,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tracking record found for week starting {week_start_date}",
        )
    _ensure_defaults(record)
    return record


@router.put(
    "/weekly-tracking/{week_start_date}",
    response_model=WeeklyTrackingResponse,
    tags=["Weekly Tracking"],
)
async def upsert_week(
    week_start_date: date,
    payload: WeeklyTrackingUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update a week's tracking record (upsert).

    Only fields included in the payload are updated; omitted fields are left
    unchanged. The week_start_date must be a Monday.
    """
    result = await db.execute(
        select(WeeklyTracking).where(
            WeeklyTracking.user_id == current_user.id,
            WeeklyTracking.week_start_date == week_start_date,
        )
    )
    record = result.scalar_one_or_none()

    if record is None:
        record = WeeklyTracking(
            user_id=current_user.id,
            week_start_date=week_start_date,
            phone_calls_daily=[],
        )
        db.add(record)

    # Apply only the fields that were explicitly set in the payload
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    record.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(record)
    _ensure_defaults(record)
    return record


# ── User Annual Goals ─────────────────────────────────────────────────────────


@router.put(
    "/users/goals",
    response_model=UserGoalsResponse,
    tags=["Weekly Tracking"],
)
async def update_user_goals(
    payload: UserGoalsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the annual goals for the authenticated user."""
    result = await db.execute(
        select(User).where(User.id == current_user.id)
    )
    user = result.scalar_one()

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return UserGoalsResponse(
        gc_goal_year=user.gc_goal_year,
        listings_target_year=user.listings_target_year,
        deals_target_year=user.deals_target_year,
    )


@router.get(
    "/users/goals",
    response_model=UserGoalsResponse,
    tags=["Weekly Tracking"],
)
async def get_user_goals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the annual goals for the authenticated user."""
    return UserGoalsResponse(
        gc_goal_year=current_user.gc_goal_year,
        listings_target_year=current_user.listings_target_year,
        deals_target_year=current_user.deals_target_year,
    )
