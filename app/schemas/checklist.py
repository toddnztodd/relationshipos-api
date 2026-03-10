"""Pydantic schemas for Listing Checklist Items."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChecklistItemCreate(BaseModel):
    phase: str = Field(..., max_length=255)
    step_name: str = Field(..., max_length=500)
    is_completed: bool = False
    due_date: Optional[date] = None
    notes: Optional[str] = None
    sort_order: int = 0
    sale_method: Optional[str] = Field(None, max_length=100, examples=["Auction", "Tender", "Deadline Treaty", "Exclusive"])


class ChecklistItemUpdate(BaseModel):
    phase: Optional[str] = Field(None, max_length=255)
    step_name: Optional[str] = Field(None, max_length=500)
    is_completed: Optional[bool] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None
    sale_method: Optional[str] = Field(None, max_length=100)


class ChecklistItemResponse(BaseModel):
    id: int
    owner_id: int
    property_id: int
    phase: str
    step_name: str
    is_completed: bool
    completed_at: datetime | None
    due_date: date | None
    notes: str | None
    sort_order: int
    sale_method: str | None

    model_config = {"from_attributes": True}
