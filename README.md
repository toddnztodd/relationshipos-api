# RelationshipOS — Backend API

A mobile-first relationship intelligence operating system. People are the central object — the system builds memory, structure and intelligence.

Built with **FastAPI**, **async SQLAlchemy**, **Pydantic v2**, and **JWT authentication**.

---

## Architecture

```
relationshipos/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py             # Pydantic-settings configuration
│   ├── database.py           # Async SQLAlchemy engine & session
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py         # SQLAlchemy ORM models (User, Person, Property, Activity, EmailThread)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py           # Auth & user schemas
│   │   ├── person.py         # People engine schemas
│   │   ├── property.py       # Property intelligence schemas
│   │   ├── activity.py       # Interaction logging schemas
│   │   ├── email_thread.py   # Email thread schemas
│   │   └── dashboard.py      # Dashboard, kiosk, and AI suggestion schemas
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py           # Register & login endpoints
│   │   ├── people.py         # People CRUD + search + filtering
│   │   ├── properties.py     # Properties CRUD + filtering
│   │   ├── activities.py     # Activities CRUD + quick-log
│   │   ├── email_threads.py  # Email threads CRUD
│   │   └── dashboard.py      # Dashboard aggregation, kiosk check-in, AI suggestions
│   └── services/
│       ├── __init__.py
│       ├── auth.py           # JWT token management & password hashing
│       └── cadence.py        # Cadence tracking & drift detection logic
├── alembic/                  # Database migration configuration
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── alembic.ini
├── seed_data.py              # Sample data for testing
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Clone and install dependencies

```bash
cd relationshipos
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings (defaults work for SQLite development)
```

### 3. Seed the database (optional but recommended)

```bash
python seed_data.py
```

This creates sample users, people, properties, activities, and email threads. Test credentials:

| User | Email | Password |
|------|-------|----------|
| Primary | `todd@eves.co.nz` | `password123` |
| Demo | `demo@relationshipos.app` | `demo1234` |

### 4. Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Explore the API

- **Interactive docs (Swagger UI):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health check:** http://localhost:8000/health

---

## Database

### Default: SQLite (development)

Works out of the box with no additional setup. Database file is created at `./relationshipos.db`.

### PostgreSQL (production)

1. Create a PostgreSQL database:
   ```sql
   CREATE DATABASE relationshipos;
   ```

2. Update `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/relationshipos
   ```

3. Update `alembic.ini` with the same connection string.

### Migrations with Alembic

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

---

## API Endpoints

All endpoints are prefixed with `/api/v1`.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Login and receive JWT token |

### People

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/people/` | Create a person |
| GET | `/api/v1/people/` | List people (with filtering, sorting, pagination) |
| GET | `/api/v1/people/search?phone=...` | Search by phone number |
| GET | `/api/v1/people/{id}` | Get person with cadence status |
| PUT | `/api/v1/people/{id}` | Update a person |
| DELETE | `/api/v1/people/{id}` | Delete a person |

**Filters:** `tier`, `relationship_type`, `suburb`, `is_relationship_asset`, `search`
**Sorting:** `sort_by` (created_at, first_name, last_name, tier, influence_score, updated_at), `sort_order` (asc, desc)

### Properties

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/properties/` | Create a property |
| GET | `/api/v1/properties/` | List properties (with filtering) |
| GET | `/api/v1/properties/{id}` | Get a property |
| PUT | `/api/v1/properties/{id}` | Update a property |
| DELETE | `/api/v1/properties/{id}` | Delete a property |

**Filters:** `suburb`, `bedrooms_min`, `bedrooms_max`, `has_pool`, `search`

### Activities

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/activities/` | Create an activity |
| POST | `/api/v1/activities/quick-log` | Quick-log (optimised for mobile speed) |
| GET | `/api/v1/activities/` | List activities (with filtering) |
| GET | `/api/v1/activities/{id}` | Get an activity |
| PUT | `/api/v1/activities/{id}` | Update an activity |
| DELETE | `/api/v1/activities/{id}` | Delete an activity |

**Filters:** `person_id`, `property_id`, `interaction_type`, `is_meaningful`

### Email Threads

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/email-threads/` | Create an email thread |
| GET | `/api/v1/email-threads/` | List email threads |
| GET | `/api/v1/email-threads/{id}` | Get an email thread |
| PUT | `/api/v1/email-threads/{id}` | Update an email thread |
| DELETE | `/api/v1/email-threads/{id}` | Delete an email thread |

**Note:** Email thread creation requires the linked person to have both `is_relationship_asset` and `email_sync_enabled` set to `true`.

### Open Home Kiosk

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/open-home/checkin` | Kiosk check-in (find/create person + log attendance) |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/dashboard` | Full execution dashboard aggregation |

Returns:
- **A-tier drifting:** A-tier relationships with no meaningful interaction in 30+ days
- **Due for contact:** People approaching their cadence deadline within 7 days
- **Callbacks needed:** Open home attendees from the last 7 days without a callback logged
- **Repeat attendees:** People who have attended more than one open home
- **Cadence statuses:** Green/amber/red status for every person

### AI Suggestions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/ai/suggestions` | Mock AI suggestions (stub) |

---

## Cadence Logic

Cadence tracking determines how frequently each person should be contacted based on their tier:

| Tier | Window | Green | Amber | Red |
|------|--------|-------|-------|-----|
| A | 30 days | Within 30 days | Days 24–30 | Over 30 days |
| B | 60 days | Within 60 days | Days 54–60 | Over 60 days |
| C | 90 days | Within 90 days | Days 84–90 | Over 90 days |

Only **meaningful** interactions (`is_meaningful = true`) count toward cadence tracking.

---

## Interaction Types

| Type | Description |
|------|-------------|
| `open_home_attendance` | Person attended an open home event |
| `open_home_callback` | Follow-up call after open home attendance |
| `phone_call` | General phone call |
| `text_message` | Text/SMS message |
| `door_knock` | In-person door knock |
| `coffee_meeting` | Face-to-face coffee meeting |
| `email_conversation` | Email exchange |

---

## Authentication

All endpoints (except `/api/v1/auth/register`, `/api/v1/auth/login`, `/`, `/health`) require a JWT bearer token.

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123", "full_name": "Test User"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret123"}'

# Use the token
curl http://localhost:8000/api/v1/people/ \
  -H "Authorization: Bearer <your-token>"
```

---

## Development

```bash
# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run seed data
python seed_data.py
```

---

## License

Proprietary — RelationshipOS.
