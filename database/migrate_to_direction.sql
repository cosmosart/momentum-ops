-- Migration: Replace price-prediction columns with directional-probability columns.
-- Run this against an existing momentum_db that still has the old schema.
--
-- Usage:  psql -U momentum_user -d momentum_db -f database/migrate_to_direction.sql

BEGIN;

-- 1. Drop old prediction columns
ALTER TABLE analysis_info
    DROP COLUMN IF EXISTS prediction_1d,
    DROP COLUMN IF EXISTS prediction_1w,
    DROP COLUMN IF EXISTS prediction_1m,
    DROP COLUMN IF EXISTS prediction_1y;

-- 2. Add new columns
ALTER TABLE analysis_info
    ADD COLUMN IF NOT EXISTS bb_upper              DECIMAL(12, 4),
    ADD COLUMN IF NOT EXISTS bb_middle             DECIMAL(12, 4),
    ADD COLUMN IF NOT EXISTS bb_lower              DECIMAL(12, 4),
    ADD COLUMN IF NOT EXISTS direction_probability DECIMAL(6, 4);

COMMIT;
