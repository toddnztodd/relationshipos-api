"""Migration: create community_entities, community_entity_people,
community_entity_properties, and community_entity_activities tables."""

import os
import psycopg2


def get_db_url():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        # Fallback to hardcoded Neon URL for local migration runs
        from app.config import _resolve_database_url
        url = _resolve_database_url()
    # psycopg2 needs postgresql:// not postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def run():
    url = get_db_url()
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating community_entity_type enum...")
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'community_entity_type') THEN
                CREATE TYPE community_entity_type AS ENUM (
                    'business',
                    'school',
                    'sport_club',
                    'community_group',
                    'charity',
                    'event_partner',
                    'other'
                );
            END IF;
        END$$;
    """)

    print("Creating community_entities table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS community_entities (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            type        community_entity_type NOT NULL DEFAULT 'other',
            location    TEXT,
            notes       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_community_entities_user_id ON community_entities(user_id);
    """)

    print("Creating community_entity_people join table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS community_entity_people (
            id                   SERIAL PRIMARY KEY,
            community_entity_id  INTEGER NOT NULL REFERENCES community_entities(id) ON DELETE CASCADE,
            person_id            INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
            role                 VARCHAR(255),
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_ce_person UNIQUE (community_entity_id, person_id)
        );
        CREATE INDEX IF NOT EXISTS ix_cep_entity_id ON community_entity_people(community_entity_id);
        CREATE INDEX IF NOT EXISTS ix_cep_person_id ON community_entity_people(person_id);
    """)

    print("Creating community_entity_properties join table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS community_entity_properties (
            id                   SERIAL PRIMARY KEY,
            community_entity_id  INTEGER NOT NULL REFERENCES community_entities(id) ON DELETE CASCADE,
            property_id          INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_ce_property UNIQUE (community_entity_id, property_id)
        );
        CREATE INDEX IF NOT EXISTS ix_cepr_entity_id ON community_entity_properties(community_entity_id);
        CREATE INDEX IF NOT EXISTS ix_cepr_property_id ON community_entity_properties(property_id);
    """)

    print("Creating community_entity_activities join table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS community_entity_activities (
            id                   SERIAL PRIMARY KEY,
            community_entity_id  INTEGER NOT NULL REFERENCES community_entities(id) ON DELETE CASCADE,
            activity_id          INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_ce_activity UNIQUE (community_entity_id, activity_id)
        );
        CREATE INDEX IF NOT EXISTS ix_cea_entity_id ON community_entity_activities(community_entity_id);
        CREATE INDEX IF NOT EXISTS ix_cea_activity_id ON community_entity_activities(activity_id);
    """)

    cur.close()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/ubuntu/relationshipos")
    run()
