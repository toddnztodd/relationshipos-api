-- Migration 024: Add agents table and link to properties
-- Creates an agents intelligence layer for tracking competing/collaborating agents.

CREATE TABLE IF NOT EXISTS agents (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    agency      VARCHAR(255),
    phone       VARCHAR(100),
    email       VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add listing_agent_id FK on properties (nullable, keeps existing text fields)
ALTER TABLE properties
    ADD COLUMN IF NOT EXISTS listing_agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_agents_name   ON agents(name);
CREATE INDEX IF NOT EXISTS idx_agents_agency ON agents(agency);
CREATE INDEX IF NOT EXISTS idx_properties_listing_agent_id ON properties(listing_agent_id);
