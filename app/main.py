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
