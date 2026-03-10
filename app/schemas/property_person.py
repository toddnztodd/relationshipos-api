"""Pydantic schemas for Property-Person Links."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PropertyPersonCreate(BaseModel):
    person_id: int = Field(..., description="ID of the person to link")
    role: str = Field(..., max_length=255, examples=["Vendor", "Buyer Enquiry", "Open Home Attendee", "Solicitor", "Builder/Inspector", "Other"])
    custom_label: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class PropertyPersonResponse(BaseModel):
    id: int
    owner_id: int
    property_id: int
    person_id: int
    role: str
    custom_label: str | None = None
    notes: str | None
    created_at: datetime
    # Enriched fields
    person_name: str | None = None
    property_address: str | None = None

    model_config = {"from_attributes": True}
