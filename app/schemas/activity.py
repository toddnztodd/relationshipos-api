"""Pydantic schemas for Activity / Interaction Logging."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.models import InteractionType


class ActivityCreate(BaseModel):
    person_id: int
    property_id: Optional[int] = None
    interaction_type: InteractionType
    date: Optional[datetime] = None  # defaults to now on server
    notes: Optional[str] = None
    is_meaningful: bool = True


class ActivityQuickLog(BaseModel):
    """Optimised for speed — minimal fields for fast mobile logging."""
    person_id: int
    interaction_type: InteractionType
    notes: Optional[str] = None
    is_meaningful: bool = True


class ActivityUpdate(BaseModel):
    person_id: Optional[int] = None
    property_id: Optional[int] = None
    interaction_type: Optional[InteractionType] = None
    date: Optional[datetime] = None
    notes: Optional[str] = None
    is_meaningful: Optional[bool] = None


class ActivityResponse(BaseModel):
    id: int
    user_id: int
    person_id: int
    property_id: int | None
    interaction_type: InteractionType
    date: datetime
    notes: str | None
    is_meaningful: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityWithPerson(ActivityResponse):
    """Activity response enriched with person name for dashboard views."""
    person_first_name: str | None = None
    person_last_name: str | None = None
    person_phone: str | None = None
