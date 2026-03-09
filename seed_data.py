"""
Seed data script for RelationshipOS.

Creates sample users, people, properties, activities, and email threads
for testing and development purposes.

Usage:
    python seed_data.py
"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.database import engine, async_session_factory, Base
from app.models.models import (
    User,
    Person,
    Property,
    Activity,
    EmailThread,
    InteractionType,
    TierEnum,
)
from app.services.auth import hash_password


async def seed():
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)

        # ── Users ──────────────────────────────────────────────────────────
        user = User(
            email="todd@eves.co.nz",
            password_hash=hash_password("password123"),
            full_name="Todd Hilleard",
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        print(f"✓ Created user: {user.email} (id={user.id})")

        demo_user = User(
            email="demo@relationshipos.app",
            password_hash=hash_password("demo1234"),
            full_name="Demo User",
        )
        session.add(demo_user)
        await session.flush()
        await session.refresh(demo_user)
        print(f"✓ Created user: {demo_user.email} (id={demo_user.id})")

        # ── Properties ─────────────────────────────────────────────────────
        properties_data = [
            {
                "address": "42 Marine Parade, Papamoa Beach",
                "suburb": "Papamoa",
                "bedrooms": 4,
                "bathrooms": 2,
                "has_pool": True,
                "renovation_status": "recently renovated",
                "years_owned": 3.5,
                "council_valuation": 1250000.0,
            },
            {
                "address": "18 Domain Road, Papamoa",
                "suburb": "Papamoa",
                "bedrooms": 3,
                "bathrooms": 1,
                "has_pool": False,
                "renovation_status": "original condition",
                "years_owned": 12.0,
                "council_valuation": 850000.0,
            },
            {
                "address": "7 Oceanview Terrace, Mount Maunganui",
                "suburb": "Mount Maunganui",
                "bedrooms": 5,
                "bathrooms": 3,
                "has_pool": True,
                "renovation_status": "partial renovation",
                "years_owned": 1.0,
                "council_valuation": 1800000.0,
            },
            {
                "address": "103 Gravatt Road, Papamoa",
                "suburb": "Papamoa",
                "bedrooms": 3,
                "bathrooms": 2,
                "has_pool": False,
                "renovation_status": "needs work",
                "years_owned": 8.0,
                "council_valuation": 720000.0,
            },
            {
                "address": "55 Girven Road, Mount Maunganui",
                "suburb": "Mount Maunganui",
                "bedrooms": 4,
                "bathrooms": 2,
                "has_pool": False,
                "renovation_status": "recently renovated",
                "years_owned": 2.0,
                "council_valuation": 1450000.0,
            },
        ]

        props = []
        for pd in properties_data:
            p = Property(user_id=user.id, **pd)
            session.add(p)
            props.append(p)
        await session.flush()
        for p in props:
            await session.refresh(p)
        print(f"✓ Created {len(props)} properties")

        # ── People ─────────────────────────────────────────────────────────
        people_data = [
            # A-tier people
            {
                "first_name": "Sarah",
                "last_name": "Mitchell",
                "phone": "+64211234567",
                "email": "sarah.mitchell@gmail.com",
                "suburb": "Papamoa",
                "relationship_type": "buyer",
                "influence_score": 9.2,
                "tier": TierEnum.A,
                "lead_source": "referral",
                "buyer_readiness_status": "actively looking",
                "notes": "Looking for 4-bed in Papamoa. Budget $1.2M. Pre-approved.",
                "is_relationship_asset": True,
                "email_sync_enabled": True,
            },
            {
                "first_name": "James",
                "last_name": "Wong",
                "phone": "+64212345678",
                "email": "james.wong@outlook.co.nz",
                "suburb": "Mount Maunganui",
                "relationship_type": "investor",
                "influence_score": 8.5,
                "tier": TierEnum.A,
                "lead_source": "networking event",
                "buyer_readiness_status": "evaluating",
                "notes": "Owns 3 investment properties. Interested in Mount area.",
                "is_relationship_asset": True,
                "email_sync_enabled": True,
            },
            {
                "first_name": "Lisa",
                "last_name": "Patel",
                "phone": "+64213456789",
                "email": "lisa.patel@xtra.co.nz",
                "suburb": "Papamoa Beach",
                "relationship_type": "seller",
                "influence_score": 8.8,
                "tier": TierEnum.A,
                "lead_source": "door knock",
                "buyer_readiness_status": None,
                "notes": "Considering selling family home. Wants market appraisal.",
                "is_relationship_asset": True,
                "email_sync_enabled": False,
            },
            # B-tier people
            {
                "first_name": "Mark",
                "last_name": "Thompson",
                "phone": "+64214567890",
                "email": "mark.t@gmail.com",
                "suburb": "Papamoa",
                "relationship_type": "buyer",
                "influence_score": 6.0,
                "tier": TierEnum.B,
                "lead_source": "open_home",
                "buyer_readiness_status": "early research",
                "notes": "First home buyer. Looking in 6-12 months.",
                "is_relationship_asset": False,
                "email_sync_enabled": False,
            },
            {
                "first_name": "Rachel",
                "last_name": "Green",
                "phone": "+64215678901",
                "email": "rachel.green@yahoo.co.nz",
                "suburb": "Te Puke",
                "relationship_type": "neighbour",
                "influence_score": 5.5,
                "tier": TierEnum.B,
                "lead_source": "community",
                "buyer_readiness_status": None,
                "notes": "Active in local community. Good referral source.",
                "is_relationship_asset": True,
                "email_sync_enabled": False,
            },
            {
                "first_name": "David",
                "last_name": "Chen",
                "phone": "+64216789012",
                "email": "david.chen@business.co.nz",
                "suburb": "Tauranga",
                "relationship_type": "investor",
                "influence_score": 7.0,
                "tier": TierEnum.B,
                "lead_source": "referral",
                "buyer_readiness_status": "evaluating",
                "notes": "Commercial property investor considering residential.",
                "is_relationship_asset": True,
                "email_sync_enabled": True,
            },
            # C-tier people
            {
                "first_name": "Emma",
                "last_name": "Wilson",
                "phone": "+64217890123",
                "email": "emma.w@gmail.com",
                "suburb": "Papamoa",
                "relationship_type": "buyer",
                "influence_score": 3.0,
                "tier": TierEnum.C,
                "lead_source": "open_home",
                "buyer_readiness_status": "browsing",
                "notes": "Attended one open home. Casual interest.",
                "is_relationship_asset": False,
                "email_sync_enabled": False,
            },
            {
                "first_name": "Tom",
                "last_name": "Harris",
                "phone": "+64218901234",
                "email": None,
                "suburb": "Bethlehem",
                "relationship_type": "vendor",
                "influence_score": 4.0,
                "tier": TierEnum.C,
                "lead_source": "cold call",
                "buyer_readiness_status": None,
                "notes": "Spoke briefly. May consider selling next year.",
                "is_relationship_asset": False,
                "email_sync_enabled": False,
            },
            {
                "first_name": "Aroha",
                "last_name": "Tane",
                "phone": "+64219012345",
                "email": "aroha.tane@gmail.com",
                "suburb": "Papamoa",
                "relationship_type": "colleague",
                "influence_score": 5.0,
                "tier": TierEnum.C,
                "lead_source": "office",
                "buyer_readiness_status": None,
                "notes": "Fellow agent at EVES. Good for referrals.",
                "is_relationship_asset": False,
                "email_sync_enabled": False,
            },
            {
                "first_name": "Mike",
                "last_name": "Brown",
                "phone": "+64210123456",
                "email": "mike.brown@hotmail.com",
                "suburb": "Mount Maunganui",
                "relationship_type": "buyer",
                "influence_score": 2.5,
                "tier": TierEnum.C,
                "lead_source": "open_home",
                "buyer_readiness_status": "browsing",
                "notes": "Attended two open homes in Mount area.",
                "is_relationship_asset": False,
                "email_sync_enabled": False,
            },
        ]

        persons = []
        for pd in people_data:
            p = Person(user_id=user.id, **pd)
            session.add(p)
            persons.append(p)
        await session.flush()
        for p in persons:
            await session.refresh(p)
        print(f"✓ Created {len(persons)} people")

        # ── Activities ─────────────────────────────────────────────────────
        # Create a mix of activities at various dates to test cadence logic
        activities_data = [
            # Sarah Mitchell — recent meaningful contact (green)
            {
                "person_id": persons[0].id,
                "property_id": props[0].id,
                "interaction_type": InteractionType.open_home_attendance,
                "date": now - timedelta(days=5),
                "notes": "Attended 42 Marine Parade open home. Very interested.",
                "is_meaningful": True,
            },
            {
                "person_id": persons[0].id,
                "interaction_type": InteractionType.phone_call,
                "date": now - timedelta(days=3),
                "notes": "Follow-up call. Wants second viewing.",
                "is_meaningful": True,
            },
            # James Wong — approaching deadline (amber, ~25 days ago)
            {
                "person_id": persons[1].id,
                "interaction_type": InteractionType.coffee_meeting,
                "date": now - timedelta(days=25),
                "notes": "Coffee at Mount. Discussed investment strategy.",
                "is_meaningful": True,
            },
            # Lisa Patel — drifting (red, 45 days ago for A-tier)
            {
                "person_id": persons[2].id,
                "interaction_type": InteractionType.door_knock,
                "date": now - timedelta(days=45),
                "notes": "Door knock. Discussed market conditions.",
                "is_meaningful": True,
            },
            {
                "person_id": persons[2].id,
                "interaction_type": InteractionType.text_message,
                "date": now - timedelta(days=40),
                "notes": "Sent market update text.",
                "is_meaningful": False,  # Not meaningful
            },
            # Mark Thompson — B-tier, recent
            {
                "person_id": persons[3].id,
                "property_id": props[1].id,
                "interaction_type": InteractionType.open_home_attendance,
                "date": now - timedelta(days=10),
                "notes": "First open home visit.",
                "is_meaningful": True,
            },
            # Rachel Green — B-tier, approaching deadline (~55 days)
            {
                "person_id": persons[4].id,
                "interaction_type": InteractionType.phone_call,
                "date": now - timedelta(days=55),
                "notes": "Catch-up call about community events.",
                "is_meaningful": True,
            },
            # David Chen — B-tier, drifting (70 days)
            {
                "person_id": persons[5].id,
                "interaction_type": InteractionType.email_conversation,
                "date": now - timedelta(days=70),
                "notes": "Email about residential investment opportunities.",
                "is_meaningful": True,
            },
            # Emma Wilson — C-tier, open home attendance (recent, needs callback)
            {
                "person_id": persons[6].id,
                "property_id": props[0].id,
                "interaction_type": InteractionType.open_home_attendance,
                "date": now - timedelta(days=2),
                "notes": "Attended 42 Marine Parade open home.",
                "is_meaningful": True,
            },
            # Mike Brown — repeat open home attendee
            {
                "person_id": persons[9].id,
                "property_id": props[2].id,
                "interaction_type": InteractionType.open_home_attendance,
                "date": now - timedelta(days=14),
                "notes": "First visit to Oceanview Terrace.",
                "is_meaningful": True,
            },
            {
                "person_id": persons[9].id,
                "property_id": props[4].id,
                "interaction_type": InteractionType.open_home_attendance,
                "date": now - timedelta(days=7),
                "notes": "Second open home — Girven Road.",
                "is_meaningful": True,
            },
            {
                "person_id": persons[9].id,
                "property_id": props[2].id,
                "interaction_type": InteractionType.open_home_attendance,
                "date": now - timedelta(days=3),
                "notes": "Returned to Oceanview Terrace for second look.",
                "is_meaningful": True,
            },
            # Sarah Mitchell — also a repeat attendee
            {
                "person_id": persons[0].id,
                "property_id": props[2].id,
                "interaction_type": InteractionType.open_home_attendance,
                "date": now - timedelta(days=12),
                "notes": "Also visited Oceanview Terrace.",
                "is_meaningful": True,
            },
            # Open home callback already done for Mark Thompson
            {
                "person_id": persons[3].id,
                "interaction_type": InteractionType.open_home_callback,
                "date": now - timedelta(days=8),
                "notes": "Called back after open home. Good conversation.",
                "is_meaningful": True,
            },
            # Tom Harris — no meaningful interactions (will be red)
            # Aroha Tane — one old interaction
            {
                "person_id": persons[8].id,
                "interaction_type": InteractionType.coffee_meeting,
                "date": now - timedelta(days=100),
                "notes": "Office coffee catch-up.",
                "is_meaningful": True,
            },
        ]

        acts = []
        for ad in activities_data:
            a = Activity(user_id=user.id, **ad)
            session.add(a)
            acts.append(a)
        await session.flush()
        print(f"✓ Created {len(acts)} activities")

        # ── Email Threads ──────────────────────────────────────────────────
        email_threads_data = [
            {
                "person_id": persons[0].id,  # Sarah Mitchell
                "subject_line": "Re: 42 Marine Parade — Second Viewing",
                "first_message_date": now - timedelta(days=5),
                "last_message_date": now - timedelta(days=2),
                "message_count": 4,
                "thread_body": (
                    "Hi Todd,\n\nThanks for showing us through 42 Marine Parade. "
                    "We'd love to arrange a second viewing this weekend if possible.\n\n"
                    "Cheers,\nSarah\n\n---\n\n"
                    "Hi Sarah,\n\nAbsolutely! How does Saturday at 10am work?\n\n"
                    "Best,\nTodd"
                ),
            },
            {
                "person_id": persons[1].id,  # James Wong
                "subject_line": "Investment Property Opportunities — Mount Maunganui",
                "first_message_date": now - timedelta(days=30),
                "last_message_date": now - timedelta(days=25),
                "message_count": 6,
                "thread_body": (
                    "Hi Todd,\n\nFollowing up on our coffee meeting. "
                    "Could you send through the yield analysis for the Mount properties?\n\n"
                    "Regards,\nJames\n\n---\n\n"
                    "Hi James,\n\nAttached is the analysis. The Girven Road property "
                    "shows the strongest yield at 5.2%.\n\nCheers,\nTodd"
                ),
            },
            {
                "person_id": persons[5].id,  # David Chen
                "subject_line": "Residential vs Commercial — Your Thoughts",
                "first_message_date": now - timedelta(days=75),
                "last_message_date": now - timedelta(days=70),
                "message_count": 3,
                "thread_body": (
                    "Todd,\n\nI've been thinking about diversifying into residential. "
                    "What's the market like in Tauranga right now?\n\n"
                    "David\n\n---\n\n"
                    "David,\n\nGreat timing. The residential market here is showing "
                    "strong fundamentals. Let's catch up over coffee.\n\nTodd"
                ),
            },
        ]

        for etd in email_threads_data:
            et = EmailThread(user_id=user.id, **etd)
            session.add(et)
        await session.flush()
        print(f"✓ Created {len(email_threads_data)} email threads")

        await session.commit()
        print("\n✅ Seed data loaded successfully!")
        print("\n── Test Credentials ──")
        print(f"  Primary:  todd@eves.co.nz / password123")
        print(f"  Demo:     demo@relationshipos.app / demo1234")
        print("\n── Expected Dashboard State ──")
        print(f"  A-tier drifting: Lisa Patel (45 days since last meaningful)")
        print(f"  Due for contact: James Wong (~5 days until A-tier deadline)")
        print(f"  Due for contact: Rachel Green (~5 days until B-tier deadline)")
        print(f"  Callbacks needed: Emma Wilson, Mike Brown (attended, no callback)")
        print(f"  Repeat attendees: Mike Brown (3 visits), Sarah Mitchell (2 visits)")


if __name__ == "__main__":
    asyncio.run(seed())
