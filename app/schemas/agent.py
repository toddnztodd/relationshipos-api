"""Pydantic schemas for the Agents intelligence layer."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────


class AgentCreate(BaseModel):
    """Payload to create a new agent."""
    name: str = Field(..., min_length=1, max_length=255)
    agency: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)


class AgentUpdate(BaseModel):
    """Payload to update an agent (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    agency: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)


# ── Response schemas ──────────────────────────────────────────────────────────


class AgentResponse(BaseModel):
    """Basic agent response."""
    id: int
    name: str
    agency: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListItem(BaseModel):
    """Agent list item with property count and latest activity date."""
    id: int
    name: str
    agency: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    property_count: int = 0
    latest_activity_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    """Paginated list of agents."""
    agents: list[AgentListItem]
    total: int


# ── Detail view with linked properties ────────────────────────────────────────


class AgentPropertySummary(BaseModel):
    """Minimal property info shown on the agent detail view."""
    id: int
    address: str
    suburb: Optional[str] = None
    listing_agent: Optional[str] = None
    listing_agency: Optional[str] = None
    current_listing_price: Optional[str] = None
    last_listing_result: Optional[str] = None
    last_sold_amount: Optional[str] = None
    last_sold_date: Optional[date] = None
    appraisal_status: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentWithProperties(BaseModel):
    """Full agent detail including linked properties."""
    id: int
    name: str
    agency: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    properties: list[AgentPropertySummary] = []

    model_config = {"from_attributes": True}
