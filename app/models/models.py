"""SQLAlchemy ORM models for RelationshipOS."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


# ── Enums ──────────────────────────────────────────────────────────────────────


class InteractionType(str, enum.Enum):
    open_home_attendance = "open_home_attendance"
    open_home_callback = "open_home_callback"
    phone_call = "phone_call"
    text_message = "text_message"
    door_knock = "door_knock"
    coffee_meeting = "coffee_meeting"
    email_conversation = "email_conversation"
    # New activity types for voice capture and structured notes
    voice_note = "voice_note"
    meeting_note = "meeting_note"
    appraisal_note = "appraisal_note"
    conversation_update = "conversation_update"
    system_event = "system_event"
    vault = "vault"
    restore = "restore"


class TierEnum(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class CadenceStatus(str, enum.Enum):
    green = "green"
    amber = "amber"
    red = "red"


class AnchorStatus(str, enum.Enum):
    suggested = "suggested"
    accepted = "accepted"
    dismissed = "dismissed"


class SummaryStatus(str, enum.Enum):
    suggested = "suggested"
    accepted = "accepted"
    dismissed = "dismissed"


class SignalType(str, enum.Enum):
    listing_opportunity = "listing_opportunity"
    buyer_match = "buyer_match"
    vendor_pressure = "vendor_pressure"
    relationship_cooling = "relationship_cooling"
    relationship_warming = "relationship_warming"
    community_cluster = "community_cluster"


class SignalSourceType(str, enum.Enum):
    voice_note = "voice_note"
    email = "email"
    meeting = "meeting"
    system = "system"


class ListingResultType(str, enum.Enum):
    sold = "sold"
    withdrawn = "withdrawn"
    expired = "expired"
    private_sale = "private_sale"
    unknown = "unknown"


class BuyerInterestStage(str, enum.Enum):
    seen = "seen"
    interested = "interested"
    hot = "hot"
    offer = "offer"
    purchased = "purchased"


# ── Models ─────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Annual goals
    gc_goal_year = Column(Float, nullable=True)           # GC target for the year
    listings_target_year = Column(Integer, nullable=True)  # Listings target for the year
    deals_target_year = Column(Integer, nullable=True)     # Deals target for the year

    # Relationships
    people = relationship("Person", back_populates="user", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    email_threads = relationship("EmailThread", back_populates="user", cascade="all, delete-orphan")
    person_properties = relationship("PersonProperty", back_populates="user", cascade="all, delete-orphan")
    door_knock_sessions = relationship("DoorKnockSession", back_populates="user", cascade="all, delete-orphan")
    weekly_tracking = relationship("WeeklyTracking", back_populates="user", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("user_id", "phone", name="uq_user_phone"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=True, default="")
    phone = Column(String(50), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    suburb = Column(String(255), nullable=True)
    relationship_type = Column(String(100), nullable=True)
    relationship_types = Column(JSON, nullable=True, default=list)  # multi-select array
    influence_score = Column(Float, nullable=True, default=0.0)
    tier = Column(Enum(TierEnum), nullable=False, default=TierEnum.C)
    lead_source = Column(String(255), nullable=True)
    buyer_readiness_status = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    is_relationship_asset = Column(Boolean, default=False)
    email_sync_enabled = Column(Boolean, default=False)
    # New AML / licence fields
    drivers_licence_number = Column(String(100), nullable=True)
    drivers_licence_expiry = Column(Date, nullable=True)
    drivers_licence_verified = Column(Boolean, default=False)
    drivers_licence_verified_date = Column(Date, nullable=True)
    aml_status = Column(String(50), nullable=False, default="not_started")
    perceived_value = Column(String(255), nullable=True)
    buyer_interest = Column(Integer, nullable=True)
    seller_likelihood = Column(Integer, nullable=True)
    nickname = Column(String(255), nullable=True)
    relationship_group_id = Column(Integer, nullable=True, index=True)  # shared household/group identifier
    preferred_contact_channel = Column(String(20), nullable=True)  # text | whatsapp | messenger | email | call
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)
    last_interaction_channel = Column(String(50), nullable=True)  # call, text, whatsapp, email, messenger, linkedin
    # Contact Vault fields
    contact_status = Column(String(20), nullable=False, default="active")  # active | vaulted | private
    vault_note = Column(Text, nullable=True)
    vaulted_at = Column(DateTime(timezone=True), nullable=True)
    original_source = Column(String(100), nullable=True)
    # Referral programme fields
    referral_member = Column(Boolean, default=False, nullable=False)
    referral_reward_amount = Column(Numeric(10, 2), default=250, nullable=False)
    referral_email_sent_at = Column(DateTime(timezone=True), nullable=True)
    # Additional contact fields
    phone_numbers = Column(JSON, nullable=True, default=list)  # array of {label, number} objects
    date_of_birth = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="people")
    activities = relationship("Activity", back_populates="person", cascade="all, delete-orphan")
    email_threads = relationship("EmailThread", back_populates="person", cascade="all, delete-orphan")
    important_dates = relationship("PersonDate", back_populates="person", cascade="all, delete-orphan")
    important_dates_v2 = relationship("PersonImportantDate", back_populates="person", cascade="all, delete-orphan")
    property_links = relationship("PropertyPerson", back_populates="person", cascade="all, delete-orphan")
    person_properties = relationship("PersonProperty", back_populates="person", cascade="all, delete-orphan")
    rapport_anchors = relationship("RapportAnchor", back_populates="person", cascade="all, delete-orphan")
    relationship_summaries = relationship("RelationshipSummary", back_populates="person", cascade="all, delete-orphan")
    suggested_outreach = relationship("SuggestedOutreach", back_populates="person", cascade="all, delete-orphan")
    context_node_links = relationship("PersonContextNode", back_populates="person", cascade="all, delete-orphan")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    address = Column(String(500), nullable=False)
    suburb = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    has_pool = Column(Boolean, default=False)
    renovation_status = Column(String(255), nullable=True)
    years_owned = Column(Float, nullable=True)
    council_valuation = Column(Float, nullable=True)
    # New property fields
    garaging = Column(String(255), nullable=True)
    section_size_sqm = Column(Float, nullable=True)
    house_size_sqm = Column(Float, nullable=True)
    land_value = Column(String(255), nullable=True)
    perceived_value = Column(String(255), nullable=True)
    appraisal_stage = Column(String(100), nullable=True)
    appraisal_status = Column(String(100), nullable=True)  # booked | completed | converted_to_listing | lost
    toilets = Column(Integer, nullable=True)
    ensuites = Column(Integer, nullable=True)
    living_rooms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="properties")
    activities = relationship("Activity", back_populates="property", cascade="all, delete-orphan")
    person_links = relationship("PropertyPerson", back_populates="property", cascade="all, delete-orphan")
    checklist_items = relationship("ListingChecklistItem", back_populates="property", cascade="all, delete-orphan")
    context_node_links = relationship("PropertyContextNode", back_populates="property", cascade="all, delete-orphan")

    # Property Intelligence fields
    land_size = Column(Text, nullable=True)
    cv = Column(Text, nullable=True)
    last_sold_amount = Column(Text, nullable=True)
    last_sold_date = Column(Date, nullable=True)
    current_listing_price = Column(Text, nullable=True)
    listing_url = Column(Text, nullable=True)
    listing_agent = Column(Text, nullable=True)
    listing_agency = Column(Text, nullable=True)
    last_listed_date = Column(Date, nullable=True)
    last_listing_result = Column(Enum(ListingResultType, name="listing_result_type"), nullable=True)
    sellability = Column(Integer, nullable=True)
    # Match engine fields
    estimated_value = Column(Numeric, nullable=True)
    property_type = Column(String(100), nullable=True)

    # New relationships
    buyer_interests = relationship("BuyerInterest", back_populates="property", cascade="all, delete-orphan")
    owner_links = relationship("PropertyOwner", back_populates="property", cascade="all, delete-orphan")


class ActivityPerson(Base):
    """Join table linking activities to multiple people."""
    __tablename__ = "activity_people"
    __table_args__ = (
        UniqueConstraint("activity_id", "person_id", name="uq_activity_person"),
    )

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    activity = relationship("Activity", back_populates="activity_people")
    person = relationship("Person", lazy="selectin")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True, index=True)
    interaction_type = Column(Enum(InteractionType), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notes = Column(Text, nullable=True)
    is_meaningful = Column(Boolean, default=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    feedback = Column(Text, nullable=True)
    price_indication = Column(String(255), nullable=True)
    scheduled_date = Column(Date, nullable=True)
    scheduled_time = Column(Time, nullable=True)
    source = Column(String(100), nullable=True)  # conversation_update, manual, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="activities")
    person = relationship("Person", back_populates="activities")
    property = relationship("Property", back_populates="activities")
    activity_people = relationship("ActivityPerson", back_populates="activity", cascade="all, delete-orphan", lazy="selectin")


class EmailThread(Base):
    __tablename__ = "email_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_line = Column(String(500), nullable=False)
    first_message_date = Column(DateTime(timezone=True), nullable=False)
    last_message_date = Column(DateTime(timezone=True), nullable=False)
    message_count = Column(Integer, default=1)
    thread_body = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="email_threads")
    person = relationship("Person", back_populates="email_threads")


class PersonDate(Base):
    """Important dates associated with a person (birthdays, anniversaries, custom) — v1 MM-DD format."""
    __tablename__ = "person_dates"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(255), nullable=False)
    date = Column(String(5), nullable=False, doc="Month and day stored as MM-DD")
    year = Column(Integer, nullable=True)
    reminder_days_before = Column(Integer, nullable=False, default=7)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    person = relationship("Person", back_populates="important_dates")


# ── NEW TABLES ─────────────────────────────────────────────────────────────────


class PersonRelationship(Base):
    """Tracks relationships between two people (e.g. Spouse, Sibling, Referred By)."""
    __tablename__ = "person_relationships"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_a_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    person_b_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(255), nullable=False)
    custom_label = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    person_a = relationship("Person", foreign_keys=[person_a_id])
    person_b = relationship("Person", foreign_keys=[person_b_id])


class PropertyPerson(Base):
    """Links a person to a property with a role (Vendor, Buyer Enquiry, etc.)."""
    __tablename__ = "property_people"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(255), nullable=False)
    custom_label = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    property = relationship("Property", back_populates="person_links")
    person = relationship("Person", back_populates="property_links")


class PersonImportantDate(Base):
    """Important dates v2 — stores full date, supports recurring flag."""
    __tablename__ = "person_important_dates"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(255), nullable=False)
    date = Column(Date, nullable=False)
    is_recurring = Column(Boolean, default=True)
    reminder_days_before = Column(Integer, nullable=False, default=7)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    person = relationship("Person", back_populates="important_dates_v2")


class ListingChecklistItem(Base):
    """Checklist items for a property listing workflow."""
    __tablename__ = "listing_checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    phase = Column(String(255), nullable=False)
    step_name = Column(String(500), nullable=False)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    sale_method = Column(String(100), nullable=True)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    property = relationship("Property", back_populates="checklist_items")


class ListingChecklist(Base):
    """Structured 12-phase listing checklist for a property."""
    __tablename__ = "listing_checklists"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sale_method = Column(String(20), nullable=False)
    current_phase = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    property = relationship("Property", foreign_keys=[property_id])
    phases = relationship("ChecklistPhase", back_populates="checklist", cascade="all, delete-orphan", lazy="selectin", order_by="ChecklistPhase.phase_number")
    items = relationship("ChecklistItem", back_populates="checklist", cascade="all, delete-orphan", lazy="selectin", order_by="ChecklistItem.sort_order")


class ChecklistPhase(Base):
    """A phase within a listing checklist."""
    __tablename__ = "checklist_phases"

    id = Column(Integer, primary_key=True, index=True)
    checklist_id = Column(Integer, ForeignKey("listing_checklists.id", ondelete="CASCADE"), nullable=False, index=True)
    phase_number = Column(Integer, nullable=False)
    phase_name = Column(String(100), nullable=False)
    is_complete = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("checklist_id", "phase_number", name="uq_checklist_phase"),)

    # Relationships
    checklist = relationship("ListingChecklist", back_populates="phases")


class ChecklistItem(Base):
    """An individual item within a listing checklist phase."""
    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    checklist_id = Column(Integer, ForeignKey("listing_checklists.id", ondelete="CASCADE"), nullable=False, index=True)
    phase_number = Column(Integer, nullable=False)
    item_text = Column(String(500), nullable=False)
    is_complete = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    checklist = relationship("ListingChecklist", back_populates="items")


class PersonProperty(Base):
    """Properties linked to a person (e.g. properties they've viewed, are interested in, own)."""
    __tablename__ = "person_properties"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    address = Column(Text, nullable=False)
    relationship_type = Column(Text, nullable=False, default="Viewed")
    notes = Column(Text, nullable=True)
    interest_level = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    person = relationship("Person", back_populates="person_properties")
    user = relationship("User", back_populates="person_properties")


class DoorKnockSession(Base):
    """Door knock session (V2) — covers a territory or area."""
    __tablename__ = "door_knock_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    territory_id = Column(Integer, ForeignKey("territories.id", ondelete="SET NULL"), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    total_knocks = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Relationships
    user = relationship("User", back_populates="door_knock_sessions")
    territory = relationship("Territory", foreign_keys=[territory_id])
    entries = relationship("DoorKnockEntry", back_populates="session", cascade="all, delete-orphan", lazy="selectin")


class WeeklyTracking(Base):
    """Weekly BASICS activity tracking record — one row per user per week."""
    __tablename__ = "weekly_tracking"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start_date = Column(Date, nullable=False)  # always the Monday of that week
    phone_calls_daily = Column(JSON, default=list)  # array of 7 ints [Mon, Tue, Wed, Thu, Fri, Sat, Sun]
    connects_count = Column(Integer, default=0)
    f2f_property_owners = Column(Integer, default=0)
    f2f_influencers = Column(Integer, default=0)
    calls_influencers = Column(Integer, default=0)
    new_contacts = Column(Integer, default=0)
    contacts_cleaned = Column(Integer, default=0)
    thank_you_cards = Column(Integer, default=0)
    letterbox_drops = Column(Integer, default=0)
    review_exercise = Column(Integer, nullable=True)    # 1-10 self-review
    review_diet = Column(Integer, nullable=True)
    review_energy = Column(Integer, nullable=True)
    review_enthusiasm = Column(Integer, nullable=True)
    review_work_life = Column(Integer, nullable=True)
    review_overall = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "week_start_date", name="uq_weekly_tracking_user_week"),)

    # Relationships
    user = relationship("User", back_populates="weekly_tracking")


