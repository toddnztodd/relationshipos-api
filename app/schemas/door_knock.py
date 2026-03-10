"""Pydantic schemas for DoorKnockSession."""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Valid marketing drop types
MarketingDropType = Optional[Literal["just_listed", "just_sold", "letter", "promo_item", "none"]]


class DoorKnockCreate(BaseModel):
    person_id: Optional[int] = Field(None, description="Link to an existing person (optional)")
    address: str = Field(..., description="Address that was door-knocked")
    relationship_type: Optional[str] = None
    interest_level: Optional[int] = Field(None, ge=1, le=5, description="1-5 interest rating")
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    marketing_drop: MarketingDropType = Field(
        None,
        description="Marketing material left at the property: just_listed | just_sold | letter | promo_item | none",
    )


class DoorKnockResponse(BaseModel):
    id: int
    user_id: int
    person_id: Optional[int] = None
    address: str
    relationship_type: Optional[str] = None
    interest_level: Optional[int] = None
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    marketing_drop: MarketingDropType = None
    created_at: datetime

    model_config = {"from_attributes": True}
