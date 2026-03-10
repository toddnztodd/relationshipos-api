"""Pydantic schemas for Person (People Engine)."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.models import TierEnum


class PersonCreate(BaseModel):
    first_name: str = Field(..., max_length=255)
    last_name: str = Field(default="", max_length=255)
    phone: str = Field(..., max_length=50, description="Primary identity key")
    email: Optional[str] = Field(None, max_length=255)
    suburb: Optional[str] = Field(None, max_length=255)
    relationship_type: Optional[str] = Field(None, max_length=100, examples=["buyer", "seller", "investor"])
    influence_score: Optional[float] = Field(0.0, ge=0)
    tier: TierEnum = Field(default=TierEnum.C)
    lead_source: Optional[str] = Field(None, max_length=255)
    buyer_readiness_status: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    is_relationship_asset: bool = False
    email_sync_enabled: bool = False
    drivers_licence_number: Optional[str] = Field(None, max_length=100)
    drivers_licence_expiry: Optional[date] = None
    drivers_licence_verified: bool = False
    drivers_licence_verified_date: Optional[date] = None
    aml_status: str = Field(default="not_started", max_length=50)
    perceived_value: Optional[str] = Field(None, max_length=255)


class PersonUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=255)
    last_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    suburb: Optional[str] = Field(None, max_length=255)
    relationship_type: Optional[str] = Field(None, max_length=100)
    influence_score: Optional[float] = Field(None, ge=0)
    tier: Optional[TierEnum] = None
    lead_source: Optional[str] = Field(None, max_length=255)
    buyer_readiness_status: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    is_relationship_asset: Optional[bool] = None
    email_sync_enabled: Optional[bool] = None
    drivers_licence_number: Optional[str] = Field(None, max_length=100)
    drivers_licence_expiry: Optional[date] = None
    drivers_licence_verified: Optional[bool] = None
    drivers_licence_verified_date: Optional[date] = None
    aml_status: Optional[str] = Field(None, max_length=50)
    perceived_value: Optional[str] = Field(None, max_length=255)


class PersonResponse(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str | None
    phone: str
    email: str | None
    suburb: str | None
    relationship_type: str | None
    influence_score: float | None
    tier: TierEnum
    lead_source: str | None
    buyer_readiness_status: str | None
    notes: str | None
    is_relationship_asset: bool
    email_sync_enabled: bool
    drivers_licence_number: str | None
    drivers_licence_expiry: date | None
    drivers_licence_verified: bool
    drivers_licence_verified_date: date | None
    aml_status: str
    perceived_value: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonWithCadence(PersonResponse):
    """Person response enriched with cadence status."""
    cadence_status: str = "green"  # green / amber / red
    days_since_last_meaningful: int | None = None
    cadence_window_days: int = 90


class PersonSearchByPhone(BaseModel):
    phone: str = Field(..., max_length=50)
