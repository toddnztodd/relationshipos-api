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
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
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
    door_knock_sessions = relationship("DoorKnockSession", back_populates="person")
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
    """Records of door knock sessions."""
    __tablename__ = "door_knock_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    address = Column(Text, nullable=False)
    relationship_type = Column(Text, nullable=True)
    interest_level = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    follow_up_date = Column(Date, nullable=True)
    marketing_drop = Column(String(50), nullable=True)  # just_listed | just_sold | letter | free_pen | other
    marketing_drop_note = Column(Text, nullable=True)  # custom note when marketing_drop = 'other'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="door_knock_sessions")
    person = relationship("Person", back_populates="door_knock_sessions")


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
