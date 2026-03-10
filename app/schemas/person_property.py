"""Pydantic schemas for PersonProperty (properties linked to a person)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonPropertyCreate(BaseModel):
    address: str = Field(..., description="Property address")
    relationship_type: str = Field(default="Viewed", description="e.g. Viewed, Interested, Owner, Tenant")
    notes: Optional[str] = None
    interest_level: Optional[int] = Field(None, ge=1, le=5, description="1-5 interest rating")


class PersonPropertyUpdate(BaseModel):
    address: Optional[str] = None
    relationship_type: Optional[str] = None
    notes: Optional[str] = None
    interest_level: Optional[int] = Field(None, ge=1, le=5)


class PersonPropertyResponse(BaseModel):
    id: int
    person_id: int
    user_id: int
    address: str
    relationship_type: str
    notes: Optional[str] = None
    interest_level: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
