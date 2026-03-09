"""Email Thread CRUD routes — linked to people."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User, Person, EmailThread
from app.schemas.email_thread import (
    EmailThreadCreate,
    EmailThreadUpdate,
    EmailThreadResponse,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/email-threads", tags=["Email Threads"])


@router.post("/", response_model=EmailThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_email_thread(
    payload: EmailThreadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new email thread linked to a person."""
    # Validate person exists and belongs to user
    result = await db.execute(
        select(Person).where(Person.id == payload.person_id, Person.user_id == current_user.id)
    )
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    # Enforce opt-in: person must be a relationship asset with email sync enabled
    if not person.is_relationship_asset or not person.email_sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email sync requires both is_relationship_asset and email_sync_enabled to be true",
        )

    thread = EmailThread(user_id=current_user.id, **payload.model_dump())
    db.add(thread)
    await db.flush()
    await db.refresh(thread)
    return thread


@router.get("/", response_model=list[EmailThreadResponse])
async def list_email_threads(
    person_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List email threads with optional person filter."""
    query = select(EmailThread).where(EmailThread.user_id == current_user.id)

    if person_id is not None:
        query = query.where(EmailThread.person_id == person_id)

    query = query.order_by(EmailThread.last_message_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{thread_id}", response_model=EmailThreadResponse)
async def get_email_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single email thread by ID."""
    result = await db.execute(
        select(EmailThread).where(EmailThread.id == thread_id, EmailThread.user_id == current_user.id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email thread not found")
    return thread


@router.put("/{thread_id}", response_model=EmailThreadResponse)
async def update_email_thread(
    thread_id: int,
    payload: EmailThreadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an email thread."""
    result = await db.execute(
        select(EmailThread).where(EmailThread.id == thread_id, EmailThread.user_id == current_user.id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email thread not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(thread, key, value)

    await db.flush()
    await db.refresh(thread)
    return thread


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_thread(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an email thread."""
    result = await db.execute(
        select(EmailThread).where(EmailThread.id == thread_id, EmailThread.user_id == current_user.id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email thread not found")

    await db.delete(thread)
    await db.flush()
