"""Pydantic schemas for DoorKnockSession."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class DoorKnockCreate(BaseModel):
    person_id: Optional[int] = Field(None, description="Link to an existing person (optional)")
    address: str = Field(..., description="Address that was door-knocked")
    relationship_type: Optional[str] = None
    interest_level: Optional[int] = Field(None, ge=1, le=5, description="1-5 interest rating")
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None


class DoorKnockResponse(BaseModel):
    id: int
    user_id: int
    person_id: Optional[int] = None
    address: str
    relationship_type: Optional[str] = None
    interest_level: Optional[int] = None
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    created_at: datetime

    model_config = {"from_attributes": True}
