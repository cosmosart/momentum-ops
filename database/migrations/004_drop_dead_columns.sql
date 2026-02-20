-- Migration 004: Drop all dead / legacy probability columns
--
-- The four-model architecture uses ONLY:
--   prob_active_1w, prob_conservative_1mo, prob_conservative_6mo, prob_experimental
--
-- Everything else is orphaned — no code writes to or reads from these columns.
--
-- Usage:
--   psql -h <host> -U momentum_user -d momentum_db \
--        -f database/migrations/004_drop_dead_columns.sql

BEGIN;

-- Legacy single-model columns (MultiHorizonPredictor — removed from codebase)
ALTER TABLE analysis_info DROP COLUMN IF EXISTS direction_probability;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS direction_prob_1d;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS direction_prob_1w;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS direction_prob_1mo;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS direction_prob_6mo;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS direction_prob_1y;

-- Old multi-strategy headline columns (no longer used)
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_conservative;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_active;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_experimental;

-- Old per-strategy × per-horizon matrix (replaced by four targeted models)
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_conservative_1d;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_conservative_1w;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_conservative_1mo;  -- kept as targeted model column
-- NOTE: prob_conservative_1mo and prob_conservative_6mo are the NEW columns;
--       the ones below are the OLD ones that may exist from migration 003 (original).
--       IF NOT EXISTS / DROP IF EXISTS makes this idempotent.
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_conservative_1y;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_active_1d;
-- NOTE: prob_active_1w is the NEW targeted column — do NOT drop it.
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_active_1mo;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_active_6mo;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_active_1y;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_experimental_1d;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_experimental_1w;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_experimental_1mo;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_experimental_6mo;
ALTER TABLE analysis_info DROP COLUMN IF EXISTS prob_experimental_1y;

COMMIT;
