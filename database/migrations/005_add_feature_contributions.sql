-- Migration 005: Add JSONB columns for per-model local feature contributions
--
-- Each column stores the top-3 TreeSHAP contributors for a specific model's
-- latest prediction, e.g.:
--   {"rsi_14": 0.045, "macd_hist": -0.021, "bb_pctb": 0.012}
--
-- The dashboard reads these columns to render a per-model SHAP bar chart
-- WITHOUT needing access to the XGBoost model files (DB-only bridge).
--
-- Usage:
--   psql -h <host> -U momentum_user -d momentum_db \
--        -f database/migrations/005_add_feature_contributions.sql

ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS features_active_1w         JSONB;
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS features_conservative_1mo  JSONB;
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS features_conservative_6mo  JSONB;
ALTER TABLE analysis_info ADD COLUMN IF NOT EXISTS features_experimental      JSONB;
