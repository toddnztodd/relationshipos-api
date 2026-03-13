"""Agent auto-detection and linking service.

Given a property and an agent name (optionally agency, phone, email), this
service will:
1. Normalise the agent name (strip whitespace, title case).
2. Try to find an existing Agent by normalised name + agency.
3. If found, link the property to that agent (set listing_agent_id).
4. If not found, create a new Agent, then link.
5. If phone/email are provided, update the agent record if those fields are
   currently empty (enrichment).
6. Return the Agent record.
"""
import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Agent, Property

logger = logging.getLogger(__name__)


def _normalise_name(name: str) -> str:
    """Strip whitespace and convert to title case."""
    return " ".join(name.strip().split()).title()


async def detect_and_link_agent(
    db: AsyncSession,
    property_id: int,
    agent_name: str,
    agency: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[Agent]:
    """Detect or create an agent and link it to the given property.

    Parameters
    ----------
    db : AsyncSession
        Active database session (caller is responsible for flush/commit).
    property_id : int
        The property to link the agent to.
    agent_name : str
        Raw agent name as captured from voice, PDF, or manual entry.
    agency : str, optional
        Agency name if known.
    phone : str, optional
        Phone number if known.
    email : str, optional
        Email address if known.

    Returns
    -------
    Agent or None
        The matched or newly-created Agent, or None if agent_name is empty.
    """
    if not agent_name or not agent_name.strip():
        return None

    normalised = _normalise_name(agent_name)
    agency_clean = agency.strip() if agency else None

    # ── Try to find existing agent ────────────────────────────────────────────
    query = select(Agent).where(func.lower(Agent.name) == normalised.lower())
    if agency_clean:
        query = query.where(func.lower(Agent.agency) == agency_clean.lower())

    result = await db.execute(query)
    agent = result.scalar_one_or_none()

    # If no match with agency, try name-only match (broader)
    if agent is None and agency_clean:
        result = await db.execute(
            select(Agent).where(func.lower(Agent.name) == normalised.lower())
        )
        agent = result.scalar_one_or_none()

    # ── Create new agent if not found ─────────────────────────────────────────
    if agent is None:
        agent = Agent(
            name=normalised,
            agency=agency_clean,
            phone=phone.strip() if phone else None,
            email=email.strip().lower() if email else None,
        )
        db.add(agent)
        await db.flush()
        await db.refresh(agent)
        logger.info("Created new agent: %s (agency=%s, id=%d)", normalised, agency_clean, agent.id)
    else:
        # ── Enrich existing agent with missing contact info ───────────────────
        updated = False
        if phone and not agent.phone:
            agent.phone = phone.strip()
            updated = True
        if email and not agent.email:
            agent.email = email.strip().lower()
            updated = True
        if agency_clean and not agent.agency:
            agent.agency = agency_clean
            updated = True
        if updated:
            await db.flush()
            await db.refresh(agent)
            logger.info("Enriched agent %d (%s) with new contact info", agent.id, normalised)

    # ── Link property to agent ────────────────────────────────────────────────
    prop_result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    prop = prop_result.scalar_one_or_none()
    if prop and prop.listing_agent_id != agent.id:
        prop.listing_agent_id = agent.id
        await db.flush()
        logger.info("Linked property %d to agent %d (%s)", property_id, agent.id, normalised)

    return agent
