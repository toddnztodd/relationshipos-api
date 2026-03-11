-- Migration 020: Referral Program Tracking

-- Add referral fields to people table
ALTER TABLE people
    ADD COLUMN IF NOT EXISTS referral_member BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS referral_reward_amount NUMERIC(10,2) NOT NULL DEFAULT 250,
    ADD COLUMN IF NOT EXISTS referral_email_sent_at TIMESTAMPTZ;

-- Create referrals table
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referrer_person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    referred_person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    referral_status VARCHAR(30) NOT NULL DEFAULT 'registered'
        CHECK (referral_status IN ('registered', 'referral_received', 'listing_secured', 'sold', 'closed')),
    reward_amount NUMERIC(10,2) NOT NULL DEFAULT 250,
    reward_status VARCHAR(20) NOT NULL DEFAULT 'none'
        CHECK (reward_status IN ('none', 'pending', 'earned', 'paid')),
    reward_paid_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (referrer_person_id, referred_person_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_referrals_user_id ON referrals(user_id);
CREATE INDEX IF NOT EXISTS ix_referrals_referrer ON referrals(referrer_person_id);
CREATE INDEX IF NOT EXISTS ix_referrals_referred ON referrals(referred_person_id);
CREATE INDEX IF NOT EXISTS ix_referrals_status ON referrals(referral_status);
CREATE INDEX IF NOT EXISTS ix_people_referral_member ON people(referral_member);
