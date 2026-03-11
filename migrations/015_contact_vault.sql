-- Migration 015: Contact Vault System
-- Adds contact_status, vault_note, vaulted_at, original_source to people table.

ALTER TABLE people ADD COLUMN IF NOT EXISTS contact_status VARCHAR(20) NOT NULL DEFAULT 'active';

-- Add check constraint only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'chk_contact_status'
    ) THEN
        ALTER TABLE people ADD CONSTRAINT chk_contact_status
            CHECK (contact_status IN ('active', 'vaulted', 'private'));
    END IF;
END $$;

ALTER TABLE people ADD COLUMN IF NOT EXISTS vault_note TEXT;
ALTER TABLE people ADD COLUMN IF NOT EXISTS vaulted_at TIMESTAMPTZ;
ALTER TABLE people ADD COLUMN IF NOT EXISTS original_source VARCHAR(100);

-- Index for fast filtering by contact_status
CREATE INDEX IF NOT EXISTS ix_people_contact_status ON people(contact_status);
