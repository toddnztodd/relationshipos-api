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
    relationship_types: Optional[list[str]] = Field(
        default=None,
        description="Multi-select relationship types. Values: buyer, seller, investor, landlord, tenant, developer, other",
    )
    influence_score: Optional[float] = Field(0.0, ge=0)
    tier: TierEnum = Field(default=TierEnum.C)
    lead_source: Optional[str] = Field(None, max_length=255)
    buyer_readiness_status: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    is_relationship_asset: Optional[bool] = False
    email_sync_enabled: Optional[bool] = False
    drivers_licence_number: Optional[str] = Field(None, max_length=100)
    drivers_licence_expiry: Optional[date] = None
    drivers_licence_verified: Optional[bool] = False
    drivers_licence_verified_date: Optional[date] = None
    aml_status: Optional[str] = Field(default="not_started", max_length=50)
    perceived_value: Optional[str] = Field(None, max_length=255)
    buyer_interest: Optional[int] = Field(None, ge=0, le=5, description="0-5 buyer interest rating")
    seller_likelihood: Optional[int] = Field(None, ge=0, le=5, description="0-5 seller likelihood rating")
    nickname: Optional[str] = Field(None, max_length=255)


class PersonUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=255)
    last_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    suburb: Optional[str] = Field(None, max_length=255)
    relationship_type: Optional[str] = Field(None, max_length=100)
    relationship_types: Optional[list[str]] = Field(
        default=None,
        description="Multi-select relationship types. Values: buyer, seller, investor, landlord, tenant, developer, other",
    )
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
    buyer_interest: Optional[int] = Field(None, ge=0, le=5)
    seller_likelihood: Optional[int] = Field(None, ge=0, le=5)
    nickname: Optional[str] = Field(None, max_length=255)


class PersonResponse(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    suburb: Optional[str] = None
    relationship_type: Optional[str] = None
    relationship_types: Optional[list[str]] = None
    influence_score: Optional[float] = None
    tier: TierEnum
    lead_source: Optional[str] = None
    buyer_readiness_status: Optional[str] = None
    notes: Optional[str] = None
    is_relationship_asset: Optional[bool] = False
    email_sync_enabled: Optional[bool] = False
    drivers_licence_number: Optional[str] = None
    drivers_licence_expiry: Optional[date] = None
    drivers_licence_verified: Optional[bool] = False
    drivers_licence_verified_date: Optional[date] = None
    aml_status: Optional[str] = "not_started"
    perceived_value: Optional[str] = None
    buyer_interest: Optional[int] = None
    seller_likelihood: Optional[int] = None
    nickname: Optional[str] = None
    last_interaction_at: Optional[datetime] = None
    last_interaction_channel: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonWithCadence(PersonResponse):
    """Person response enriched with cadence status and health fields."""
    cadence_status: str = "green"  # green / amber / red
    days_since_last_meaningful: Optional[int] = None
    cadence_window_days: int = 90
    # New health fields
    health_status: str = "Overdue"  # Healthy | At Risk | Overdue
    days_since_contact: Optional[int] = None
    cadence_limit: int = 90  # 30, 60, or 90 based on tier


class PersonSearchByPhone(BaseModel):
    phone: str = Field(..., max_length=50)


class NextBestContact(BaseModel):
    """Compact contact for the next-best-action list."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    phone: str
    email: Optional[str] = None
    tier: TierEnum
    health_status: str  # Healthy | At Risk | Overdue
    days_since_contact: Optional[int] = None
    cadence_limit: int
    last_interaction_channel: Optional[str] = None

    model_config = {"from_attributes": True}
