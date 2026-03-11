"""Migration: add preferred_contact_channel column to people table."""

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

sql = "ALTER TABLE people ADD COLUMN IF NOT EXISTS preferred_contact_channel VARCHAR(20);"
print(f"Executing: {sql}")
cur.execute(sql)
print("  OK")

cur.close()
conn.close()
print("\nMigration complete: preferred_contact_channel added to people.")
