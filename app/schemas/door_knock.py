"""Pydantic schemas for Door Knock Workflow."""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ── Legacy V1 schemas (kept for backward compatibility) ──────────────────────

MarketingDropType = Optional[Literal["just_listed", "just_sold", "letter", "free_pen", "other"]]


class DoorKnockCreate(BaseModel):
    person_id: Optional[int] = Field(None, description="Link to an existing person (optional)")
    address: str = Field(..., description="Address that was door-knocked")
    relationship_type: Optional[str] = None
    interest_level: Optional[int] = Field(None, ge=1, le=5, description="1-5 interest rating")
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    marketing_drop: MarketingDropType = Field(None)
    marketing_drop_note: Optional[str] = Field(None)


class DoorKnockResponse(BaseModel):
    id: int
    user_id: int
    person_id: Optional[int] = None
    address: str
    relationship_type: Optional[str] = None
    interest_level: Optional[int] = None
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    marketing_drop: MarketingDropType = None
    marketing_drop_note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Door Knock Session (V2) ──────────────────────────────────────────────────


class DoorKnockSessionCreate(BaseModel):
    territory_id: Optional[int] = None
    notes: Optional[str] = None


class DoorKnockSessionUpdate(BaseModel):
    notes: Optional[str] = None


class DoorKnockEntryResponse(BaseModel):
    id: int
    session_id: int
    property_id: Optional[int] = None
    property_address: str
    knock_result: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    interest_level: Optional[str] = None
    voice_note_transcript: Optional[str] = None
    notes: Optional[str] = None
    created_contact_id: Optional[int] = None
    knocked_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class DoorKnockSessionResponse(BaseModel):
    id: int
    user_id: int
    territory_id: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_knocks: int
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DoorKnockSessionDetailResponse(DoorKnockSessionResponse):
    entries: List[DoorKnockEntryResponse] = []


# ── Door Knock Entry (V2) ────────────────────────────────────────────────────


class DoorKnockEntryCreate(BaseModel):
    session_id: int
    property_id: Optional[int] = None
    property_address: str
    knock_result: str  # door_knocked / spoke_to_owner / spoke_to_occupant / no_answer / contact_captured
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    interest_level: Optional[str] = None  # not_interested / neutral / possibly_selling / actively_considering
    voice_note_transcript: Optional[str] = None
    notes: Optional[str] = None


# ── Follow-Up Task ───────────────────────────────────────────────────────────


class FollowUpTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    related_property_id: Optional[int] = None
    related_person_id: Optional[int] = None
    related_session_id: Optional[int] = None
    due_date: Optional[date] = None


class FollowUpTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    related_property_id: Optional[int] = None
    related_person_id: Optional[int] = None
    due_date: Optional[date] = None
    is_completed: Optional[bool] = None


class FollowUpTaskResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    related_property_id: Optional[int] = None
    related_person_id: Optional[int] = None
    related_session_id: Optional[int] = None
    due_date: Optional[date] = None
    is_completed: bool
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
