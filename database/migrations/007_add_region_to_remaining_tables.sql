-- Migration 007: Add region column to price_realtime, fundamental_daily, analysis_info
-- (price_daily was handled in migration 006)

BEGIN;

-- ── price_realtime ───────────────────────────────────────────────────────────
ALTER TABLE price_realtime
    ADD COLUMN IF NOT EXISTS region VARCHAR(10) NOT NULL DEFAULT 'US';

UPDATE price_realtime pr
   SET region = t.market_region
  FROM tickers t
 WHERE pr.ticker = t.symbol
   AND pr.region = 'US'
   AND t.market_region <> 'US';

CREATE INDEX IF NOT EXISTS idx_price_realtime_region
    ON price_realtime (region);

-- ── fundamental_daily ────────────────────────────────────────────────────────
ALTER TABLE fundamental_daily
    ADD COLUMN IF NOT EXISTS region VARCHAR(10) NOT NULL DEFAULT 'US';

UPDATE fundamental_daily fd
   SET region = t.market_region
  FROM tickers t
 WHERE fd.ticker = t.symbol
   AND fd.region = 'US'
   AND t.market_region <> 'US';

CREATE INDEX IF NOT EXISTS idx_fundamental_daily_region
    ON fundamental_daily (region);

-- ── analysis_info ────────────────────────────────────────────────────────────
ALTER TABLE analysis_info
    ADD COLUMN IF NOT EXISTS region VARCHAR(10) NOT NULL DEFAULT 'US';

UPDATE analysis_info ai
   SET region = t.market_region
  FROM tickers t
 WHERE ai.ticker = t.symbol
   AND ai.region = 'US'
   AND t.market_region <> 'US';

CREATE INDEX IF NOT EXISTS idx_analysis_info_region
    ON analysis_info (region);

COMMIT;
