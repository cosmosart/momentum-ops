-- Migration 003: Add four targeted strategy-model probability columns
--
-- Exactly four XGBoost models run in the single container:
--   1. prob_active_1w         — high-risk short-term momentum
--   2. prob_conservative_1mo  — foundational mid-term
--   3. prob_conservative_6mo  — foundational long-term
--   4. prob_experimental      — sandbox for testing
--
-- Usage:
--   psql -h <host> -U momentum_user -d momentum_db \
--        -f database/migrations/003_add_multi_strategy_columns.sql

ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS prob_active_1w         REAL;
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS prob_conservative_1mo  REAL;
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS prob_conservative_6mo  REAL;
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS prob_experimental      REAL;
