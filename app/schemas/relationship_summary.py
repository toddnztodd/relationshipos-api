"""Pydantic schemas for Relationship Summary endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RelationshipSummaryResponse(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    person_id: int
    user_id: int
    summary_text: str
    status: str
    is_update: bool

    model_config = {"from_attributes": True}


class RelationshipSummaryUpdate(BaseModel):
    status: Optional[str] = None
    summary_text: Optional[str] = None


class RelationshipSummaryForPerson(BaseModel):
    accepted: Optional[RelationshipSummaryResponse] = None
    suggested: Optional[RelationshipSummaryResponse] = None


class GenerationStartedResponse(BaseModel):
    message: str
