"""Pydantic schemas for Person Relationships."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonRelationshipCreate(BaseModel):
    person_b_id: int = Field(..., description="ID of the related person")
    relationship_type: str = Field(..., max_length=255, examples=["Spouse", "Sibling", "Referred By", "Friend"])
    notes: Optional[str] = None


class PersonRelationshipResponse(BaseModel):
    id: int
    owner_id: int
    person_a_id: int
    person_b_id: int
    relationship_type: str
    notes: str | None
    created_at: datetime
    # Enriched fields for display
    person_a_name: str | None = None
    person_b_name: str | None = None

    model_config = {"from_attributes": True}