class RapportAnchor(Base):
    """Rapport anchors extracted from voice notes — stored as suggestions on contact profiles."""
    __tablename__ = "rapport_anchors"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    relationship_group_id = Column(Integer, nullable=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    anchor_text = Column(Text, nullable=False)
    anchor_type = Column(String(20), nullable=False, default="individual")  # individual | household
    status = Column(Enum(AnchorStatus, name="anchor_status"), nullable=False, default=AnchorStatus.suggested)

    # Relationships
    person = relationship("Person", foreign_keys=[person_id], back_populates="rapport_anchors")
    activity = relationship("Activity", foreign_keys=[activity_id])
    user = relationship("User", foreign_keys=[user_id])


class RelationshipSummary(Base):
    """AI-generated relationship summaries for contacts."""
    __tablename__ = "relationship_summaries"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    status = Column(Enum(SummaryStatus, name="summary_status"), nullable=False, default=SummaryStatus.suggested)
    is_update = Column(Boolean, default=False)

    # Relationships
    person = relationship("Person", foreign_keys=[person_id], back_populates="relationship_summaries")
    user = relationship("User", foreign_keys=[user_id])


class SuggestedOutreach(Base):
    """AI-generated suggested outreach messages for contacts."""
    __tablename__ = "suggested_outreach"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    is_current = Column(Boolean, default=True)

    # Relationships
    person = relationship("Person", foreign_keys=[person_id], back_populates="suggested_outreach")
    user = relationship("User", foreign_keys=[user_id])

class ContextNodeType(str, enum.Enum):
    community = "community"
    school = "school"
    sport = "sport"
    location = "location"
    interest = "interest"
    network = "network"
    other = "other"


class ContextSuggestionStatus(str, enum.Enum):
    suggested = "suggested"
    accepted = "accepted"
    dismissed = "dismissed"


class ContextNode(Base):
    """A shared context node (community, school, sport, etc.)."""
    __tablename__ = "context_nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    type = Column(Enum(ContextNodeType, name="context_node_type"), nullable=False, default=ContextNodeType.other)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    person_links = relationship("PersonContextNode", back_populates="context_node", cascade="all, delete-orphan")
    property_links = relationship("PropertyContextNode", back_populates="context_node", cascade="all, delete-orphan")


class PersonContextNode(Base):
    """Links a person to a context node."""
    __tablename__ = "person_context_nodes"

    id = Column(Integer, primary_key=True, index=True)
    context_node_id = Column(Integer, ForeignKey("context_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("context_node_id", "person_id", name="uq_pcn_node_person"),)

    # Relationships
    context_node = relationship("ContextNode", back_populates="person_links")
    person = relationship("Person", back_populates="context_node_links")


class PropertyContextNode(Base):
    """Links a property to a context node."""
    __tablename__ = "property_context_nodes"

    id = Column(Integer, primary_key=True, index=True)
    context_node_id = Column(Integer, ForeignKey("context_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("context_node_id", "property_id", name="uq_propcn_node_property"),)

    # Relationships
    context_node = relationship("ContextNode", back_populates="property_links")
    property = relationship("Property", back_populates="context_node_links")


class RelationshipGroupContextNode(Base):
    """Links a relationship group to a context node."""
    __tablename__ = "relationship_group_context_nodes"

    id = Column(Integer, primary_key=True, index=True)
    context_node_id = Column(Integer, ForeignKey("context_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_group_id = Column(Integer, nullable=False, index=True)

    __table_args__ = (UniqueConstraint("context_node_id", "relationship_group_id", name="uq_rgcn_node_rg"),)

    # Relationships
    context_node = relationship("ContextNode")


class ContextNodeSuggestion(Base):
    """AI-suggested context nodes from voice notes and conversation updates."""
    __tablename__ = "context_node_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    suggested_name = Column(Text, nullable=False)
    suggested_type = Column(Enum(ContextNodeType, name="context_node_type"), nullable=False, default=ContextNodeType.other)
    status = Column(Enum(ContextSuggestionStatus, name="context_suggestion_status"), nullable=False, default=ContextSuggestionStatus.suggested)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    person = relationship("Person", foreign_keys=[person_id])
    activity = relationship("Activity", foreign_keys=[activity_id])
    user = relationship("User", foreign_keys=[user_id])


# ── Community Entities ─────────────────────────────────────────────────────────


class CommunityEntityType(str, enum.Enum):
    business = "business"
    school = "school"
    sport_club = "sport_club"
    community_group = "community_group"
    charity = "charity"
    event_partner = "event_partner"
    other = "other"


class CommunityEntity(Base):
    """A real-world organisation that acts as a relationship hub."""
    __tablename__ = "community_entities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    type = Column(Enum(CommunityEntityType, name="community_entity_type"), nullable=False, default=CommunityEntityType.other)
    location = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    people_links = relationship("CommunityEntityPerson", back_populates="community_entity", cascade="all, delete-orphan", lazy="selectin")
    property_links = relationship("CommunityEntityProperty", back_populates="community_entity", cascade="all, delete-orphan", lazy="selectin")
    activity_links = relationship("CommunityEntityActivity", back_populates="community_entity", cascade="all, delete-orphan", lazy="selectin")


class CommunityEntityPerson(Base):
    """Links a person to a community entity with an optional role."""
    __tablename__ = "community_entity_people"

    id = Column(Integer, primary_key=True, index=True)
    community_entity_id = Column(Integer, ForeignKey("community_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("community_entity_id", "person_id", name="uq_ce_person"),)

    # Relationships
    community_entity = relationship("CommunityEntity", back_populates="people_links")
    person = relationship("Person", lazy="selectin")


class CommunityEntityProperty(Base):
    """Links a property to a community entity."""
    __tablename__ = "community_entity_properties"

    id = Column(Integer, primary_key=True, index=True)
    community_entity_id = Column(Integer, ForeignKey("community_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("community_entity_id", "property_id", name="uq_ce_property"),)

    # Relationships
    community_entity = relationship("CommunityEntity", back_populates="property_links")
    property = relationship("Property", lazy="selectin")


class CommunityEntityActivity(Base):
    """Links an activity to a community entity."""
    __tablename__ = "community_entity_activities"

    id = Column(Integer, primary_key=True, index=True)
    community_entity_id = Column(Integer, ForeignKey("community_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("community_entity_id", "activity_id", name="uq_ce_activity"),)

    # Relationships
    community_entity = relationship("CommunityEntity", back_populates="activity_links")
    activity = relationship("Activity", lazy="selectin")


# ── Buyer Interest ─────────────────────────────────────────────────────────────


class BuyerInterest(Base):
    """Tracks a person's buying interest in a specific property."""
    __tablename__ = "buyer_interest"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(Enum(BuyerInterestStage, name="buyer_interest_stage"), nullable=False, default=BuyerInterestStage.seen)
    # Buyer preference fields for match engine
    price_min = Column(Numeric, nullable=True)
    price_max = Column(Numeric, nullable=True)
    bedrooms_min = Column(Integer, nullable=True)
    bathrooms_min = Column(Integer, nullable=True)
    land_size_min = Column(Integer, nullable=True)  # sqm
    preferred_suburbs = Column(ARRAY(String), nullable=True)
    property_type_preference = Column(String(100), nullable=True)
    special_features = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("property_id", "person_id", name="uq_buyer_interest"),)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    property = relationship("Property", back_populates="buyer_interests")
    person = relationship("Person", lazy="selectin")


# ── Property Owners ────────────────────────────────────────────────────────────


# ── Signals ───────────────────────────────────────────────────────────────────


class Signal(Base):
    """An opportunity signal detected by the signal engine."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_type = Column(Enum(SignalType, name="signal_type"), nullable=False)
    entity_type = Column(String(50), nullable=False)  # 'person', 'property', 'community'
    entity_id = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    source_contact_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True)
    source_type = Column(Enum(SignalSourceType, name="signal_source_type"), nullable=False, default=SignalSourceType.system)
    description = Column(Text, nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    source_contact = relationship("Person", foreign_keys=[source_contact_id])


class PropertyOwner(Base):
    """Links a person as an owner of a property."""
    __tablename__ = "property_owners"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("property_id", "person_id", name="uq_property_owner"),)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    property = relationship("Property", back_populates="owner_links")
    person = relationship("Person", lazy="selectin")


# ── Territory Intelligence ────────────────────────────────────────────────────


class Territory(Base):
    """A geographic territory for farming and coverage tracking."""
    __tablename__ = "territories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(30), nullable=True)  # core_territory, expansion_zone, tactical_route
    notes = Column(Text, nullable=True)
    boundary_data = Column(JSON, nullable=True)
    map_image_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    property_links = relationship("TerritoryProperty", back_populates="territory", cascade="all, delete-orphan", lazy="selectin")
    coverage_activities = relationship("CoverageActivity", back_populates="territory", cascade="all, delete-orphan", lazy="selectin")
    farming_programs = relationship("FarmingProgram", back_populates="territory", cascade="all, delete-orphan", lazy="selectin")


class TerritoryProperty(Base):
    """Links a property to a territory."""
    __tablename__ = "territory_properties"

    id = Column(Integer, primary_key=True, index=True)
    territory_id = Column(Integer, ForeignKey("territories.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    linked_manually = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("territory_id", "property_id", name="uq_territory_property"),)

    # Relationships
    territory = relationship("Territory", back_populates="property_links")
    property = relationship("Property", lazy="selectin")


class CoverageActivity(Base):
    """A coverage activity logged against a territory, property, or person."""
    __tablename__ = "coverage_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    territory_id = Column(Integer, ForeignKey("territories.id", ondelete="SET NULL"), nullable=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    activity_type = Column(String(30), nullable=False)
    notes = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    territory = relationship("Territory", back_populates="coverage_activities")
    property = relationship("Property", foreign_keys=[property_id])
    person = relationship("Person", foreign_keys=[person_id])


class FarmingProgram(Base):
    """A recurring farming program linked to a territory."""
    __tablename__ = "farming_programs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    territory_id = Column(Integer, ForeignKey("territories.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    recurrence = Column(String(30), nullable=True)
    next_due_date = Column(Date, nullable=True)
    last_completed_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    territory = relationship("Territory", back_populates="farming_programs")


# ── Door Knock Workflow ───────────────────────────────────────────────────────


class DoorKnockEntry(Base):
    """A single door knock entry within a session."""
    __tablename__ = "door_knock_entries"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("door_knock_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True, index=True)
    property_address = Column(String(500), nullable=False)
    knock_result = Column(String(30), nullable=False)
    contact_name = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    interest_level = Column(String(30), nullable=True)
    voice_note_transcript = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_contact_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    knocked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Relationships
    session = relationship("DoorKnockSession", back_populates="entries")
    property = relationship("Property", foreign_keys=[property_id])
    created_contact = relationship("Person", foreign_keys=[created_contact_id])


class FollowUpTask(Base):
    """A follow-up task linked to a person, property, or door knock session."""
    __tablename__ = "follow_up_tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    related_property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True)
    related_person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True)
    related_session_id = Column(Integer, ForeignKey("door_knock_sessions.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(Date, nullable=True)
    is_completed = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    related_property = relationship("Property", foreign_keys=[related_property_id])
    related_person = relationship("Person", foreign_keys=[related_person_id])
    related_session = relationship("DoorKnockSession", foreign_keys=[related_session_id])


# ── Referral Programme ────────────────────────────────────────────────────────


class Referral(Base):
    """A referral relationship between two contacts."""
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    referrer_person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    referred_person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    referral_status = Column(String(30), nullable=False, default="registered")
    reward_amount = Column(Numeric(10, 2), nullable=False, default=250)
    reward_status = Column(String(20), nullable=False, default="none")
    reward_paid_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    referrer = relationship("Person", foreign_keys=[referrer_person_id], lazy="selectin")
    referred = relationship("Person", foreign_keys=[referred_person_id], lazy="selectin")
