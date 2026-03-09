"""SQLAlchemy ORM models for RelationshipOS."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="people")
    activities = relationship("Activity", back_populates="person", cascade="all, delete-orphan")
    email_threads = relationship("EmailThread", back_populates="person", cascade="all, delete-orphan")
    important_dates = relationship("PersonDate", back_populates="person", cascade="all, delete-orphan")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    address = Column(String(500), nullable=False)
    suburb = Column(String(255), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    has_pool = Column(Boolean, default=False)
    renovation_status = Column(String(255), nullable=True)
    years_owned = Column(Float, nullable=True)
    council_valuation = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="properties")
    activities = relationship("Activity", back_populates="property", cascade="all, delete-orphan")


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
    """Important dates associated with a person (birthdays, anniversaries, custom)."""
    __tablename__ = "person_dates"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(255), nullable=False, doc="e.g. 'Birthday', 'Anniversary', or custom text")
    date = Column(String(5), nullable=False, doc="Month and day stored as MM-DD, e.g. '03-25'")
    year = Column(Integer, nullable=True, doc="Optional year the event occurred or will occur")
    reminder_days_before = Column(Integer, nullable=False, default=7)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    person = relationship("Person", back_populates="important_dates")
