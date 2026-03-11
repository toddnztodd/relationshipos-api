"""Pydantic schemas for Territory Intelligence."""

from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel


# ── Territory ────────────────────────────────────────────────────────────────


class TerritoryCreate(BaseModel):
    name: str
    type: Optional[str] = None  # core_territory / expansion_zone / tactical_route
    notes: Optional[str] = None
    boundary_data: Optional[Any] = None
    map_image_url: Optional[str] = None


class TerritoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    notes: Optional[str] = None
    boundary_data: Optional[Any] = None
    map_image_url: Optional[str] = None


class TerritoryResponse(BaseModel):
    id: int
    user_id: int
    name: str
    type: Optional[str] = None
    notes: Optional[str] = None
    boundary_data: Optional[Any] = None
    map_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TerritorySummaryStats(BaseModel):
    property_count: int = 0
    owners_known: int = 0
    relationships_known: int = 0
    recent_sales: int = 0
    recent_listings: int = 0
    signal_count: int = 0


class TerritoryListItem(TerritoryResponse):
    stats: TerritorySummaryStats = TerritorySummaryStats()


class TerritoryDetail(TerritoryResponse):
    stats: TerritorySummaryStats = TerritorySummaryStats()
    properties: list = []
    farming_programs: list = []


# ── Territory Property Link ──────────────────────────────────────────────────


class TerritoryPropertyCreate(BaseModel):
    property_id: int


class TerritoryPropertyResponse(BaseModel):
    id: int
    territory_id: int
    property_id: int
    linked_manually: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Coverage Activity ────────────────────────────────────────────────────────


class CoverageActivityCreate(BaseModel):
    territory_id: Optional[int] = None
    property_id: Optional[int] = None
    person_id: Optional[int] = None
    activity_type: str  # territory_intro / flyer_drop / magnet_drop / door_knock / welcome_touch / market_update
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None


class CoverageActivityResponse(BaseModel):
    id: int
    user_id: int
    territory_id: Optional[int] = None
    property_id: Optional[int] = None
    person_id: Optional[int] = None
    activity_type: str
    notes: Optional[str] = None
    completed_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class CoverageSummary(BaseModel):
    total_properties: int = 0
    properties_introduced: int = 0
    properties_with_relationship: int = 0
    properties_untouched: int = 0
    recent_activities: List[CoverageActivityResponse] = []


# ── Farming Program ──────────────────────────────────────────────────────────


class FarmingProgramCreate(BaseModel):
    territory_id: int
    title: str
    recurrence: Optional[str] = None
    next_due_date: Optional[date] = None
    notes: Optional[str] = None


class FarmingProgramUpdate(BaseModel):
    title: Optional[str] = None
    recurrence: Optional[str] = None
    next_due_date: Optional[date] = None
    last_completed_date: Optional[date] = None
    notes: Optional[str] = None


class FarmingProgramResponse(BaseModel):
    id: int
    user_id: int
    territory_id: int
    title: str
    recurrence: Optional[str] = None
    next_due_date: Optional[date] = None
    last_completed_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
