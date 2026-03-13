-- Migration 025: Add optional address fields to the people table
-- Existing suburb column is retained; new fields add structured address support.

ALTER TABLE people
    ADD COLUMN IF NOT EXISTS address_line_1 VARCHAR(255),
    ADD COLUMN IF NOT EXISTS address_line_2 VARCHAR(255),
    ADD COLUMN IF NOT EXISTS city           VARCHAR(255),
    ADD COLUMN IF NOT EXISTS postcode       VARCHAR(20),
    ADD COLUMN IF NOT EXISTS latitude       DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS longitude      DOUBLE PRECISION;
