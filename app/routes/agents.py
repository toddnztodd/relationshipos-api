"""Agents Intelligence Layer — CRUD and search routes."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Agent, Property
from app.schemas.agent import (
    AgentCreate,
    AgentListItem,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
    AgentPropertySummary,
    AgentWithProperties,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/agents", tags=["Agents"])


# ── GET /agents — list all agents ─────────────────────────────────────────────


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all agents with property count and latest activity date.

    Property count and latest activity date are scoped to the current user's
    properties only.
    """
    # Sub-query: property count and latest created_at per agent for this user
    prop_stats = (
        select(
            Property.listing_agent_id,
            func.count(Property.id).label("property_count"),
            func.max(Property.created_at).label("latest_activity_date"),
        )
        .where(
            Property.user_id == current_user.id,
            Property.listing_agent_id.isnot(None),
        )
        .group_by(Property.listing_agent_id)
        .subquery()
    )

    query = (
        select(
            Agent,
            func.coalesce(prop_stats.c.property_count, 0).label("property_count"),
            prop_stats.c.latest_activity_date,
        )
        .outerjoin(prop_stats, Agent.id == prop_stats.c.listing_agent_id)
        .order_by(func.coalesce(prop_stats.c.property_count, 0).desc(), Agent.name)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    # Total count
    total_result = await db.execute(select(func.count(Agent.id)))
    total = total_result.scalar() or 0

    agents = []
    for agent, prop_count, latest_date in rows:
        agents.append(
            AgentListItem(
                id=agent.id,
                name=agent.name,
                agency=agent.agency,
                phone=agent.phone,
                email=agent.email,
                property_count=prop_count,
                latest_activity_date=latest_date,
                created_at=agent.created_at,
                updated_at=agent.updated_at,
            )
        )

    return AgentListResponse(agents=agents, total=total)


# ── GET /agents/search — search agents by name or agency ──────────────────────


@router.get("/search", response_model=AgentListResponse)
async def search_agents(
    q: str = Query(..., min_length=1, description="Search term for name or agency"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Search agents by name or agency (case-insensitive partial match)."""
    pattern = f"%{q.strip()}%"

    # Sub-query for property stats scoped to user
    prop_stats = (
        select(
            Property.listing_agent_id,
            func.count(Property.id).label("property_count"),
            func.max(Property.created_at).label("latest_activity_date"),
        )
        .where(
            Property.user_id == current_user.id,
            Property.listing_agent_id.isnot(None),
        )
        .group_by(Property.listing_agent_id)
        .subquery()
    )

    query = (
        select(
            Agent,
            func.coalesce(prop_stats.c.property_count, 0).label("property_count"),
            prop_stats.c.latest_activity_date,
        )
        .outerjoin(prop_stats, Agent.id == prop_stats.c.listing_agent_id)
        .where(
            or_(
                Agent.name.ilike(pattern),
                Agent.agency.ilike(pattern),
            )
        )
        .order_by(Agent.name)
        .limit(50)
    )

    result = await db.execute(query)
    rows = result.all()

    agents = []
    for agent, prop_count, latest_date in rows:
        agents.append(
            AgentListItem(
                id=agent.id,
                name=agent.name,
                agency=agent.agency,
                phone=agent.phone,
                email=agent.email,
                property_count=prop_count,
                latest_activity_date=latest_date,
                created_at=agent.created_at,
                updated_at=agent.updated_at,
            )
        )

    return AgentListResponse(agents=agents, total=len(agents))


# ── GET /agents/{agent_id} — agent detail with linked properties ──────────────


@router.get("/{agent_id}", response_model=AgentWithProperties)
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get agent detail with all linked properties for the current user."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Fetch user's properties linked to this agent
    prop_result = await db.execute(
        select(Property)
        .where(
            Property.listing_agent_id == agent_id,
            Property.user_id == current_user.id,
        )
        .order_by(Property.created_at.desc())
    )
    properties = prop_result.scalars().all()

    return AgentWithProperties(
        id=agent.id,
        name=agent.name,
        agency=agent.agency,
        phone=agent.phone,
        email=agent.email,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        properties=[AgentPropertySummary.model_validate(p) for p in properties],
    )


# ── POST /agents — create agent ──────────────────────────────────────────────


@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new agent record."""
    agent = Agent(
        name=body.name.strip().title(),
        agency=body.agency.strip() if body.agency else None,
        phone=body.phone.strip() if body.phone else None,
        email=body.email.strip().lower() if body.email else None,
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return AgentResponse.model_validate(agent)


# ── PUT /agents/{agent_id} — update agent ────────────────────────────────────


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update an existing agent record."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "name" and value:
            value = value.strip().title()
        elif key == "email" and value:
            value = value.strip().lower()
        elif isinstance(value, str):
            value = value.strip()
        setattr(agent, key, value)

    await db.flush()
    await db.refresh(agent)
    return AgentResponse.model_validate(agent)


# ── DELETE /agents/{agent_id} — delete agent ─────────────────────────────────


@router.delete("/{agent_id}", status_code=200)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete an agent. Properties linked to this agent will have listing_agent_id set to NULL."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    await db.flush()
    return {"detail": "Agent deleted", "id": agent_id}
