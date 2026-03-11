"""Pydantic schemas for Activity / Interaction Logging."""

from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field

from app.models.models import InteractionType


class ActivityCreate(BaseModel):
    person_id: Optional[int] = None
    property_id: Optional[int] = None
    interaction_type: InteractionType
    date: Optional[datetime] = None  # defaults to now on server
    notes: Optional[str] = None
    is_meaningful: bool = True
    feedback: Optional[str] = None
    price_indication: Optional[str] = Field(None, max_length=255)
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[time] = None
    source: Optional[str] = Field(None, max_length=100, description="Source of the activity: conversation_update, manual, etc.")


class ActivityQuickLog(BaseModel):
    """Optimised for speed — minimal fields for fast mobile logging."""
    person_id: Optional[int] = None
    interaction_type: InteractionType
    notes: Optional[str] = None
    is_meaningful: bool = True
    source: Optional[str] = Field(None, max_length=100)


class ActivityUpdate(BaseModel):
    person_id: Optional[int] = None
    property_id: Optional[int] = None
    interaction_type: Optional[InteractionType] = None
    date: Optional[datetime] = None
    notes: Optional[str] = None
    is_meaningful: Optional[bool] = None
    feedback: Optional[str] = None
    price_indication: Optional[str] = Field(None, max_length=255)
    scheduled_date: Optional[date] = None
    scheduled_time: Optional[time] = None
    source: Optional[str] = Field(None, max_length=100)


class ActivityResponse(BaseModel):
    id: int
    user_id: int
    person_id: int | None
    property_id: int | None
    interaction_type: InteractionType
    date: datetime
    notes: str | None
    is_meaningful: bool
    due_date: datetime | None = None
    feedback: str | None = None
    price_indication: str | None = None
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    source: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityWithPerson(ActivityResponse):
    """Activity response enriched with person name for dashboard views."""
    person_first_name: str | None = None
    person_last_name: str | None = None
    person_phone: str | None = None


class TranscriptionResponse(BaseModel):
    """Response from the voice transcription endpoint."""
    transcription: str


class ScreenshotAnalysisResponse(BaseModel):
    """Response from the conversation screenshot analysis endpoint."""
    summary: str | None = None
    participants: list[str] = []
    property: str | None = None
    datetime: str | None = None
