"""Pydantic schemas for Dashboard aggregation and Open Home Kiosk."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.person import PersonWithCadence


class OpenHomeCheckin(BaseModel):
    """Kiosk-style check-in: phone + name + property_id."""
    phone: str = Field(..., max_length=50)
    first_name: str = Field(..., max_length=255)
    last_name: str = Field(default="", max_length=255)
    property_id: int


class OpenHomeCheckinResponse(BaseModel):
    person_id: int
    activity_id: int
    is_new_person: bool
    message: str


class DriftingRelationship(BaseModel):
    person_id: int
    first_name: str
    last_name: str | None
    phone: str
    tier: str
    days_since_last_meaningful: int
    cadence_window_days: int


class DueForContact(BaseModel):
    person_id: int
    first_name: str
    last_name: str | None
    phone: str
    tier: str
    days_until_deadline: int
    cadence_window_days: int


class OpenHomeCallback(BaseModel):
    person_id: int
    first_name: str
    last_name: str | None
    phone: str
    property_id: int | None
    attendance_date: datetime


class RepeatAttendee(BaseModel):
    person_id: int
    first_name: str
    last_name: str | None
    phone: str
    attendance_count: int
    properties_visited: list[int]


class PersonCadenceStatus(BaseModel):
    person_id: int
    first_name: str
    last_name: str | None
    tier: str
    cadence_status: str  # green / amber / red
    days_since_last_meaningful: int | None
    cadence_window_days: int


class CadenceSummary(BaseModel):
    """Aggregate counts of cadence statuses across all contacts."""
    total_people: int = 0
    green: int = 0
    amber: int = 0
    red: int = 0


class TierBreakdown(BaseModel):
    """Count of contacts per relationship tier."""
    A: int = 0
    B: int = 0
    C: int = 0
    D: int = 0
    total: int = 0


class DashboardResponse(BaseModel):
    a_tier_drifting: list[DriftingRelationship]
    due_for_contact_this_week: list[DueForContact]
    open_home_callbacks_needed: list[OpenHomeCallback]
    repeat_open_home_attendees: list[RepeatAttendee]
    cadence_statuses: list[PersonCadenceStatus]  # limited by ?cadence_limit (default 20)
    cadence_summary: CadenceSummary = CadenceSummary()
    tier_breakdown: TierBreakdown = TierBreakdown()
    cached: bool = False  # True if served from cache


class AISuggestion(BaseModel):
    suggestion_type: str
    person_id: int | None = None
    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)


class AISuggestionsResponse(BaseModel):
    suggestions: list[AISuggestion]
