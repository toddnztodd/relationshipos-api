-- Migration 016: Listing Checklists with Phases and Items
-- Adds structured 12-phase listing checklists with sale method templates

-- Listing checklists table
CREATE TABLE IF NOT EXISTS listing_checklists (
    id SERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sale_method VARCHAR(20) NOT NULL CHECK (sale_method IN ('priced', 'by_negotiation', 'deadline', 'auction')),
    current_phase INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Checklist phases
CREATE TABLE IF NOT EXISTS checklist_phases (
    id SERIAL PRIMARY KEY,
    checklist_id INTEGER NOT NULL REFERENCES listing_checklists(id) ON DELETE CASCADE,
    phase_number INTEGER NOT NULL,
    phase_name VARCHAR(100) NOT NULL,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    UNIQUE(checklist_id, phase_number)
);

-- Checklist items
CREATE TABLE IF NOT EXISTS checklist_items (
    id SERIAL PRIMARY KEY,
    checklist_id INTEGER NOT NULL REFERENCES listing_checklists(id) ON DELETE CASCADE,
    phase_number INTEGER NOT NULL,
    item_text VARCHAR(500) NOT NULL,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    due_date DATE,
    note TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_listing_checklists_property_id ON listing_checklists(property_id);
CREATE INDEX IF NOT EXISTS ix_listing_checklists_user_id ON listing_checklists(user_id);
CREATE INDEX IF NOT EXISTS ix_checklist_phases_checklist_id ON checklist_phases(checklist_id);
CREATE INDEX IF NOT EXISTS ix_checklist_items_checklist_id ON checklist_items(checklist_id);
