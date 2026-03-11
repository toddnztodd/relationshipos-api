"""Migration: create summary_status enum and relationship_summaries table."""

import os
import ssl
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

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
conn.autocommit = True
cur = conn.cursor()

statements = [
    # 1. Create the summary_status enum
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'summary_status') THEN
            CREATE TYPE summary_status AS ENUM ('suggested', 'accepted', 'dismissed');
        END IF;
    END
    $$;
    """,
    # 2. Create the relationship_summaries table
    """
    CREATE TABLE IF NOT EXISTS relationship_summaries (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        summary_text TEXT NOT NULL,
        status summary_status NOT NULL DEFAULT 'suggested',
        is_update BOOLEAN NOT NULL DEFAULT false
    );
    """,
    # 3. Add indexes
    "CREATE INDEX IF NOT EXISTS ix_relationship_summaries_person_id ON relationship_summaries(person_id);",
    "CREATE INDEX IF NOT EXISTS ix_relationship_summaries_user_id ON relationship_summaries(user_id);",
    "CREATE INDEX IF NOT EXISTS ix_relationship_summaries_status ON relationship_summaries(status);",
]

for sql in statements:
    print(f"Executing: {sql.strip()[:80]}...")
    cur.execute(sql)
    print("  OK")

cur.close()
conn.close()
print("\nMigration complete: relationship_summaries table created.")
