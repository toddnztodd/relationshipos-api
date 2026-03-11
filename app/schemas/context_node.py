"""Pydantic schemas for Context Nodes."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.models import ContextNodeType


# ── Context Node CRUD ─────────────────────────────────────────────────────────

class ContextNodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    type: ContextNodeType = ContextNodeType.other


class ContextNodeResponse(BaseModel):
    id: int
    name: str
    type: ContextNodeType
    created_at: datetime

    model_config = {"from_attributes": True}


class ContextNodeBrief(BaseModel):
    """Minimal context node info for embedding in person/property responses."""
    id: int
    name: str
    type: ContextNodeType

    model_config = {"from_attributes": True}


# ── Person / Property Attachment ──────────────────────────────────────────────

class AttachContextNodeRequest(BaseModel):
    """Attach an existing context node or create-and-attach."""
    context_node_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    type: ContextNodeType = ContextNodeType.other


class PersonContextNodesResponse(BaseModel):
    """Context nodes attached to a person."""
    person_id: int
    context_nodes: list[ContextNodeBrief] = []


class PropertyContextNodesResponse(BaseModel):
    """Context nodes attached to a property."""
    property_id: int
    context_nodes: list[ContextNodeBrief] = []


# ── Context Node Suggestions ─────────────────────────────────────────────────

class ContextNodeSuggestionResponse(BaseModel):
    id: int
    person_id: int | None
    activity_id: int
    suggested_name: str
    suggested_type: ContextNodeType
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContextNodeSuggestionUpdate(BaseModel):
    status: str = Field(..., pattern="^(accepted|dismissed)$")
