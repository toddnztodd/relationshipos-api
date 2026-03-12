-- Migration 021: Add phone_numbers (JSONB) and date_of_birth (DATE) to people table
-- Run once against the production database.

ALTER TABLE people
    ADD COLUMN IF NOT EXISTS phone_numbers JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS date_of_birth DATE;
