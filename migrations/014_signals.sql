-- Migration 014: Opportunity Signals Phase 1
-- Creates signal_type and signal_source_type enums, signals table with indexes.

-- Signal type enum
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signal_type') THEN
        CREATE TYPE signal_type AS ENUM (
            'listing_opportunity',
            'buyer_match',
            'vendor_pressure',
            'relationship_cooling',
            'relationship_warming',
            'community_cluster'
        );
    END IF;
END $$;

-- Signal source type enum
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signal_source_type') THEN
        CREATE TYPE signal_source_type AS ENUM (
            'voice_note',
            'email',
            'meeting',
            'system'
        );
    END IF;
END $$;

-- Signals table
CREATE TABLE IF NOT EXISTS signals (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    signal_type     signal_type NOT NULL,
    entity_type     VARCHAR(50) NOT NULL,   -- 'person', 'property', 'community'
    entity_id       INTEGER NOT NULL,
    confidence      FLOAT NOT NULL DEFAULT 0.0,
    source_contact_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    source_type     signal_source_type NOT NULL DEFAULT 'system',
    description     TEXT NOT NULL DEFAULT '',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS ix_signals_user_id ON signals(user_id);
CREATE INDEX IF NOT EXISTS ix_signals_entity ON signals(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_signals_active ON signals(user_id, is_active);
CREATE INDEX IF NOT EXISTS ix_signals_type ON signals(signal_type);

-- Unique constraint to prevent duplicate active signals of same type for same entity
CREATE UNIQUE INDEX IF NOT EXISTS uq_signals_active_entity
    ON signals(user_id, signal_type, entity_type, entity_id)
    WHERE is_active = TRUE;
