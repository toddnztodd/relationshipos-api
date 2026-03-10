"""Pydantic schemas for Property Intelligence Layer."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PropertyCreate(BaseModel):
    address: str = Field(..., max_length=500)
    suburb: Optional[str] = Field(None, max_length=255)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    has_pool: bool = False
    renovation_status: Optional[str] = Field(None, max_length=255)
    years_owned: Optional[float] = Field(None, ge=0)
    council_valuation: Optional[float] = Field(None, ge=0)
    garaging: Optional[str] = Field(None, max_length=255)
    section_size_sqm: Optional[float] = Field(None, ge=0)
    house_size_sqm: Optional[float] = Field(None, ge=0)
    land_value: Optional[str] = Field(None, max_length=255)
    perceived_value: Optional[str] = Field(None, max_length=255)


class PropertyUpdate(BaseModel):
    address: Optional[str] = Field(None, max_length=500)
    suburb: Optional[str] = Field(None, max_length=255)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    has_pool: Optional[bool] = None
    renovation_status: Optional[str] = Field(None, max_length=255)
    years_owned: Optional[float] = Field(None, ge=0)
    council_valuation: Optional[float] = Field(None, ge=0)
    garaging: Optional[str] = Field(None, max_length=255)
    section_size_sqm: Optional[float] = Field(None, ge=0)
    house_size_sqm: Optional[float] = Field(None, ge=0)
    land_value: Optional[str] = Field(None, max_length=255)
    perceived_value: Optional[str] = Field(None, max_length=255)


class PropertyResponse(BaseModel):
    id: int
    user_id: int
    address: str
    suburb: str | None
    bedrooms: int | None
    bathrooms: int | None
    has_pool: Optional[bool] = False
    renovation_status: str | None
    years_owned: float | None
    council_valuation: float | None
    garaging: str | None
    section_size_sqm: float | None
    house_size_sqm: float | None
    land_value: str | None
    perceived_value: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
