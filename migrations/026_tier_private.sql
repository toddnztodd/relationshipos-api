-- Migration 026: Add 'Private' to the tierenum PostgreSQL enum type
-- ALTER TYPE ... ADD VALUE is safe and does not require a table rewrite.
ALTER TYPE tierenum ADD VALUE IF NOT EXISTS 'Private';
