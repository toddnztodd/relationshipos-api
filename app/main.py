"""RelationshipOS — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routes import auth, people, properties, activities, email_threads, dashboard
from app.routes.person_dates import person_dates_router, dates_router
from app.routes.person_relationships import router as person_relationships_router
from app.routes.property_people import router as property_people_router
from app.routes.important_dates import router as important_dates_router
from app.routes.checklist import router as checklist_router

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

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(people.router, prefix=API_PREFIX)
app.include_router(properties.router, prefix=API_PREFIX)
app.include_router(activities.router, prefix=API_PREFIX)
app.include_router(email_threads.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(person_dates_router, prefix=API_PREFIX)
app.include_router(dates_router, prefix=API_PREFIX)
# New feature routers
app.include_router(person_relationships_router, prefix=API_PREFIX)
app.include_router(property_people_router, prefix=API_PREFIX)
app.include_router(important_dates_router, prefix=API_PREFIX)
app.include_router(checklist_router, prefix=API_PREFIX)


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


@app.get("/debug/db", tags=["Debug"])
async def debug_db():
    """Temporary endpoint to verify which database is in use."""
    from app.config import _resolve_database_url
    import os
    url = _resolve_database_url()
    env_url = os.environ.get("DATABASE_URL", "NOT SET")
    # Mask credentials in output
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
