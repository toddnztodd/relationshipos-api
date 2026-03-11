"""Migration: Create activity_people join table and backfill from activities.person_id."""

import psycopg2

# Neon PostgreSQL (same as app/config.py)
DATABASE_URL = (
    "postgresql://neondb_owner:npg_HvYka2b5nPOZ"
    "@ep-autumn-sound-a7om89h2-pooler.ap-southeast-2.aws.neon.tech"
    "/neondb?sslmode=require"
)


def run():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. Create activity_people table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_people (
                id SERIAL PRIMARY KEY,
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                CONSTRAINT uq_activity_person UNIQUE (activity_id, person_id)
            );
        """)
        print("OK  Created activity_people table (or already exists)")

        # 2. Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS ix_activity_people_activity_id
            ON activity_people(activity_id);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS ix_activity_people_person_id
            ON activity_people(person_id);
        """)
        print("OK  Created indexes on activity_people")

        # 3. Backfill: insert activity_people rows for all existing activities with person_id
        cur.execute("""
            INSERT INTO activity_people (activity_id, person_id)
            SELECT id, person_id FROM activities
            WHERE person_id IS NOT NULL
            ON CONFLICT (activity_id, person_id) DO NOTHING;
        """)
        backfilled = cur.rowcount
        print(f"OK  Backfilled {backfilled} rows into activity_people from activities.person_id")

        conn.commit()
        print("Migration complete.")
    except Exception as e:
        conn.rollback()
        print(f"FAIL  Migration error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
