"""Pydantic schemas for Person Important Dates (v2 — full date)."""

import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field


class ImportantDateCreate(BaseModel):
    label: str = Field(..., max_length=255, examples=["Birthday", "Anniversary", "Settlement Date"])
    date: dt.date = Field(..., description="Full date (YYYY-MM-DD)")
    is_recurring: bool = True
    notes: Optional[str] = None


class ImportantDateUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=255)
    date: Optional[dt.date] = None
    is_recurring: Optional[bool] = None
    notes: Optional[str] = None


class ImportantDateResponse(BaseModel):
    id: int
    owner_id: int
    person_id: int
    label: str
    date: dt.date
    is_recurring: bool
    notes: str | None
    # Enriched
    person_name: str | None = None

    model_config = {"from_attributes": True}
