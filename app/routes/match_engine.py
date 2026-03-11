"""Buyer-Property Match Engine.

Provides:
  GET  /api/v1/buyers/{buyer_interest_id}/matches   — top properties for a buyer
  GET  /api/v1/properties/{property_id}/buyer-matches — top buyers for a property
  POST /api/v1/match-engine/run                     — run engine, create/deactivate signals
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import (
    BuyerInterest,
    BuyerInterestStage,
    ListingResultType,
    Person,
    Property,
    Signal,
    SignalSourceType,
    SignalType,
)
from app.services.auth import get_current_user

router = APIRouter(tags=["Match Engine"])

# ── Scoring weights ────────────────────────────────────────────────────────────

WEIGHT_SUBURB = 25
WEIGHT_BEDROOMS = 20
WEIGHT_PRICE = 20
WEIGHT_BATHROOMS = 10
WEIGHT_LAND_SIZE = 10
WEIGHT_PROPERTY_TYPE = 10
WEIGHT_SPECIAL_FEATURES = 5  # per feature, up to 10 total
WEIGHT_SELLABILITY_BOOST = 5  # bonus when sellability >= 4

ACTIVE_STAGES = {
    BuyerInterestStage.interested,
    BuyerInterestStage.hot,
    BuyerInterestStage.offer,
}


# ── Core scoring function ──────────────────────────────────────────────────────

def calculate_match_score(bi: BuyerInterest, prop: Property) -> Dict[str, Any]:
    """Return {'score': float, 'reasons': list[str]} for a buyer–property pair."""
    score = 0.0
    reasons: List[str] = []

    # 1. Suburb match (25 pts)
    if bi.preferred_suburbs and prop.suburb:
        if prop.suburb.lower() in [s.lower() for s in bi.preferred_suburbs]:
            score += WEIGHT_SUBURB
            reasons.append(f"Suburb match: {prop.suburb}")

    # 2. Bedroom match (20 pts)
    if bi.bedrooms_min is not None and prop.bedrooms is not None:
        if prop.bedrooms >= bi.bedrooms_min:
            score += WEIGHT_BEDROOMS
            reasons.append(f"Bedrooms: {prop.bedrooms} (min {bi.bedrooms_min})")

    # 3. Price range match (20 pts)
    prop_value: Optional[float] = None
    if prop.estimated_value is not None:
        try:
            prop_value = float(prop.estimated_value)
        except (TypeError, ValueError):
            pass
    elif prop.cv:
        # Try to parse cv like "1.12M" or "850,000"
        try:
            cv_str = prop.cv.upper().replace(",", "").strip()
            if cv_str.endswith("M"):
                prop_value = float(cv_str[:-1]) * 1_000_000
            elif cv_str.endswith("K"):
                prop_value = float(cv_str[:-1]) * 1_000
            else:
                prop_value = float(cv_str)
        except (TypeError, ValueError):
            pass

    if prop_value is not None:
        in_range = True
        if bi.price_min is not None and prop_value < bi.price_min:
            in_range = False
        if bi.price_max is not None and prop_value > bi.price_max:
            in_range = False
        if (bi.price_min is not None or bi.price_max is not None) and in_range:
            score += WEIGHT_PRICE
            lo = f"${bi.price_min:,.0f}" if bi.price_min else "any"
            hi = f"${bi.price_max:,.0f}" if bi.price_max else "any"
            reasons.append(f"Price in range ({lo}–{hi}): ${prop_value:,.0f}")

    # 4. Bathroom match (10 pts)
    if bi.bathrooms_min is not None and prop.bathrooms is not None:
        if prop.bathrooms >= bi.bathrooms_min:
            score += WEIGHT_BATHROOMS
            reasons.append(f"Bathrooms: {prop.bathrooms} (min {bi.bathrooms_min})")

    # 5. Land size match (10 pts)
    if bi.land_size_min is not None and prop.land_size:
        try:
            ls_str = prop.land_size.lower().replace("sqm", "").replace(",", "").strip()
            ls_val = float(ls_str)
            if ls_val >= bi.land_size_min:
                score += WEIGHT_LAND_SIZE
                reasons.append(f"Land size: {prop.land_size} (min {bi.land_size_min} sqm)")
        except (TypeError, ValueError):
            pass

    # 6. Property type match (10 pts)
    if bi.property_type_preference and prop.property_type:
        if bi.property_type_preference.lower() == prop.property_type.lower():
            score += WEIGHT_PROPERTY_TYPE
            reasons.append(f"Property type: {prop.property_type}")

    # 7. Special features (5 pts each, max 10)
    if bi.special_features:
        prop_text = " ".join(filter(None, [
            prop.address or "",
            prop.suburb or "",
            str(prop.has_pool) if prop.has_pool else "",
            prop.garaging or "",
            prop.renovation_status or "",
        ])).lower()
        feature_hits = 0
        for feature in bi.special_features:
            if feature.lower() in prop_text:
                feature_pts = min(WEIGHT_SPECIAL_FEATURES, 10 - feature_hits * WEIGHT_SPECIAL_FEATURES)
                if feature_pts > 0:
                    score += feature_pts
                    reasons.append(f"Feature match: {feature}")
                    feature_hits += 1

    # 8. Sellability boost (5 pts)
    if prop.sellability is not None and prop.sellability >= 4:
        score += WEIGHT_SELLABILITY_BOOST
        reasons.append(f"High sellability: {prop.sellability}/5")

    return {"score": min(round(score, 1), 100.0), "reasons": reasons}


# ── Pydantic response models ───────────────────────────────────────────────────

class MatchResult(BaseModel):
    buyer_interest_id: int
    property_id: int
    person_id: Optional[int] = None
    person_name: Optional[str] = None
    property_address: str
    stage: str
    score: float
    reasons: List[str]


class RunEngineResponse(BaseModel):
    signals_created: int
    signals_deactivated: int
    matches_evaluated: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/buyers/{buyer_interest_id}/matches", response_model=List[MatchResult])
async def get_buyer_matches(
    buyer_interest_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return top matching properties for a specific buyer interest record."""
    bi_result = await db.execute(
        select(BuyerInterest).where(
            BuyerInterest.id == buyer_interest_id,
            BuyerInterest.user_id == current_user.id,
        )
    )
    bi = bi_result.scalar_one_or_none()
    if not bi:
        raise HTTPException(status_code=404, detail="Buyer interest not found")

    # Load all user properties
    props_result = await db.execute(
        select(Property).where(Property.user_id == current_user.id)
    )
    properties = props_result.scalars().all()

    # Score each property
    scored = []
    for prop in properties:
        result = calculate_match_score(bi, prop)
        if result["score"] > 0:
            scored.append({
                "buyer_interest_id": bi.id,
                "property_id": prop.id,
                "person_id": bi.person_id,
                "person_name": None,
                "property_address": prop.address,
                "stage": bi.stage.value,
                "score": result["score"],
                "reasons": result["reasons"],
            })

    # Load person name
    if bi.person_id:
        person_result = await db.execute(
            select(Person).where(Person.id == bi.person_id)
        )
        person = person_result.scalar_one_or_none()
        if person:
            pname = f"{person.first_name} {person.last_name or ''}".strip()
            for s in scored:
                s["person_name"] = pname

    scored.sort(key=lambda x: x["score"], reverse=True)
    return [MatchResult(**s) for s in scored[:10]]


