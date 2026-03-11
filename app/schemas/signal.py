"""Pydantic schemas for Opportunity Signals."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SignalResponse(BaseModel):
    id: int
    signal_type: str
    entity_type: str
    entity_id: int
    entity_name: Optional[str] = None
    confidence: float
    source_contact_id: Optional[int] = None
    source_type: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SignalBriefingItem(BaseModel):
    """Lightweight signal for inclusion in the daily briefing."""
    id: int
    signal_type: str
    entity_type: str
    entity_id: int
    entity_name: Optional[str] = None
    confidence: float
    description: str


class SignalDetectResponse(BaseModel):
    """Response from the POST /signals/detect endpoint."""
    signals_created: int
    signals_deactivated: int
    total_active: int


class SignalListResponse(BaseModel):
    signals: list[SignalResponse]
    total: int
