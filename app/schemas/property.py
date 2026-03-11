"""Pydantic schemas for Property Intelligence Layer."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PropertyCreate(BaseModel):
    address: str = Field(..., max_length=500)
    suburb: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=255)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    toilets: Optional[int] = Field(None, ge=0)
    ensuites: Optional[int] = Field(None, ge=0)
    living_rooms: Optional[int] = Field(None, ge=0)
    has_pool: bool = False
    renovation_status: Optional[str] = Field(None, max_length=255)
    years_owned: Optional[float] = Field(None, ge=0)
    council_valuation: Optional[float] = Field(None, ge=0)
    garaging: Optional[str] = Field(None, max_length=255)
    section_size_sqm: Optional[float] = Field(None, ge=0)
    house_size_sqm: Optional[float] = Field(None, ge=0)
    land_value: Optional[str] = Field(None, max_length=255)
    perceived_value: Optional[str] = Field(None, max_length=255)
    appraisal_stage: Optional[str] = Field(None, max_length=100)
    appraisal_status: Optional[str] = Field(None, max_length=100, description="booked | completed | converted_to_listing | lost")
    # Property Intelligence fields
    land_size: Optional[str] = None
    cv: Optional[str] = None
    last_sold_amount: Optional[str] = None
    last_sold_date: Optional[date] = None
    current_listing_price: Optional[str] = None
    listing_url: Optional[str] = None
    listing_agent: Optional[str] = None
    listing_agency: Optional[str] = None
    last_listed_date: Optional[date] = None
    last_listing_result: Optional[str] = Field(None, description="sold | withdrawn | expired | private_sale | unknown")
    sellability: Optional[int] = Field(None, ge=1, le=5)


class PropertyUpdate(BaseModel):
    address: Optional[str] = Field(None, max_length=500)
    suburb: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=255)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    toilets: Optional[int] = Field(None, ge=0)
    ensuites: Optional[int] = Field(None, ge=0)
    living_rooms: Optional[int] = Field(None, ge=0)
    has_pool: Optional[bool] = None
    renovation_status: Optional[str] = Field(None, max_length=255)
    years_owned: Optional[float] = Field(None, ge=0)
    council_valuation: Optional[float] = Field(None, ge=0)
    garaging: Optional[str] = Field(None, max_length=255)
    section_size_sqm: Optional[float] = Field(None, ge=0)
    house_size_sqm: Optional[float] = Field(None, ge=0)
    land_value: Optional[str] = Field(None, max_length=255)
    perceived_value: Optional[str] = Field(None, max_length=255)
    appraisal_stage: Optional[str] = Field(None, max_length=100)
    appraisal_status: Optional[str] = Field(None, max_length=100)
    # Property Intelligence fields
    land_size: Optional[str] = None
    cv: Optional[str] = None
    last_sold_amount: Optional[str] = None
    last_sold_date: Optional[date] = None
    current_listing_price: Optional[str] = None
    listing_url: Optional[str] = None
    listing_agent: Optional[str] = None
    listing_agency: Optional[str] = None
    last_listed_date: Optional[date] = None
    last_listing_result: Optional[str] = None
    sellability: Optional[int] = Field(None, ge=1, le=5)


class PropertyResponse(BaseModel):
    id: int
    user_id: int
    address: str
    suburb: str | None
    city: str | None
    bedrooms: int | None
    bathrooms: int | None
    toilets: int | None = None
    ensuites: int | None = None
    living_rooms: int | None = None
    has_pool: Optional[bool] = False
    renovation_status: str | None
    years_owned: float | None
    council_valuation: float | None
    garaging: str | None
    section_size_sqm: float | None
    house_size_sqm: float | None
    land_value: str | None
    perceived_value: str | None
    appraisal_stage: str | None = None
    appraisal_status: str | None = None
    # Property Intelligence fields
    land_size: str | None = None
    cv: str | None = None
    last_sold_amount: str | None = None
    last_sold_date: date | None = None
    current_listing_price: str | None = None
    listing_url: str | None = None
    listing_agent: str | None = None
    listing_agency: str | None = None
    last_listed_date: date | None = None
    last_listing_result: str | None = None
    sellability: int | None = None
    estimated_value: Optional[float] = None
    property_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Buyer Interest schemas ────────────────────────────────────────────────────

class BuyerInterestCreate(BaseModel):
    person_id: int
    stage: str = Field("seen", description="seen | interested | hot | offer | purchased")
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    bedrooms_min: Optional[int] = None
    bathrooms_min: Optional[int] = None
    land_size_min: Optional[int] = None
    preferred_suburbs: Optional[List[str]] = None
    property_type_preference: Optional[str] = None
    special_features: Optional[List[str]] = None


class BuyerInterestUpdate(BaseModel):
    stage: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    bedrooms_min: Optional[int] = None
    bathrooms_min: Optional[int] = None
    land_size_min: Optional[int] = None
    preferred_suburbs: Optional[List[str]] = None
    property_type_preference: Optional[str] = None
    special_features: Optional[List[str]] = None


class BuyerInterestPersonSummary(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = ""

    model_config = {"from_attributes": True}


class BuyerInterestResponse(BaseModel):
    id: int
    property_id: int
    person_id: int
    person: Optional[BuyerInterestPersonSummary] = None
    stage: str
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    bedrooms_min: Optional[int] = None
    bathrooms_min: Optional[int] = None
    land_size_min: Optional[int] = None
    preferred_suburbs: Optional[List[str]] = None
    property_type_preference: Optional[str] = None
    special_features: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Property Owner schemas ────────────────────────────────────────────────────

class PropertyOwnerCreate(BaseModel):
    person_id: int


class PropertyOwnerPersonSummary(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = ""

    model_config = {"from_attributes": True}


class PropertyOwnerResponse(BaseModel):
    id: int
    property_id: int
    person_id: int
    person: Optional[PropertyOwnerPersonSummary] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Property Match schemas ────────────────────────────────────────────────────

class PropertyMatchRequest(BaseModel):
    address: str


class PropertyMatchResponse(BaseModel):
    match: Optional[PropertyResponse] = None
    confidence: str = Field(..., description="exact | likely | none")


# ── Property Voice Parse schemas ──────────────────────────────────────────────

class PropertyParseVoiceRequest(BaseModel):
    transcription: str


class PropertyParseVoiceResponse(BaseModel):
    cv: Optional[str] = None
    last_sold_amount: Optional[str] = None
    last_sold_date: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    land_size: Optional[str] = None
    last_listed_date: Optional[str] = None
    last_listing_result: Optional[str] = None
    listing_agent: Optional[str] = None
    listing_agency: Optional[str] = None
    current_listing_price: Optional[str] = None