@router.get("/properties/{property_id}/buyer-matches", response_model=List[MatchResult])
async def get_property_buyer_matches(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return top matching buyers for a specific property."""
    prop_result = await db.execute(
        select(Property).where(
            Property.id == property_id,
            Property.user_id == current_user.id,
        )
    )
    prop = prop_result.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    # Load active buyer interests (interested, hot, offer — not purchased)
    bi_result = await db.execute(
        select(BuyerInterest).where(
            BuyerInterest.user_id == current_user.id,
            BuyerInterest.stage.in_(list(ACTIVE_STAGES)),
        )
    )
    buyer_interests = bi_result.scalars().all()

    # Load person names in bulk
    person_ids = list({bi.person_id for bi in buyer_interests if bi.person_id})
    person_map: Dict[int, str] = {}
    if person_ids:
        persons_result = await db.execute(
            select(Person).where(Person.id.in_(person_ids))
        )
        for p in persons_result.scalars().all():
            person_map[p.id] = f"{p.first_name} {p.last_name or ''}".strip()

    scored = []
    for bi in buyer_interests:
        result = calculate_match_score(bi, prop)
        if result["score"] > 0:
            scored.append(MatchResult(
                buyer_interest_id=bi.id,
                property_id=prop.id,
                person_id=bi.person_id,
                person_name=person_map.get(bi.person_id) if bi.person_id else None,
                property_address=prop.address,
                stage=bi.stage.value,
                score=result["score"],
                reasons=result["reasons"],
            ))

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:10]


@router.post("/match-engine/run", response_model=RunEngineResponse)
async def run_match_engine(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Run the match engine across all active buyers and properties.

    Creates buyer_match signals for pairs scoring >= 40.
    Deactivates stale buyer_match signals that no longer meet the threshold.
    """
    THRESHOLD = 40.0

    # Load all active buyer interests
    bi_result = await db.execute(
        select(BuyerInterest).where(
            BuyerInterest.user_id == current_user.id,
            BuyerInterest.stage.in_(list(ACTIVE_STAGES)),
        )
    )
    buyer_interests = bi_result.scalars().all()

    # Load all user properties
    props_result = await db.execute(
        select(Property).where(Property.user_id == current_user.id)
    )
    properties = props_result.scalars().all()

    # Load person names
    person_ids = list({bi.person_id for bi in buyer_interests if bi.person_id})
    person_map: Dict[int, str] = {}
    if person_ids:
        persons_result = await db.execute(
            select(Person).where(Person.id.in_(person_ids))
        )
        for p in persons_result.scalars().all():
            person_map[p.id] = f"{p.first_name} {p.last_name or ''}".strip()

    # Evaluate all pairs
    qualifying_pairs: Dict[int, Dict] = {}  # keyed by property_id
    matches_evaluated = 0

    for bi in buyer_interests:
        for prop in properties:
            matches_evaluated += 1
            result = calculate_match_score(bi, prop)
            if result["score"] >= THRESHOLD:
                # Keep the highest-scoring buyer per property
                existing = qualifying_pairs.get(prop.id)
                if existing is None or result["score"] > existing["score"]:
                    buyer_name = person_map.get(bi.person_id, "Buyer") if bi.person_id else "Buyer"
                    qualifying_pairs[prop.id] = {
                        "score": result["score"],
                        "reasons": result["reasons"],
                        "buyer_name": buyer_name,
                        "property_address": prop.address,
                        "person_id": bi.person_id,
                        "property_id": prop.id,
                    }

    # Load existing active buyer_match signals for this user
    existing_signals_result = await db.execute(
        select(Signal).where(
            Signal.user_id == current_user.id,
            Signal.signal_type == SignalType.buyer_match,
            Signal.is_active == True,
        )
    )
    existing_signals = existing_signals_result.scalars().all()
    existing_by_property: Dict[int, Signal] = {s.entity_id: s for s in existing_signals}

    signals_created = 0
    signals_deactivated = 0

    # Create or update qualifying signals
    qualifying_property_ids = set(qualifying_pairs.keys())
    for prop_id, match_data in qualifying_pairs.items():
        confidence = round(match_data["score"] / 100.0, 4)
        reasons_preview = ", ".join(match_data["reasons"][:2])
        description = (
            f"{match_data['buyer_name']} matches {match_data['property_address']}"
            + (f" — {reasons_preview}" if reasons_preview else "")
        )

        if prop_id in existing_by_property:
            # Update existing signal
            sig = existing_by_property[prop_id]
            sig.confidence = confidence
            sig.description = description
            sig.source_contact_id = match_data["person_id"]
        else:
            # Create new signal
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
            signals_created += 1

    # Deactivate stale signals (property no longer qualifies)
    for prop_id, sig in existing_by_property.items():
        if prop_id not in qualifying_property_ids:
            sig.is_active = False
            signals_deactivated += 1

    await db.flush()

    return RunEngineResponse(
        signals_created=signals_created,
        signals_deactivated=signals_deactivated,
        matches_evaluated=matches_evaluated,
    )
