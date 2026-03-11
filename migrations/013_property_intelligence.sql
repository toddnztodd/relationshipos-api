-- Migration 013: Property Intelligence Phase 1
-- Adds new property columns, buyer_interest table, property_owners table

BEGIN;

-- 1. Enum for last_listing_result
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'listing_result_type') THEN
        CREATE TYPE listing_result_type AS ENUM (
            'sold',
            'withdrawn',
            'expired',
            'private_sale',
            'unknown'
        );
    END IF;
END$$;

-- 2. Enum for buyer interest stage
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'buyer_interest_stage') THEN
        CREATE TYPE buyer_interest_stage AS ENUM (
            'seen',
            'interested',
            'hot',
            'offer',
            'purchased'
        );
    END IF;
END$$;

-- 3. Add new columns to properties table (all nullable, non-destructive)
ALTER TABLE properties ADD COLUMN IF NOT EXISTS land_size           TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS cv                  TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS last_sold_amount    TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS last_sold_date      DATE;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS current_listing_price TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS listing_url         TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS listing_agent       TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS listing_agency      TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS last_listed_date    DATE;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS last_listing_result listing_result_type;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS sellability         INTEGER;

-- 4. buyer_interest table
CREATE TABLE IF NOT EXISTS buyer_interest (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    person_id       INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    stage           buyer_interest_stage NOT NULL DEFAULT 'seen',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_buyer_interest UNIQUE (property_id, person_id)
);

CREATE INDEX IF NOT EXISTS ix_buyer_interest_property ON buyer_interest(property_id);
CREATE INDEX IF NOT EXISTS ix_buyer_interest_person   ON buyer_interest(person_id);
CREATE INDEX IF NOT EXISTS ix_buyer_interest_user     ON buyer_interest(user_id);

-- 5. property_owners table
CREATE TABLE IF NOT EXISTS property_owners (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    person_id       INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_property_owner UNIQUE (property_id, person_id)
);

CREATE INDEX IF NOT EXISTS ix_property_owners_property ON property_owners(property_id);
CREATE INDEX IF NOT EXISTS ix_property_owners_person   ON property_owners(person_id);
CREATE INDEX IF NOT EXISTS ix_property_owners_user     ON property_owners(user_id);

COMMIT;
