"""Migration: create suggested_outreach table."""

import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL or "postgresql" not in DATABASE_URL:
    DATABASE_URL = (
        "postgresql://neondb_owner:npg_HvYka2b5nPOZ"
        "@ep-autumn-sound-a7om89h2-pooler.ap-southeast-2.aws.neon.tech"
        "/neondb?sslmode=require"
    )
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
conn.autocommit = True
cur = conn.cursor()

statements = [
    # Create the suggested_outreach table
    """
    CREATE TABLE IF NOT EXISTS suggested_outreach (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        message_text TEXT NOT NULL,
        is_current BOOLEAN NOT NULL DEFAULT true
    );
    """,
    "CREATE INDEX IF NOT EXISTS ix_suggested_outreach_person_id ON suggested_outreach(person_id);",
    "CREATE INDEX IF NOT EXISTS ix_suggested_outreach_user_id ON suggested_outreach(user_id);",
    "CREATE INDEX IF NOT EXISTS ix_suggested_outreach_current ON suggested_outreach(person_id, user_id, is_current) WHERE is_current = true;",
]

for sql in statements:
    print(f"Executing: {sql.strip()[:80]}...")
    cur.execute(sql)
    print("  OK")

cur.close()
conn.close()
print("\nMigration complete: suggested_outreach table created.")
