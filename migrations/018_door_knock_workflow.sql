-- Migration 018: Door Knock Workflow
-- Tables: door_knock_sessions, door_knock_entries, follow_up_tasks

-- Door knock sessions
CREATE TABLE IF NOT EXISTS door_knock_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    territory_id INTEGER REFERENCES territories(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    total_knocks INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_door_knock_sessions_user_id ON door_knock_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_door_knock_sessions_territory_id ON door_knock_sessions(territory_id);

-- Door knock entries
CREATE TABLE IF NOT EXISTS door_knock_entries (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES door_knock_sessions(id) ON DELETE CASCADE,
    property_id INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    property_address VARCHAR(500) NOT NULL,
    knock_result VARCHAR(30) NOT NULL CHECK (knock_result IN (
        'door_knocked', 'spoke_to_owner', 'spoke_to_occupant',
        'no_answer', 'contact_captured'
    )),
    contact_name VARCHAR(255),
    contact_phone VARCHAR(50),
    interest_level VARCHAR(30) CHECK (interest_level IN (
        'not_interested', 'neutral', 'possibly_selling', 'actively_considering'
    )),
    voice_note_transcript TEXT,
    notes TEXT,
    created_contact_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    knocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_door_knock_entries_session_id ON door_knock_entries(session_id);
CREATE INDEX IF NOT EXISTS ix_door_knock_entries_property_id ON door_knock_entries(property_id);
CREATE INDEX IF NOT EXISTS ix_door_knock_entries_created_contact_id ON door_knock_entries(created_contact_id);

-- Follow-up tasks
CREATE TABLE IF NOT EXISTS follow_up_tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    related_property_id INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    related_person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    related_session_id INTEGER REFERENCES door_knock_sessions(id) ON DELETE SET NULL,
    due_date DATE,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_follow_up_tasks_user_id ON follow_up_tasks(user_id);
CREATE INDEX IF NOT EXISTS ix_follow_up_tasks_due_date ON follow_up_tasks(due_date);
CREATE INDEX IF NOT EXISTS ix_follow_up_tasks_is_completed ON follow_up_tasks(is_completed);
