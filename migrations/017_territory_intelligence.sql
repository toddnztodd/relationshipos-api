-- Migration 017: Territory Intelligence Phase 1
-- Tables: territories, territory_properties, coverage_activities, farming_programs

-- ── Territories ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS territories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(30) CHECK (type IN ('core_territory', 'expansion_zone', 'tactical_route')),
    notes TEXT,
    boundary_data JSONB,
    map_image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_territories_user_id ON territories(user_id);

-- ── Territory-Property Links ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS territory_properties (
    id SERIAL PRIMARY KEY,
    territory_id INTEGER NOT NULL REFERENCES territories(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    linked_manually BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(territory_id, property_id)
);

CREATE INDEX IF NOT EXISTS ix_territory_properties_territory_id ON territory_properties(territory_id);
CREATE INDEX IF NOT EXISTS ix_territory_properties_property_id ON territory_properties(property_id);

-- ── Coverage Activities ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS coverage_activities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    territory_id INTEGER REFERENCES territories(id) ON DELETE SET NULL,
    property_id INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    activity_type VARCHAR(30) NOT NULL CHECK (activity_type IN (
        'territory_intro', 'flyer_drop', 'magnet_drop',
        'door_knock', 'welcome_touch', 'market_update'
    )),
    notes TEXT,
    completed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_coverage_activities_user_id ON coverage_activities(user_id);
CREATE INDEX IF NOT EXISTS ix_coverage_activities_territory_id ON coverage_activities(territory_id);
CREATE INDEX IF NOT EXISTS ix_coverage_activities_property_id ON coverage_activities(property_id);

-- ── Farming Programs ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS farming_programs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    territory_id INTEGER NOT NULL REFERENCES territories(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    recurrence VARCHAR(30),
    next_due_date DATE,
    last_completed_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_farming_programs_user_id ON farming_programs(user_id);
CREATE INDEX IF NOT EXISTS ix_farming_programs_territory_id ON farming_programs(territory_id);
