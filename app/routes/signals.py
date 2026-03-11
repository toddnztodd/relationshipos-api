"""Opportunity Signals — detection, listing, and entity-scoped endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    BuyerInterest,
    BuyerInterestStage,
    CommunityEntity,
    Person,
    Property,
    Signal,
    SignalSourceType,
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

    # Also run the match engine to create/update buyer_match signals based on preference scoring
    from app.routes.match_engine import ACTIVE_STAGES, calculate_match_score
    THRESHOLD = 40.0
    bi_result = await db.execute(
        select(BuyerInterest).where(
            BuyerInterest.user_id == current_user.id,
            BuyerInterest.stage.in_(list(ACTIVE_STAGES)),
        )
    )
    buyer_interests = bi_result.scalars().all()
    props_result = await db.execute(select(Property).where(Property.user_id == current_user.id))
    properties = props_result.scalars().all()
    person_ids = list({bi.person_id for bi in buyer_interests if bi.person_id})
    person_map: dict = {}
    if person_ids:
        persons_result = await db.execute(select(Person).where(Person.id.in_(person_ids)))
        for p in persons_result.scalars().all():
            person_map[p.id] = f"{p.first_name} {p.last_name or ''}".strip()
    qualifying_pairs: dict = {}
    for bi in buyer_interests:
        for prop in properties:
            score_result = calculate_match_score(bi, prop)
            if score_result["score"] >= THRESHOLD:
                existing = qualifying_pairs.get(prop.id)
                if existing is None or score_result["score"] > existing["score"]:
                    qualifying_pairs[prop.id] = {
                        "score": score_result["score"],
                        "reasons": score_result["reasons"],
                        "buyer_name": person_map.get(bi.person_id, "Buyer") if bi.person_id else "Buyer",
                        "property_address": prop.address,
                        "person_id": bi.person_id,
                    }
    existing_sigs_result = await db.execute(
        select(Signal).where(
            Signal.user_id == current_user.id,
            Signal.signal_type == SignalType.buyer_match,
            Signal.is_active == True,
        )
    )
    existing_by_prop = {s.entity_id: s for s in existing_sigs_result.scalars().all()}
    me_created = 0
    for prop_id, match_data in qualifying_pairs.items():
        confidence = round(match_data["score"] / 100.0, 4)
        reasons_preview = ", ".join(match_data["reasons"][:2])
        description = (
            f"{match_data['buyer_name']} matches {match_data['property_address']}"
            + (f" — {reasons_preview}" if reasons_preview else "")
        )
        if prop_id in existing_by_prop:
            sig = existing_by_prop[prop_id]
            sig.confidence = confidence
            sig.description = description
            sig.source_contact_id = match_data["person_id"]
        else:
            sig = Signal(
                user_id=current_user.id,
                signal_type=SignalType.buyer_match,
                entity_type="property",
                entity_id=prop_id,
                confidence=confidence,
                source_contact_id=match_data["person_id"],
                source_type=SignalSourceType.system,
                description=description,
                is_active=True,
            )
            db.add(sig)
            me_created += 1
    for prop_id, sig in existing_by_prop.items():
        if prop_id not in qualifying_pairs:
            sig.is_active = False
    await db.flush()
    result["signals_created"] = result.get("signals_created", 0) + me_created
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
