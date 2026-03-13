"""Pydantic schemas for Appraisal Recordings."""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel


# ── Request schemas ───────────────────────────────────────────────────────────


class AppraisalRecordingCreate(BaseModel):
    """Payload to create a new appraisal recording."""

    audio_url: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    extracted_intelligence: Optional[Dict[str, Any]] = None
    detected_signals: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[int] = None


class AppraisalRecordingUpdate(BaseModel):
    """Payload to update an existing appraisal recording (all fields optional)."""

    audio_url: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    extracted_intelligence: Optional[Dict[str, Any]] = None
    detected_signals: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[int] = None


# ── Response schemas ──────────────────────────────────────────────────────────


class AppraisalRecordingResponse(BaseModel):
    """Full appraisal recording response."""

    id: int
    property_id: int
    user_id: int
    created_at: datetime
    audio_url: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    extracted_intelligence: Optional[Dict[str, Any]] = None
    detected_signals: Optional[Dict[str, Any]] = None
    duration_seconds: Optional[int] = None

    model_config = {"from_attributes": True}


class AppraisalRecordingListResponse(BaseModel):
    """List of appraisal recordings with total count."""

    recordings: list[AppraisalRecordingResponse]
    total: int
