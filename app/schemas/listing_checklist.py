"""Pydantic schemas for the structured Listing Checklist system."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


# ── Item schemas ─────────────────────────────────────────────────────────────


class ChecklistItemCreate(BaseModel):
    phase_number: int
    item_text: str
    sort_order: int = 0
    due_date: Optional[date] = None
    note: Optional[str] = None


class ChecklistItemUpdate(BaseModel):
    is_complete: Optional[bool] = None
    due_date: Optional[date] = None
    note: Optional[str] = None


class ChecklistItemResponse(BaseModel):
    id: int
    phase_number: int
    item_text: str
    is_complete: bool
    completed_at: Optional[datetime] = None
    due_date: Optional[date] = None
    note: Optional[str] = None
    sort_order: int

    model_config = {"from_attributes": True}


# ── Phase schemas ────────────────────────────────────────────────────────────


class ChecklistPhaseResponse(BaseModel):
    phase_number: int
    phase_name: str
    is_complete: bool
    completed_at: Optional[datetime] = None
    items: List[ChecklistItemResponse] = []

    model_config = {"from_attributes": True}


# ── Checklist schemas ────────────────────────────────────────────────────────


class ChecklistCreate(BaseModel):
    sale_method: str  # priced, by_negotiation, deadline, auction


class PhaseUpdate(BaseModel):
    current_phase: int


class ChecklistResponse(BaseModel):
    id: int
    property_id: int
    sale_method: str
    current_phase: int
    phases: List[ChecklistPhaseResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
