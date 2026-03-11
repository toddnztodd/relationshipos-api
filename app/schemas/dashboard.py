"""Pydantic schemas for Dashboard aggregation and Open Home Kiosk."""

from datetime import date, datetime, time
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
    property_address: str | None = None
    attendance_date: datetime
    due_date: datetime | None = None


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
    needs_attention: int = 0  # contacts overdue by tier cadence (A>30d, B>60d, C>90d)


class TierBreakdown(BaseModel):
    """Count of contacts per relationship tier — snake_case keys for frontend."""
    tier_a: int = 0
    tier_b: int = 0
    tier_c: int = 0
    tier_d: int = 0
    total: int = 0


class DashboardResponse(BaseModel):
    a_tier_drifting: list[DriftingRelationship]
    due_for_contact_this_week: list[DueForContact]
    open_home_callbacks_needed: list[OpenHomeCallback]
    repeat_open_home_attendees: list[RepeatAttendee]
    cadence_statuses: list[PersonCadenceStatus]  # limited by ?cadence_limit (default 20)
    cadence_summary: CadenceSummary = CadenceSummary()
    tier_breakdown: TierBreakdown = TierBreakdown()
    active_listings: int = 0  # count of properties for this user
    active_appraisals: int = 0  # count of properties with appraisal_status in (booked, completed)
    cached: bool = False  # True if served from cache


class BriefingAnchor(BaseModel):
    id: int
    anchor_text: str
    anchor_type: str

    model_config = {"from_attributes": True}


class BriefingContact(BaseModel):
    person_id: int
    first_name: str
    last_name: str | None
    phone: str
    tier: str
    cadence_status: str
    days_since_last_meaningful: int | None
    cadence_window_days: int
    relationship_summary: str | None = None
    rapport_anchors: list[BriefingAnchor] = []
    suggested_outreach: str | None = None


class BriefingSignal(BaseModel):
    id: int
    signal_type: str
    entity_type: str
    entity_id: int
    entity_name: str | None = None
    confidence: float
    description: str


class BriefingResponse(BaseModel):
    contacts: list[BriefingContact]
    signals: list[BriefingSignal] = []
    total: int
    cached: bool = False


class AISuggestion(BaseModel):
    suggestion_type: str
    person_id: int | None = None
    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)


class AISuggestionsResponse(BaseModel):
    suggestions: list[AISuggestion]
