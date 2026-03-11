"""Pydantic schemas for Community Entities."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ── Nested summaries ──────────────────────────────────────────────────────────

class PersonSummary(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = ""
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class PropertySummary(BaseModel):
    id: int
    address: str

    class Config:
        from_attributes = True


class ActivitySummary(BaseModel):
    id: int
    interaction_type: str
    notes: Optional[str] = None
    date: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommunityEntityPersonLink(BaseModel):
    person_id: int
    first_name: str
    last_name: Optional[str] = ""
    role: Optional[str] = None

    class Config:
        from_attributes = True


class CommunityEntityPropertyLink(BaseModel):
    property_id: int
    address: str

    class Config:
        from_attributes = True


class CommunityEntityActivityLink(BaseModel):
    activity_id: int
    interaction_type: str
    notes: Optional[str] = None
    date: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── CRUD schemas ──────────────────────────────────────────────────────────────

class CommunityEntityCreate(BaseModel):
    name: str
    type: str = "other"
    location: Optional[str] = None
    notes: Optional[str] = None


class CommunityEntityUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class CommunityEntityResponse(BaseModel):
    id: int
    name: str
    type: str
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    people: List[CommunityEntityPersonLink] = []
    properties: List[CommunityEntityPropertyLink] = []
    recent_activities: List[CommunityEntityActivityLink] = []

    class Config:
        from_attributes = True


class CommunityEntityListItem(BaseModel):
    id: int
    name: str
    type: str
    location: Optional[str] = None
    people_count: int = 0
    property_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# ── Linking schemas ───────────────────────────────────────────────────────────

class LinkPersonRequest(BaseModel):
    person_id: int
    role: Optional[str] = None


class LinkPropertyRequest(BaseModel):
    property_id: int


class LinkActivityRequest(BaseModel):
    activity_id: int
