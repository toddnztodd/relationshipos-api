"""RelationshipOS — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routes import auth, people, properties, activities, email_threads, dashboard
from app.routes.person_dates import person_dates_router, dates_router
from app.routes.person_relationships import person_router as relationships_person_router
from app.routes.person_relationships import top_router as relationships_top_router
from app.routes.property_people import router as property_people_router
from app.routes.property_people import top_router as property_people_top_router
from app.routes.important_dates import person_router as dates_person_router
from app.routes.important_dates import top_router as dates_top_router
from app.routes.checklist import router as checklist_router
from app.routes.checklist import top_router as checklist_top_router
from app.routes.person_properties import router as person_properties_router
from app.routes.door_knocks import router as door_knocks_router
from app.routes.weekly_tracking import router as weekly_tracking_router
from app.routes.rapport_anchors import person_router as rapport_person_router
from app.routes.rapport_anchors import top_router as rapport_top_router
from app.routes.relationship_summaries import person_router as summary_person_router
from app.routes.relationship_summaries import top_router as summary_top_router
from app.routes.open_homes import router as open_homes_router
from app.routes.context_nodes import (
    router as context_nodes_router,
    person_router as context_person_router,
    property_router as context_property_router,
    suggestion_router as context_suggestion_router,
)
from app.routes.community_entities import (
    router as community_entities_router,
    people_router as ce_people_router,
    properties_router as ce_properties_router,
)
from app.routes.buyer_interest import (
    property_router as buyer_interest_property_router,
    top_router as buyer_interest_top_router,
)
from app.routes.property_owners import router as property_owners_router
from app.routes.property_intelligence import router as property_intelligence_router
from app.routes.signals import (
    router as signals_router,
    property_router as signals_property_router,
    person_router as signals_person_router,
)
from app.routes.listing_checklists import (
    property_router as listing_checklist_property_router,
    checklists_router as listing_checklists_router,
    items_router as listing_checklist_items_router,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables. Shutdown: nothing special."""
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "A mobile-first relationship intelligence operating system. "
        "People are the central object — the system builds memory, structure and intelligence."
    ),
    lifespan=lifespan,
    redirect_slashes=False,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers under /api/v1 ───────────────────────────────────────────────

API_PREFIX = "/api/v1"

# Core CRUD
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(people.router, prefix=API_PREFIX)
app.include_router(properties.router, prefix=API_PREFIX)
app.include_router(activities.router, prefix=API_PREFIX)
app.include_router(email_threads.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)

# Person dates (v1 — legacy)
app.include_router(person_dates_router, prefix=API_PREFIX)
app.include_router(dates_router, prefix=API_PREFIX)

# Relationships (Charlotte's Web)
app.include_router(relationships_person_router, prefix=API_PREFIX)  # /people/{id}/relationships
app.include_router(relationships_top_router, prefix=API_PREFIX)     # /relationships

# Property-Person links
app.include_router(property_people_router, prefix=API_PREFIX)       # /properties/{id}/people, /people/{id}/properties
app.include_router(property_people_top_router, prefix=API_PREFIX)   # /property-people/{id}

# Important dates (v2)
app.include_router(dates_person_router, prefix=API_PREFIX)          # /people/{id}/important-dates, /people/{id}/dates
app.include_router(dates_top_router, prefix=API_PREFIX)             # /dates/{id}

# Listing checklist
app.include_router(checklist_router, prefix=API_PREFIX)             # /properties/{id}/checklist
app.include_router(checklist_top_router, prefix=API_PREFIX)         # /checklist-items/{id}

# Person properties (properties linked to a person)
app.include_router(person_properties_router, prefix=API_PREFIX)     # /people/{id}/properties

# Door knock sessions
app.include_router(door_knocks_router, prefix=API_PREFIX)           # /door-knocks/

# Weekly BASICS tracking + user annual goals
app.include_router(weekly_tracking_router, prefix=API_PREFIX)       # /weekly-tracking/, /users/goals

# Rapport anchors
app.include_router(rapport_person_router, prefix=API_PREFIX)        # /people/{id}/rapport-anchors
app.include_router(rapport_top_router, prefix=API_PREFIX)           # /rapport-anchors/{id}

# Relationship summaries
app.include_router(summary_person_router, prefix=API_PREFIX)        # /people/{id}/relationship-summary
app.include_router(summary_top_router, prefix=API_PREFIX)           # /relationship-summaries/{id}

# Open homes
app.include_router(open_homes_router, prefix=API_PREFIX)            # /open-homes/{id}/vendor-update

# Context nodes
app.include_router(context_nodes_router, prefix=API_PREFIX)         # /context-nodes/
app.include_router(context_person_router, prefix=API_PREFIX)        # /people/{id}/context-nodes
app.include_router(context_property_router, prefix=API_PREFIX)      # /properties/{id}/context-nodes
app.include_router(context_suggestion_router, prefix=API_PREFIX)    # /context-node-suggestions/{id}

# Community entities
app.include_router(community_entities_router, prefix=API_PREFIX)    # /community-entities/
app.include_router(ce_people_router, prefix=API_PREFIX)             # /people/{id}/community-entities
app.include_router(ce_properties_router, prefix=API_PREFIX)         # /properties/{id}/community-entities

# Property Intelligence (buyer interest, owners, match, parse-voice)
app.include_router(buyer_interest_property_router, prefix=API_PREFIX)  # /properties/{id}/buyer-interest
app.include_router(buyer_interest_top_router, prefix=API_PREFIX)       # /buyer-interest/{id}
app.include_router(property_owners_router, prefix=API_PREFIX)          # /properties/{id}/owners
app.include_router(property_intelligence_router, prefix=API_PREFIX)    # /properties/match, /properties/parse-voice

# Opportunity Signals
app.include_router(signals_router, prefix=API_PREFIX)                  # /signals, /signals/detect
app.include_router(signals_property_router, prefix=API_PREFIX)         # /properties/{id}/signals
app.include_router(signals_person_router, prefix=API_PREFIX)           # /people/{id}/signals

# Listing Checklist V2 (structured 12-phase)
app.include_router(listing_checklist_property_router, prefix=API_PREFIX)  # /properties/{id}/listing-checklist
app.include_router(listing_checklists_router, prefix=API_PREFIX)          # /checklists/{id}/phase, /checklists/{id}
app.include_router(listing_checklist_items_router, prefix=API_PREFIX)     # /checklist-items-v2/{id}


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.api_route("/health", methods=["GET", "HEAD"], tags=["Health"])
async def health_check():
    return {"status": "healthy"}


@app.get("/debug/db", tags=["Debug"])
async def debug_db():
    """Temporary endpoint to verify which database is in use."""
    from app.config import _resolve_database_url
    import os
    url = _resolve_database_url()
    env_url = os.environ.get("DATABASE_URL", "NOT SET")

    def mask(u: str) -> str:
        if "@" in u:
            parts = u.split("@")
            return parts[0][:15] + "...@" + parts[1]
        return u[:30] + "..."

    return {
        "resolved_url": mask(url),
        "env_var_set": env_url != "NOT SET",
        "env_var_value": mask(env_url) if env_url != "NOT SET" else "NOT SET",
        "is_postgres": "postgresql" in url or "postgres://" in url,
        "is_neon": "neon.tech" in url,
    }
