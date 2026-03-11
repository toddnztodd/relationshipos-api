-- Migration 012: Community Entities
-- Creates community_entities table and three join tables

BEGIN;

-- Enum type for community entity categories
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

-- Main community_entities table
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

-- Join table: community_entities <-> people
CREATE TABLE IF NOT EXISTS community_entity_people (
    id                    SERIAL PRIMARY KEY,
    community_entity_id   INTEGER NOT NULL REFERENCES community_entities(id) ON DELETE CASCADE,
    person_id             INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    role                  VARCHAR(255),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ce_person UNIQUE (community_entity_id, person_id)
);

CREATE INDEX IF NOT EXISTS ix_ce_people_entity_id ON community_entity_people(community_entity_id);
CREATE INDEX IF NOT EXISTS ix_ce_people_person_id ON community_entity_people(person_id);

-- Join table: community_entities <-> properties
CREATE TABLE IF NOT EXISTS community_entity_properties (
    id                    SERIAL PRIMARY KEY,
    community_entity_id   INTEGER NOT NULL REFERENCES community_entities(id) ON DELETE CASCADE,
    property_id           INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ce_property UNIQUE (community_entity_id, property_id)
);

CREATE INDEX IF NOT EXISTS ix_ce_properties_entity_id ON community_entity_properties(community_entity_id);
CREATE INDEX IF NOT EXISTS ix_ce_properties_property_id ON community_entity_properties(property_id);

-- Join table: community_entities <-> activities
CREATE TABLE IF NOT EXISTS community_entity_activities (
    id                    SERIAL PRIMARY KEY,
    community_entity_id   INTEGER NOT NULL REFERENCES community_entities(id) ON DELETE CASCADE,
    activity_id           INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ce_activity UNIQUE (community_entity_id, activity_id)
);

CREATE INDEX IF NOT EXISTS ix_ce_activities_entity_id ON community_entity_activities(community_entity_id);
CREATE INDEX IF NOT EXISTS ix_ce_activities_activity_id ON community_entity_activities(activity_id);

COMMIT;
