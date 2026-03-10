"""Pydantic schemas for Weekly BASICS tracking and user annual goals."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Weekly Tracking ────────────────────────────────────────────────────────────


class WeeklyTrackingBase(BaseModel):
    """Shared fields for weekly tracking records."""
    phone_calls_daily: Optional[list[int]] = Field(
        default=None,
        description="Array of 7 integers — phone calls per day [Mon, Tue, Wed, Thu, Fri, Sat, Sun]",
    )
    connects_count: Optional[int] = Field(default=None, ge=0)
    f2f_property_owners: Optional[int] = Field(default=None, ge=0)
    f2f_influencers: Optional[int] = Field(default=None, ge=0)
    calls_influencers: Optional[int] = Field(default=None, ge=0)
    new_contacts: Optional[int] = Field(default=None, ge=0)
    contacts_cleaned: Optional[int] = Field(default=None, ge=0)
    thank_you_cards: Optional[int] = Field(default=None, ge=0)
    letterbox_drops: Optional[int] = Field(default=None, ge=0)
    review_exercise: Optional[int] = Field(default=None, ge=1, le=10)
    review_diet: Optional[int] = Field(default=None, ge=1, le=10)
    review_energy: Optional[int] = Field(default=None, ge=1, le=10)
    review_enthusiasm: Optional[int] = Field(default=None, ge=1, le=10)
    review_work_life: Optional[int] = Field(default=None, ge=1, le=10)
    review_overall: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None


class WeeklyTrackingUpsert(WeeklyTrackingBase):
    """Payload for PUT /weekly-tracking/{week_start_date}."""
    pass


class WeeklyTrackingResponse(WeeklyTrackingBase):
    """Full weekly tracking record returned by the API."""
    id: int
    user_id: int
    week_start_date: date
    phone_calls_daily: list[int] = Field(default_factory=list)
    connects_count: int = 0
    f2f_property_owners: int = 0
    f2f_influencers: int = 0
    calls_influencers: int = 0
    new_contacts: int = 0
    contacts_cleaned: int = 0
    thank_you_cards: int = 0
    letterbox_drops: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Weekly Summary (month-to-date + YTD) ──────────────────────────────────────


class WeeklySummaryTotals(BaseModel):
    """Aggregated totals for a time period."""
    phone_calls: int = 0
    connects: int = 0
    f2f_property_owners: int = 0
    f2f_influencers: int = 0
    calls_influencers: int = 0
    new_contacts: int = 0
    contacts_cleaned: int = 0
    thank_you_cards: int = 0
    letterbox_drops: int = 0
    door_knocks: int = 0


class WeeklySummaryResponse(BaseModel):
    """Summary of activity totals for the current month and YTD."""
    month_to_date: WeeklySummaryTotals
    year_to_date: WeeklySummaryTotals
    current_week: Optional[WeeklyTrackingResponse] = None


# ── User Annual Goals ──────────────────────────────────────────────────────────


class UserGoalsUpdate(BaseModel):
    """Payload for PUT /users/goals."""
    gc_goal_year: Optional[float] = Field(default=None, description="Annual GC target (dollars)")
    listings_target_year: Optional[int] = Field(default=None, ge=0, description="Annual listings target")
    deals_target_year: Optional[int] = Field(default=None, ge=0, description="Annual deals target")


class UserGoalsResponse(BaseModel):
    """Annual goals for the current user."""
    gc_goal_year: Optional[float] = None
    listings_target_year: Optional[int] = None
    deals_target_year: Optional[int] = None

    class Config:
        from_attributes = True
