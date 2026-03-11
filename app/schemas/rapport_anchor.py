"""Pydantic schemas for Rapport Anchors."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.models import AnchorStatus


class RapportAnchorCreate(BaseModel):
    """Manually add a rapport anchor to a person."""
    anchor_text: str = Field(..., min_length=1, max_length=500)
    anchor_type: Literal["individual", "household"] = "individual"


class RapportAnchorUpdate(BaseModel):
    """Update anchor status or text."""
    status: Optional[AnchorStatus] = None
    anchor_text: Optional[str] = Field(None, min_length=1, max_length=500)


class RapportAnchorResponse(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    person_id: int | None
    relationship_group_id: int | None
    activity_id: int
    user_id: int
    anchor_text: str
    anchor_type: str
    status: AnchorStatus

    model_config = {"from_attributes": True}


class RapportAnchorsForPerson(BaseModel):
    """Grouped response: accepted + suggested anchors for a person."""
    accepted: list[RapportAnchorResponse] = []
    suggested: list[RapportAnchorResponse] = []
