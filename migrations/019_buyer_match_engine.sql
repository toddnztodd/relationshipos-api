-- Migration 019: Buyer Match Engine — extend buyer_interest with preference fields
-- Also add estimated_value and property_type to properties for scoring

-- Extend buyer_interest table with buyer preference fields
ALTER TABLE buyer_interest ADD COLUMN IF NOT EXISTS price_min NUMERIC NULLABLE;
ALTER TABLE buyer_interest ADD COLUMN IF NOT EXISTS price_max NUMERIC NULLABLE;
ALTER TABLE buyer_interest ADD COLUMN IF NOT EXISTS bedrooms_min INTEGER NULLABLE;
ALTER TABLE buyer_interest ADD COLUMN IF NOT EXISTS bathrooms_min INTEGER NULLABLE;
ALTER TABLE buyer_interest ADD COLUMN IF NOT EXISTS land_size_min INTEGER NULLABLE;
ALTER TABLE buyer_interest ADD COLUMN IF NOT EXISTS preferred_suburbs TEXT[] NULLABLE;
ALTER TABLE buyer_interest ADD COLUMN IF NOT EXISTS property_type_preference VARCHAR(100) NULLABLE;
ALTER TABLE buyer_interest ADD COLUMN IF NOT EXISTS special_features TEXT[] NULLABLE;

-- Extend properties table with fields needed for scoring
ALTER TABLE properties ADD COLUMN IF NOT EXISTS estimated_value NUMERIC NULLABLE;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS property_type VARCHAR(100) NULLABLE;

-- Index for match engine performance
CREATE INDEX IF NOT EXISTS ix_buyer_interest_stage ON buyer_interest(stage);
CREATE INDEX IF NOT EXISTS ix_buyer_interest_user_stage ON buyer_interest(user_id, stage);
CREATE INDEX IF NOT EXISTS ix_properties_suburb ON properties(suburb);
CREATE INDEX IF NOT EXISTS ix_properties_sellability ON properties(sellability);
