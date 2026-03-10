"""Pydantic schemas for Person Important Dates (v2 — full date)."""

import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field


class ImportantDateCreate(BaseModel):
    label: str = Field(..., max_length=255, examples=["Birthday", "Anniversary", "Settlement Date"])
    date: dt.date = Field(..., description="Full date (YYYY-MM-DD)")
    is_recurring: bool = True
    reminder_days_before: int = Field(7, ge=0, le=365)
    notes: Optional[str] = None


class ImportantDateUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=255)
    date: Optional[dt.date] = None
    is_recurring: Optional[bool] = None
    reminder_days_before: Optional[int] = Field(None, ge=0, le=365)
    notes: Optional[str] = None


class ImportantDateResponse(BaseModel):
    id: int
    owner_id: int
    person_id: int
    label: str
    date: dt.date
    is_recurring: bool
    reminder_days_before: int = 7
    notes: str | None
    created_at: dt.datetime | None = None
    # Enriched
    person_name: str | None = None

    model_config = {"from_attributes": True}
