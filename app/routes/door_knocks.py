"""CRUD routes for door_knock_sessions."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, DoorKnockSession
from app.schemas.door_knock import DoorKnockCreate, DoorKnockResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/door-knocks", tags=["Door Knocks"])


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
    """Create a new door knock session."""
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
