-- Migration 022: Add address intelligence fields to properties table
-- Adds formatted_address, postcode, latitude, longitude
-- suburb and city already exist — no changes needed for those

ALTER TABLE properties
    ADD COLUMN IF NOT EXISTS formatted_address TEXT,
    ADD COLUMN IF NOT EXISTS postcode          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS latitude          DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS longitude         DOUBLE PRECISION;
