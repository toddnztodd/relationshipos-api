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
    String,
    Text,
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


class TierEnum(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class CadenceStatus(str, enum.Enum):
    green = "green"
    amber = "amber"
    red = "red"


# ── Models ─────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    people = relationship("Person", back_populates="user", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    email_threads = relationship("EmailThread", back_populates="user", cascade="all, delete-orphan")


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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="people")
    activities = relationship("Activity", back_populates="person", cascade="all, delete-orphan")
    email_threads = relationship("EmailThread", back_populates="person", cascade="all, delete-orphan")
    important_dates = relationship("PersonDate", back_populates="person", cascade="all, delete-orphan")
    important_dates_v2 = relationship("PersonImportantDate", back_populates="person", cascade="all, delete-orphan")
    property_links = relationship("PropertyPerson", back_populates="person", cascade="all, delete-orphan")


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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="properties")
    activities = relationship("Activity", back_populates="property", cascade="all, delete-orphan")
    person_links = relationship("PropertyPerson", back_populates="property", cascade="all, delete-orphan")
    checklist_items = relationship("ListingChecklistItem", back_populates="property", cascade="all, delete-orphan")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="SET NULL"), nullable=True, index=True)
    interaction_type = Column(Enum(InteractionType), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notes = Column(Text, nullable=True)
    is_meaningful = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="activities")
    person = relationship("Person", back_populates="activities")
    property = relationship("Property", back_populates="activities")


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
