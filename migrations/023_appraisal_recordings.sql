-- Migration 023: Add appraisal_recordings table
-- Stores audio recordings, transcripts, and AI-extracted intelligence from property appraisals.

CREATE TABLE IF NOT EXISTS appraisal_recordings (
    id               SERIAL PRIMARY KEY,
    property_id      INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    audio_url        TEXT,
    transcript       TEXT,
    summary          TEXT,
    extracted_intelligence JSONB,
    detected_signals       JSONB,
    duration_seconds INTEGER
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_appraisal_recordings_property_id ON appraisal_recordings(property_id);
CREATE INDEX IF NOT EXISTS idx_appraisal_recordings_user_id     ON appraisal_recordings(user_id);
