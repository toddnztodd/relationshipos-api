"""Opportunity Signals — detection, listing, and entity-scoped endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    CommunityEntity,
    Person,
    Property,
    Signal,
    SignalType,
)
from app.schemas.signal import (
    SignalDetectResponse,
    SignalListResponse,
    SignalResponse,
)
from app.services.auth import get_current_user
from app.services.signal_detection import run_signal_detection

# Main signals router
router = APIRouter(prefix="/signals", tags=["Signals"])

# Entity-scoped routers
property_router = APIRouter(prefix="/properties", tags=["Signals"])
person_router = APIRouter(prefix="/people", tags=["Signals"])


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _resolve_entity_name(db: AsyncSession, entity_type: str, entity_id: int) -> Optional[str]:
    """Resolve a human-readable name for a signal entity."""
    if entity_type == "person":
        result = await db.execute(select(Person).where(Person.id == entity_id))
        p = result.scalar_one_or_none()
        if p:
            return f"{p.first_name} {p.last_name or ''}".strip()
    elif entity_type == "property":
        result = await db.execute(select(Property).where(Property.id == entity_id))
        prop = result.scalar_one_or_none()
        if prop:
            return prop.address
    elif entity_type == "community":
        result = await db.execute(select(CommunityEntity).where(CommunityEntity.id == entity_id))
        ce = result.scalar_one_or_none()
        if ce:
            return ce.name
    return None


async def _build_response(db: AsyncSession, sig: Signal) -> SignalResponse:
    entity_name = await _resolve_entity_name(db, sig.entity_type, sig.entity_id)
    return SignalResponse(
        id=sig.id,
        signal_type=sig.signal_type.value,
        entity_type=sig.entity_type,
        entity_id=sig.entity_id,
        entity_name=entity_name,
        confidence=sig.confidence,
        source_contact_id=sig.source_contact_id,
        source_type=sig.source_type.value,
        description=sig.description,
        is_active=sig.is_active,
        created_at=sig.created_at,
        updated_at=sig.updated_at,
    )


# ── POST /signals/detect ────────────────────────────────────────────────────

@router.post("/detect", response_model=SignalDetectResponse)
async def detect_signals(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Run all signal detection rules across all entities.

    Creates new signals where conditions are met (skips duplicates).
    Deactivates signals where conditions no longer hold.
    """
    result = await run_signal_detection(db, current_user.id)
    return SignalDetectResponse(**result)


# ── GET /signals ─────────────────────────────────────────────────────────────

@router.get("", response_model=SignalListResponse)
async def list_signals(
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (person, property, community)"),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    active_only: bool = Query(True, description="Only return active signals"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all signals with optional filters."""
    query = select(Signal).where(Signal.user_id == current_user.id)

    if active_only:
        query = query.where(Signal.is_active == True)
    if signal_type:
        try:
            st = SignalType(signal_type)
            query = query.where(Signal.signal_type == st)
        except ValueError:
            pass
    if entity_type:
        query = query.where(Signal.entity_type == entity_type)
    if confidence_min is not None:
        query = query.where(Signal.confidence >= confidence_min)

    query = query.order_by(Signal.confidence.desc(), Signal.created_at.desc())

    result = await db.execute(query)
    signals = result.scalars().all()

    responses = []
    for sig in signals:
        responses.append(await _build_response(db, sig))

    return SignalListResponse(signals=responses, total=len(responses))


# ── GET /properties/{property_id}/signals ────────────────────────────────────

@property_router.get("/{property_id}/signals", response_model=SignalListResponse)
async def list_property_signals(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List active signals for a specific property."""
    result = await db.execute(
        select(Signal).where(
            Signal.user_id == current_user.id,
            Signal.entity_type == "property",
            Signal.entity_id == property_id,
            Signal.is_active == True,
        ).order_by(Signal.confidence.desc())
    )
    signals = result.scalars().all()
    responses = [await _build_response(db, sig) for sig in signals]
    return SignalListResponse(signals=responses, total=len(responses))


# ── GET /people/{person_id}/signals ──────────────────────────────────────────

@person_router.get("/{person_id}/signals", response_model=SignalListResponse)
async def list_person_signals(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List active signals for a specific person."""
    result = await db.execute(
        select(Signal).where(
            Signal.user_id == current_user.id,
            Signal.entity_type == "person",
            Signal.entity_id == person_id,
            Signal.is_active == True,
        ).order_by(Signal.confidence.desc())
    )
    signals = result.scalars().all()
    responses = [await _build_response(db, sig) for sig in signals]
    return SignalListResponse(signals=responses, total=len(responses))
