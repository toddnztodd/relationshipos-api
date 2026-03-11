"""
Migration: Create rapport_anchors table and anchor_status enum.

Non-destructive — uses IF NOT EXISTS guards.
"""

import os
import re
import sys

import psycopg2

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

raw_url = raw_url.replace("postgresql+asyncpg://", "postgresql://")
raw_url = re.sub(r"[&?]channel_binding=[^&]*", "", raw_url).rstrip("?").rstrip("&")

print(f"Connecting to: {raw_url[:60]}...")

conn = psycopg2.connect(raw_url)
conn.autocommit = True
cur = conn.cursor()

migrations = [
    (
        "Create anchor_status enum",
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'anchor_status') THEN
                CREATE TYPE anchor_status AS ENUM ('suggested', 'accepted', 'dismissed');
            END IF;
        END$$;
        """,
    ),
    (
        "Create rapport_anchors table",
        """
        CREATE TABLE IF NOT EXISTS rapport_anchors (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
            relationship_group_id INTEGER,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            anchor_text TEXT NOT NULL,
            anchor_type VARCHAR(20) NOT NULL DEFAULT 'individual',
            status anchor_status NOT NULL DEFAULT 'suggested'
        );
        """,
    ),
    (
        "Create index on rapport_anchors.person_id",
        "CREATE INDEX IF NOT EXISTS ix_rapport_anchors_person_id ON rapport_anchors (person_id);",
    ),
    (
        "Create index on rapport_anchors.user_id",
        "CREATE INDEX IF NOT EXISTS ix_rapport_anchors_user_id ON rapport_anchors (user_id);",
    ),
    (
        "Create index on rapport_anchors.activity_id",
        "CREATE INDEX IF NOT EXISTS ix_rapport_anchors_activity_id ON rapport_anchors (activity_id);",
    ),
    (
        "Create index on rapport_anchors.relationship_group_id",
        "CREATE INDEX IF NOT EXISTS ix_rapport_anchors_rel_group ON rapport_anchors (relationship_group_id);",
    ),
    (
        "Create index on rapport_anchors.status",
        "CREATE INDEX IF NOT EXISTS ix_rapport_anchors_status ON rapport_anchors (status);",
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
