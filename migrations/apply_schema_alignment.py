"""
Schema alignment migration — three non-destructive changes:

1. Make activities.person_id nullable
2. Expand InteractionType enum with new values
3. Add relationship_group_id to people

Run once against the Neon production database.
"""

import os
import re
import sys

import psycopg2

# ── Resolve the Neon connection string ────────────────────────────────────────

_NEON_DATABASE_URL = (
    "postgresql://neondb_owner:npg_HvYka2b5nPOZ"
    "@ep-autumn-sound-a7om89h2-pooler.ap-southeast-2.aws.neon.tech"
    "/neondb?sslmode=require"
)

env_url = os.environ.get("DATABASE_URL", "").strip()
if env_url and ("postgresql" in env_url or "postgres://" in env_url):
    raw_url = env_url
else:
    raw_url = _NEON_DATABASE_URL

# psycopg2 needs postgresql://, not postgresql+asyncpg://
raw_url = raw_url.replace("postgresql+asyncpg://", "postgresql://")
# Strip channel_binding if present
raw_url = re.sub(r"[&?]channel_binding=[^&]*", "", raw_url).rstrip("?").rstrip("&")

print(f"Connecting to: {raw_url[:60]}...")

conn = psycopg2.connect(raw_url)
conn.autocommit = True
cur = conn.cursor()

migrations = [
    # ── Change 1: Make activities.person_id nullable ──────────────────────────
    (
        "Make activities.person_id nullable",
        "ALTER TABLE activities ALTER COLUMN person_id DROP NOT NULL;",
    ),

    # ── Change 2: Expand InteractionType enum ─────────────────────────────────
    (
        "Add voice_note to interactiontype enum",
        "ALTER TYPE interactiontype ADD VALUE IF NOT EXISTS 'voice_note';",
    ),
    (
        "Add meeting_note to interactiontype enum",
        "ALTER TYPE interactiontype ADD VALUE IF NOT EXISTS 'meeting_note';",
    ),
    (
        "Add appraisal_note to interactiontype enum",
        "ALTER TYPE interactiontype ADD VALUE IF NOT EXISTS 'appraisal_note';",
    ),
    (
        "Add conversation_update to interactiontype enum",
        "ALTER TYPE interactiontype ADD VALUE IF NOT EXISTS 'conversation_update';",
    ),
    (
        "Add system_event to interactiontype enum",
        "ALTER TYPE interactiontype ADD VALUE IF NOT EXISTS 'system_event';",
    ),

    # ── Change 3: Add relationship_group_id to people ─────────────────────────
    (
        "Add relationship_group_id column to people",
        "ALTER TABLE people ADD COLUMN IF NOT EXISTS relationship_group_id INTEGER;",
    ),
]

success = 0
for label, sql in migrations:
    try:
        cur.execute(sql)
        print(f"  OK  {label}")
        success += 1
    except Exception as e:
        print(f"  ERR {label}: {e}", file=sys.stderr)

cur.close()
conn.close()

print(f"\n{success}/{len(migrations)} migrations applied successfully.")
if success < len(migrations):
    sys.exit(1)
