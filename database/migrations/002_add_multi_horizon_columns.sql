-- Migration: Add multi-horizon directional probability columns
-- Run this against an existing momentum_db to add the new columns.
--
-- Usage:
--   psql -h <host> -U momentum_user -d momentum_db -f database/migrations/002_add_multi_horizon_columns.sql

ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS direction_prob_1d  DECIMAL(6, 4);
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS direction_prob_1w  DECIMAL(6, 4);
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS direction_prob_1mo DECIMAL(6, 4);
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS direction_prob_6mo DECIMAL(6, 4);
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS direction_prob_1y  DECIMAL(6, 4);

-- Backfill the 1w column from the legacy direction_probability column
UPDATE analysis_info
   SET direction_prob_1w = direction_probability
 WHERE direction_prob_1w IS NULL
   AND direction_probability IS NOT NULL;
