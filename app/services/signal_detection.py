"""Signal Detection Engine — detects opportunity signals across entities.

Implements 6 signal types:
1. listing_opportunity  — high sellability + withdrawn/expired + owner linked
2. buyer_match          — interested+ buyer + matching property in network
3. vendor_pressure      — keywords in recent activities (voice notes, emails, meetings)
4. relationship_cooling — tier A/B/C contact overdue on cadence
5. relationship_warming — recent meaningful interaction or new context node
6. community_cluster    — 2+ homeowners in same community entity + buyer demand
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Activity,
    BuyerInterest,
    BuyerInterestStage,
    CommunityEntity,
    CommunityEntityPerson,
    CommunityEntityProperty,
    ListingResultType,
    Person,
    PersonContextNode,
    Property,
    PropertyOwner,
    Signal,
    SignalSourceType,
    SignalType,
    TierEnum,
)

logger = logging.getLogger(__name__)

# ── Cadence windows (days) per tier ──────────────────────────────────────────

CADENCE_WINDOWS = {
    TierEnum.A: 14,
    TierEnum.B: 30,
    TierEnum.C: 60,
}

# ── Vendor pressure keywords ────────────────────────────────────────────────

VENDOR_PRESSURE_KEYWORDS = [
    "considering offers",
    "price change",
    "price reduction",
    "urgent",
    "need to sell",
    "must sell",
    "motivated seller",
    "downsizing",
    "relocating",
    "divorce",
    "settlement",
    "mortgagee",
    "deceased estate",
    "quick sale",
    "open to offers",
    "will accept",
    "drop the price",
    "reduced",
    "keen to move",
]


async def _upsert_signal(
    db: AsyncSession,
    user_id: int,
    signal_type: SignalType,
    entity_type: str,
    entity_id: int,
    confidence: float,
    description: str,
    source_type: SignalSourceType = SignalSourceType.system,
    source_contact_id: Optional[int] = None,
) -> bool:
    """Create a signal if no active duplicate exists. Returns True if created."""
    existing = await db.execute(
        select(Signal).where(
            Signal.user_id == user_id,
            Signal.signal_type == signal_type,
            Signal.entity_type == entity_type,
            Signal.entity_id == entity_id,
            Signal.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        return False

    sig = Signal(
        user_id=user_id,
        signal_type=signal_type,
        entity_type=entity_type,
        entity_id=entity_id,
        confidence=min(confidence, 1.0),
        description=description,
        source_type=source_type,
        source_contact_id=source_contact_id,
    )
    db.add(sig)
    return True


# ── 1. Listing Opportunity ──────────────────────────────────────────────────

async def detect_listing_opportunities(db: AsyncSession, user_id: int) -> int:
    """Detect listing opportunities from property intelligence data.

    Triggers when:
    - sellability >= 4
    - last_listing_result = withdrawn OR expired
    - owner linked to contact
    """
    created = 0

    result = await db.execute(
        select(Property).where(Property.user_id == user_id)
    )
    properties = result.scalars().all()

    for prop in properties:
        confidence = 0.0
        reasons = []

        # Sellability score
        if prop.sellability and prop.sellability >= 4:
            confidence += 0.5 if prop.sellability == 4 else 0.7
            reasons.append(f"Sellability {prop.sellability}/5")

        # Listing history
        if prop.last_listing_result in (ListingResultType.withdrawn, ListingResultType.expired):
            confidence += 0.15
            reasons.append(f"Previous listing {prop.last_listing_result.value}")

        # Owner linked
        owner_result = await db.execute(
            select(PropertyOwner).where(
                PropertyOwner.property_id == prop.id,
                PropertyOwner.user_id == user_id,
            )
        )
        if owner_result.scalar_one_or_none():
            confidence += 0.05
            reasons.append("Owner linked")

        # Buyer demand on this property
        bi_result = await db.execute(
            select(BuyerInterest).where(
                BuyerInterest.property_id == prop.id,
                BuyerInterest.user_id == user_id,
                BuyerInterest.stage.in_([BuyerInterestStage.hot, BuyerInterestStage.offer]),
            )
        )
        if bi_result.scalars().first():
            confidence += 0.2
            reasons.append("Active buyer demand (hot/offer)")

        if confidence >= 0.4:
            desc = f"Listing opportunity at {prop.address}. {'; '.join(reasons)}."
            if await _upsert_signal(db, user_id, SignalType.listing_opportunity, "property", prop.id, confidence, desc):
                created += 1

    return created


# ── 2. Buyer Match ──────────────────────────────────────────────────────────

async def detect_buyer_matches(db: AsyncSession, user_id: int) -> int:
    """Detect buyer match signals.

    Triggers when buyer_interest.stage >= interested and property is in network.
    """
    created = 0

    result = await db.execute(
        select(BuyerInterest).where(
            BuyerInterest.user_id == user_id,
            BuyerInterest.stage.in_([
                BuyerInterestStage.interested,
                BuyerInterestStage.hot,
                BuyerInterestStage.offer,
            ]),
        )
    )
    interests = result.scalars().all()

    for bi in interests:
        confidence = 0.0
        reasons = []

        if bi.stage == BuyerInterestStage.offer:
            confidence += 0.7
            reasons.append("Buyer at offer stage")
        elif bi.stage == BuyerInterestStage.hot:
            confidence += 0.5
            reasons.append("Buyer is hot")
        else:
            confidence += 0.3
            reasons.append("Buyer is interested")

        # Check if property has sellability
        prop_result = await db.execute(
            select(Property).where(Property.id == bi.property_id)
        )
        prop = prop_result.scalar_one_or_none()
        if prop and prop.sellability and prop.sellability >= 3:
            confidence += 0.15
            reasons.append(f"Property sellability {prop.sellability}/5")

        person_result = await db.execute(
            select(Person).where(Person.id == bi.person_id, Person.contact_status == "active")
        )
        person = person_result.scalar_one_or_none()
        person_name = f"{person.first_name} {person.last_name or ''}".strip() if person else "Unknown"
        prop_addr = prop.address if prop else "Unknown"

        desc = f"Buyer match: {person_name} interested in {prop_addr}. {'; '.join(reasons)}."
        if await _upsert_signal(db, user_id, SignalType.buyer_match, "property", bi.property_id, confidence, desc,
                                source_contact_id=bi.person_id):
            created += 1

    return created


# ── 3. Vendor Pressure ──────────────────────────────────────────────────────

async def detect_vendor_pressure(db: AsyncSession, user_id: int) -> int:
    """Detect vendor pressure from recent activity notes.

    Scans voice_note, email_conversation, meeting_note activities from last 30 days.
    """
    created = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    result = await db.execute(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= cutoff,
            Activity.notes.isnot(None),
        )
    )
    activities = result.scalars().all()

    for act in activities:
        if not act.notes:
            continue
        notes_lower = act.notes.lower()
        matched_keywords = [kw for kw in VENDOR_PRESSURE_KEYWORDS if kw in notes_lower]

        if not matched_keywords:
            continue

        # Need a linked person and property
        if not act.person_id:
            continue

        # Check if person owns a property
        owner_result = await db.execute(
            select(PropertyOwner).where(
                PropertyOwner.person_id == act.person_id,
                PropertyOwner.user_id == user_id,
            )
        )
        owner = owner_result.scalar_one_or_none()
        if not owner:
            continue

        confidence = min(0.4 + 0.1 * len(matched_keywords), 0.9)
        person_result = await db.execute(select(Person).where(Person.id == act.person_id, Person.contact_status == "active"))
        person = person_result.scalar_one_or_none()
        if not person:
            continue
        person_name = f"{person.first_name} {person.last_name or ''}".strip() if person else "Unknown"

        # Determine source type
        source_type = SignalSourceType.system
        if act.type and act.type.value in ("voice_note",):
            source_type = SignalSourceType.voice_note
        elif act.type and act.type.value in ("email_conversation",):
            source_type = SignalSourceType.email
        elif act.type and act.type.value in ("meeting_note", "coffee_meeting"):
            source_type = SignalSourceType.meeting

        desc = f"Vendor pressure detected for {person_name}: {', '.join(matched_keywords[:3])}."
        if await _upsert_signal(db, user_id, SignalType.vendor_pressure, "person", act.person_id, confidence, desc,
                                source_type=source_type, source_contact_id=act.person_id):
            created += 1

    return created


# ── 4. Relationship Cooling ─────────────────────────────────────────────────

async def detect_relationship_cooling(db: AsyncSession, user_id: int) -> int:
    """Detect contacts who are overdue on their cadence window."""
    created = 0
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Person).where(
            Person.user_id == user_id,
            Person.tier.in_([TierEnum.A, TierEnum.B, TierEnum.C]),
            Person.contact_status == "active",
        )
    )
    people = result.scalars().all()

    # Batch fetch last meaningful interaction
    person_ids = [p.id for p in people]
    last_activity_result = await db.execute(
        select(
            Activity.person_id,
            func.max(Activity.date).label("last_date"),
        )
        .where(
            Activity.user_id == user_id,
            Activity.is_meaningful == True,
            Activity.person_id.in_(person_ids),
        )
        .group_by(Activity.person_id)
    )
    last_activity_map = {row[0]: row[1] for row in last_activity_result.all()}

    for person in people:
        window = CADENCE_WINDOWS.get(person.tier, 60)
        last_date = last_activity_map.get(person.id)

        if last_date is None:
            days_since = 999
        else:
            if hasattr(last_date, 'tzinfo') and last_date.tzinfo is None:
                last_date = last_date.replace(tzinfo=timezone.utc)
            days_since = (now - last_date).days

        if days_since <= window:
            continue

        # Overdue — calculate confidence based on how overdue
        overdue_ratio = min((days_since - window) / window, 1.0)
        confidence = 0.4 + 0.5 * overdue_ratio  # 0.4 to 0.9

        name = f"{person.first_name} {person.last_name or ''}".strip()
        desc = f"Relationship cooling: {name} (Tier {person.tier.value}) — {days_since} days since last contact (window: {window} days)."
        if await _upsert_signal(db, user_id, SignalType.relationship_cooling, "person", person.id, confidence, desc):
            created += 1

    return created


# ── 5. Relationship Warming ─────────────────────────────────────────────────

async def detect_relationship_warming(db: AsyncSession, user_id: int) -> int:
    """Detect contacts with recent positive engagement.

    Triggers when recent voice note, meeting, or new context node added (last 7 days).
    """
    created = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    # Recent meaningful activities
    result = await db.execute(
        select(Activity.person_id, func.count(Activity.id).label("cnt"))
        .where(
            Activity.user_id == user_id,
            Activity.date >= cutoff,
            Activity.is_meaningful == True,
            Activity.person_id.isnot(None),
        )
        .group_by(Activity.person_id)
    )
    warm_contacts = {row[0]: row[1] for row in result.all()}

    # Recent context nodes
    cn_result = await db.execute(
        select(PersonContextNode.person_id, func.count(PersonContextNode.id).label("cnt"))
        .where(
            PersonContextNode.person_id.isnot(None),
        )
        .group_by(PersonContextNode.person_id)
    )
    cn_map = {row[0]: row[1] for row in cn_result.all()}

    all_person_ids = set(warm_contacts.keys()) | set(cn_map.keys())
    if not all_person_ids:
        return 0

    person_result = await db.execute(
        select(Person).where(
            Person.user_id == user_id,
            Person.id.in_(all_person_ids),
            Person.contact_status == "active",
        )
    )
    people = {p.id: p for p in person_result.scalars().all()}

    for pid in all_person_ids:
        person = people.get(pid)
        if not person:
            continue

        activity_count = warm_contacts.get(pid, 0)
        cn_count = cn_map.get(pid, 0)

        if activity_count == 0 and cn_count == 0:
            continue

        confidence = min(0.3 + 0.15 * activity_count + 0.1 * cn_count, 0.9)
        reasons = []
        if activity_count:
            reasons.append(f"{activity_count} recent interaction(s)")
        if cn_count:
            reasons.append(f"{cn_count} context node(s)")

        name = f"{person.first_name} {person.last_name or ''}".strip()
        desc = f"Relationship warming: {name} — {'; '.join(reasons)}."
        if await _upsert_signal(db, user_id, SignalType.relationship_warming, "person", pid, confidence, desc):
            created += 1

    return created


# ── 6. Community Cluster ────────────────────────────────────────────────────

async def detect_community_clusters(db: AsyncSession, user_id: int) -> int:
    """Detect community clusters with 2+ homeowners and buyer demand.

    Triggers when a community entity has 2+ linked property owners and
    buyer interest exists in the same area.
    """
    created = 0

    # Get all community entities for this user
    ce_result = await db.execute(
        select(CommunityEntity).where(CommunityEntity.user_id == user_id)
    )
    entities = ce_result.scalars().all()

    for ce in entities:
        # Count linked property owners through community entity people
        people_result = await db.execute(
            select(CommunityEntityPerson.person_id).where(
                CommunityEntityPerson.community_entity_id == ce.id,
            )
        )
        ce_person_ids = [r[0] for r in people_result.all()]

        if len(ce_person_ids) < 2:
            continue

        # Check how many of these people are property owners
        owner_count_result = await db.execute(
            select(func.count(PropertyOwner.id)).where(
                PropertyOwner.person_id.in_(ce_person_ids),
                PropertyOwner.user_id == user_id,
            )
        )
        owner_count = owner_count_result.scalar() or 0

        if owner_count < 2:
            continue

        # Check for buyer demand in properties linked to this community
        prop_result = await db.execute(
            select(CommunityEntityProperty.property_id).where(
                CommunityEntityProperty.community_entity_id == ce.id,
            )
        )
        ce_prop_ids = [r[0] for r in prop_result.all()]

        buyer_demand = False
        if ce_prop_ids:
            bi_result = await db.execute(
                select(func.count(BuyerInterest.id)).where(
                    BuyerInterest.property_id.in_(ce_prop_ids),
                    BuyerInterest.user_id == user_id,
                    BuyerInterest.stage.in_([
                        BuyerInterestStage.interested,
                        BuyerInterestStage.hot,
                        BuyerInterestStage.offer,
                    ]),
                )
            )
            buyer_demand = (bi_result.scalar() or 0) > 0

        confidence = 0.4 + 0.1 * min(owner_count, 5)
        if buyer_demand:
            confidence += 0.2
        confidence = min(confidence, 1.0)

        reasons = [f"{owner_count} homeowners linked"]
        if buyer_demand:
            reasons.append("buyer demand in cluster")

        desc = f"Community cluster: {ce.name} — {'; '.join(reasons)}."
        if await _upsert_signal(db, user_id, SignalType.community_cluster, "community", ce.id, confidence, desc):
            created += 1

    return created


# ── Expiry / Deactivation ───────────────────────────────────────────────────

async def deactivate_stale_signals(db: AsyncSession, user_id: int) -> int:
    """Deactivate signals where conditions no longer hold."""
    deactivated = 0
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Signal).where(
            Signal.user_id == user_id,
            Signal.is_active == True,
        )
    )
    active_signals = result.scalars().all()

    for sig in active_signals:
        should_deactivate = False

        if sig.signal_type == SignalType.buyer_match:
            # Deactivate if buyer purchased
            bi_result = await db.execute(
                select(BuyerInterest).where(
                    BuyerInterest.property_id == sig.entity_id,
                    BuyerInterest.user_id == user_id,
                    BuyerInterest.stage == BuyerInterestStage.purchased,
                )
            )
            if bi_result.scalar_one_or_none():
                should_deactivate = True

        elif sig.signal_type == SignalType.relationship_cooling:
            # Deactivate if recent contact made
            cutoff = now - timedelta(days=7)
            act_result = await db.execute(
                select(Activity).where(
                    Activity.user_id == user_id,
                    Activity.person_id == sig.entity_id,
                    Activity.is_meaningful == True,
                    Activity.date >= cutoff,
                )
            )
            if act_result.scalars().first():
                should_deactivate = True

        elif sig.signal_type == SignalType.listing_opportunity:
            # Deactivate if property sold
            prop_result = await db.execute(
                select(Property).where(Property.id == sig.entity_id)
            )
            prop = prop_result.scalar_one_or_none()
            if prop and prop.last_listing_result == ListingResultType.sold:
                should_deactivate = True

        if should_deactivate:
            sig.is_active = False
            deactivated += 1

    return deactivated


# ── Main detection runner ───────────────────────────────────────────────────

async def run_signal_detection(db: AsyncSession, user_id: int) -> dict:
    """Run all signal detection rules and return summary."""
    # First deactivate stale signals
    deactivated = await deactivate_stale_signals(db, user_id)

    # Then detect new signals
    created = 0
    created += await detect_listing_opportunities(db, user_id)
    created += await detect_buyer_matches(db, user_id)
    created += await detect_vendor_pressure(db, user_id)
    created += await detect_relationship_cooling(db, user_id)
    created += await detect_relationship_warming(db, user_id)
    created += await detect_community_clusters(db, user_id)

    # Count total active
    count_result = await db.execute(
        select(func.count(Signal.id)).where(
            Signal.user_id == user_id,
            Signal.is_active == True,
        )
    )
    total_active = count_result.scalar() or 0

    return {
        "signals_created": created,
        "signals_deactivated": deactivated,
        "total_active": total_active,
    }
