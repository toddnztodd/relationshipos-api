"""Important Dates routes — CRUD per person and cross-person upcoming lookup."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, PersonDate
from app.schemas.person_date import (
    PersonDateCreate,
    PersonDateUpdate,
    PersonDateResponse,
    UpcomingDateResponse,
)
from app.services.auth import get_current_user

# ── Two routers: one nested under /people/{person_id}, one at /dates ──────────

person_dates_router = APIRouter(
    prefix="/people/{person_id}/dates",
    tags=["Important Dates"],
)

dates_router = APIRouter(
    prefix="/dates",
    tags=["Important Dates"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_person_or_404(db: AsyncSession, person_id: int, user_id: int) -> Person:
    result = await db.execute(
        select(Person).where(Person.id == person_id, Person.user_id == user_id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


async def _get_date_or_404(db: AsyncSession, date_id: int, person_id: int) -> PersonDate:
    result = await db.execute(
        select(PersonDate).where(
            PersonDate.id == date_id,
            PersonDate.person_id == person_id,
        )
    )
    pd = result.scalar_one_or_none()
    if not pd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Date not found")
    return pd


def _next_occurrence(mmdd: str, today: date) -> tuple[date, int]:
    """
    Given a MM-DD string and today's date, return:
      - the next calendar date on which this anniversary falls
      - the number of days from today until that date (0 = today)

    Handles Feb 29 gracefully by falling back to Feb 28 in non-leap years.
    """
    month, day = int(mmdd[:2]), int(mmdd[3:])

    # Try this year first
    for year_offset in (0, 1):
        year = today.year + year_offset
        # Handle Feb 29 in non-leap years
        if month == 2 and day == 29:
            import calendar
            if not calendar.isleap(year):
                day = 28
        try:
            candidate = date(year, month, day)
        except ValueError:
            # Shouldn't happen after the Feb-29 guard, but be safe
            candidate = date(year, month, min(day, 28))

        if candidate >= today:
            return candidate, (candidate - today).days

    # Fallback (should never reach here)
    fallback = date(today.year + 1, month, day)
    return fallback, (fallback - today).days


# ── Per-person CRUD ───────────────────────────────────────────────────────────


@person_dates_router.post(
    "/",
    response_model=PersonDateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an important date for a person",
)
async def create_person_date(
    person_id: int,
    payload: PersonDateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new important date linked to a person."""
    await _get_person_or_404(db, person_id, current_user.id)

    # Exclude frontend-only fields that don't exist on the DB model
    db_fields = payload.model_dump(exclude={"is_recurring", "recurrence_type"})
    pd = PersonDate(person_id=person_id, **db_fields)
    db.add(pd)
    await db.flush()
    await db.refresh(pd)
    return pd


@person_dates_router.get(
    "/",
    response_model=list[PersonDateResponse],
    summary="List all important dates for a person",
)
async def list_person_dates(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all important dates for the specified person, ordered by MM-DD."""
    await _get_person_or_404(db, person_id, current_user.id)

    result = await db.execute(
        select(PersonDate)
        .where(PersonDate.person_id == person_id)
        .order_by(PersonDate.date.asc())
    )
    return result.scalars().all()


@person_dates_router.put(
    "/{date_id}/",
    response_model=PersonDateResponse,
    summary="Update an important date",
)
async def update_person_date(
    person_id: int,
    date_id: int,
    payload: PersonDateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing important date."""
    await _get_person_or_404(db, person_id, current_user.id)
    pd = await _get_date_or_404(db, date_id, person_id)

    for key, value in payload.model_dump(exclude_unset=True, exclude={"is_recurring", "recurrence_type"}).items():
        setattr(pd, key, value)

    await db.flush()
    await db.refresh(pd)
    return pd


@person_dates_router.delete(
    "/{date_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an important date",
)
async def delete_person_date(
    person_id: int,
    date_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an important date."""
    await _get_person_or_404(db, person_id, current_user.id)
    pd = await _get_date_or_404(db, date_id, person_id)

    await db.delete(pd)
    await db.flush()


# ── Cross-person upcoming dates ───────────────────────────────────────────────


@dates_router.get(
    "/upcoming/",
    response_model=list[UpcomingDateResponse],
    summary="Dates falling within the next N days across all people",
)
async def get_upcoming_dates(
    days: int = Query(
        default=14,
        ge=1,
        le=365,
        description="Number of days ahead to look (inclusive of today)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all important dates across all people where the annual recurrence
    falls within the next `days` days (inclusive of today).

    Results are sorted by days_until ascending so the most imminent dates
    appear first. Includes person name, phone, and the exact next-occurrence
    calendar date for display purposes.
    """
    today = datetime.now(timezone.utc).date()

    # Fetch all PersonDates for this user via a join to people
    result = await db.execute(
        select(PersonDate, Person)
        .join(Person, PersonDate.person_id == Person.id)
        .where(Person.user_id == current_user.id)
    )
    rows = result.all()

    upcoming: list[UpcomingDateResponse] = []

    for pd, person in rows:
        next_date, days_until = _next_occurrence(pd.date, today)

        if days_until <= days:
            upcoming.append(
                UpcomingDateResponse(
                    id=pd.id,
                    person_id=person.id,
                    person_first_name=person.first_name,
                    person_last_name=person.last_name,
                    person_phone=person.phone,
                    label=pd.label,
                    date=pd.date,
                    year=pd.year,
                    reminder_days_before=pd.reminder_days_before,
                    notes=pd.notes,
                    days_until=days_until,
                    next_occurrence=next_date.isoformat(),
                    created_at=pd.created_at,
                )
            )

    # Sort by soonest first
    upcoming.sort(key=lambda x: x.days_until)
    return upcoming
