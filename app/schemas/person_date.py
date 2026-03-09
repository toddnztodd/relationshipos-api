"""Pydantic schemas for Important Dates (PersonDate).

The frontend sends dates as YYYY-MM-DD (from <input type="date">), so the
validator auto-converts to MM-DD for storage.  It also sends extra fields
(is_recurring, recurrence_type) that the backend silently ignores.
"""

import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# Matches MM-DD (already normalised)
_MMDD_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
# Matches YYYY-MM-DD (from HTML date input)
_YMMDD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _normalise_date(v: str) -> str:
    """Accept both YYYY-MM-DD and MM-DD; always return MM-DD."""
    if _MMDD_RE.match(v):
        return v
    m = _YMMDD_RE.match(v)
    if m:
        return f"{m.group(2)}-{m.group(3)}"
    raise ValueError(
        "date must be in MM-DD or YYYY-MM-DD format, e.g. '03-25' or '2026-03-25'"
    )


class PersonDateCreate(BaseModel):
    label: str = Field(
        ...,
        max_length=255,
        examples=["Birthday", "Anniversary", "Settlement Date"],
    )
    date: str = Field(
        ...,
        description="Date in MM-DD or YYYY-MM-DD format (stored as MM-DD)",
        examples=["03-25", "2026-03-25"],
    )
    year: Optional[int] = Field(
        None,
        ge=1900,
        le=2100,
        description="Optional year the event occurred or will occur",
    )
    reminder_days_before: int = Field(
        default=7,
        ge=0,
        le=365,
        description="How many days before the date to send a reminder",
    )
    notes: Optional[str] = None

    # ── Extra fields the frontend sends (accepted but not persisted) ──
    is_recurring: Optional[bool] = None
    recurrence_type: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def extract_year_and_normalise(cls, data: Any) -> Any:
        """Extract year from YYYY-MM-DD before the date field is normalised."""
        if isinstance(data, dict):
            raw_date = data.get("date", "")
            if isinstance(raw_date, str):
                m = _YMMDD_RE.match(raw_date)
                if m and data.get("year") is None:
                    data["year"] = int(m.group(1))
        return data

    @field_validator("date")
    @classmethod
    def validate_and_normalise(cls, v: str) -> str:
        return _normalise_date(v)


class PersonDateUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=255)
    date: Optional[str] = Field(None, description="MM-DD or YYYY-MM-DD format")
    year: Optional[int] = Field(None, ge=1900, le=2100)
    reminder_days_before: Optional[int] = Field(None, ge=0, le=365)
    notes: Optional[str] = None

    # ── Extra fields the frontend may send ──
    is_recurring: Optional[bool] = None
    recurrence_type: Optional[str] = None

    @field_validator("date")
    @classmethod
    def validate_and_normalise(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _normalise_date(v)
        return v


class PersonDateResponse(BaseModel):
    id: int
    person_id: int
    label: str
    date: str
    year: int | None
    reminder_days_before: int
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UpcomingDateResponse(BaseModel):
    """PersonDate enriched with person details and occurrence metadata."""
    id: int
    person_id: int
    person_first_name: str
    person_last_name: str | None
    person_phone: str
    label: str
    date: str           # MM-DD
    year: int | None
    reminder_days_before: int
    notes: str | None
    days_until: int     # 0 = today, 1 = tomorrow, etc.
    next_occurrence: str  # ISO date string of the next occurrence, e.g. "2026-03-25"
    created_at: datetime

    model_config = {"from_attributes": True}
