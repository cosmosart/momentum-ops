-- Migration 006: Add region column to price_daily
--
-- Stores the market region alongside ticker so that the yfinance symbol
-- can be derived from (ticker, region) without joining to tickers.
-- Existing rows default to 'US'; a follow-up UPDATE back-fills the
-- correct region from the tickers table.

BEGIN;

ALTER TABLE price_daily
    ADD COLUMN IF NOT EXISTS region VARCHAR(10) NOT NULL DEFAULT 'US';

-- Back-fill region from the tickers table for existing data
UPDATE price_daily pd
SET    region = t.market_region
FROM   tickers t
WHERE  t.symbol = pd.ticker
  AND  pd.region = 'US'
  AND  t.market_region <> 'US';

CREATE INDEX IF NOT EXISTS idx_price_daily_region ON price_daily(region);

COMMIT;
