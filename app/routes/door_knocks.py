"""CRUD routes for door_knock_sessions."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, DoorKnockSession, Property
from app.schemas.door_knock import DoorKnockCreate, DoorKnockResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/door-knocks", tags=["Door Knocks"])

WEEKLY_GOAL = 10  # hardcoded weekly door knock goal


def _get_week_start(today: date) -> date:
    """Return the Monday of the current week (NZ calendar week: Mon–Sun)."""
    return today - timedelta(days=today.weekday())


class WeeklySummary(BaseModel):
    count: int
    goal: int
    week_start: date


# ── Weekly summary (must be before /{id} to avoid routing conflict) ──────────


@router.get("/weekly-summary", response_model=WeeklySummary, tags=["Door Knocks"])
async def get_weekly_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return this week's door knock count and goal for the authenticated user.
    Week runs Monday–Sunday (NZ calendar week).
    """
    today = datetime.now(timezone.utc).date()
    week_start = _get_week_start(today)
    week_start_dt = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)

    result = await db.execute(
        select(func.count(DoorKnockSession.id)).where(
            DoorKnockSession.user_id == current_user.id,
            DoorKnockSession.created_at >= week_start_dt,
        )
    )
    count = result.scalar() or 0

    return WeeklySummary(count=count, goal=WEEKLY_GOAL, week_start=week_start)


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.get("/", response_model=list[DoorKnockResponse])
async def list_door_knocks(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all door knock sessions for the authenticated user."""
    result = await db.execute(
        select(DoorKnockSession)
        .where(DoorKnockSession.user_id == current_user.id)
        .order_by(DoorKnockSession.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/", response_model=DoorKnockResponse, status_code=status.HTTP_201_CREATED)
async def create_door_knock(
    payload: DoorKnockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new door knock session.

    If the address doesn't already exist as a property for this user, a new
    property record is automatically created so the address is tracked.
    """
    # Auto-create property if it doesn't already exist for this user + address
    existing_prop = await db.execute(
        select(Property).where(
            Property.user_id == current_user.id,
            Property.address == payload.address,
        )
    )
    if not existing_prop.scalar_one_or_none():
        new_prop = Property(
            user_id=current_user.id,
            address=payload.address,
        )
        db.add(new_prop)
        await db.flush()  # assign ID without committing

    # Create the door knock session
    dk = DoorKnockSession(
        user_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(dk)
    await db.flush()
    await db.refresh(dk)
    return dk


@router.get("/{door_knock_id}", response_model=DoorKnockResponse)
async def get_door_knock(
    door_knock_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific door knock session."""
    result = await db.execute(
        select(DoorKnockSession).where(
            DoorKnockSession.id == door_knock_id,
            DoorKnockSession.user_id == current_user.id,
        )
    )
    dk = result.scalar_one_or_none()
    if not dk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Door knock session not found")
    return dk


@router.delete("/{door_knock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_door_knock(
    door_knock_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a door knock session."""
    result = await db.execute(
        select(DoorKnockSession).where(
            DoorKnockSession.id == door_knock_id,
            DoorKnockSession.user_id == current_user.id,
        )
    )
    dk = result.scalar_one_or_none()
    if not dk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Door knock session not found")

    await db.delete(dk)
    await db.flush()
