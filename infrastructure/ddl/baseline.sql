-- ==========================================================================
-- Momentum-Ops — Unified Baseline DDL
--
-- This file is the canonical schema definition.  It is applied on first
-- boot via docker-compose init and can be re-applied idempotently
-- (all statements use IF NOT EXISTS).
-- ==========================================================================

-- 1. TICKERS & METADATA ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tickers (
    id            SERIAL PRIMARY KEY,
    symbol        VARCHAR(20) UNIQUE NOT NULL,
    market_region VARCHAR(10) NOT NULL DEFAULT 'US',
    asset_class   VARCHAR(20) DEFAULT 'stock',
    is_active     BOOLEAN DEFAULT true,
    is_base_index BOOLEAN DEFAULT false,
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tickers_active ON tickers(is_active);
CREATE INDEX IF NOT EXISTS idx_tickers_market ON tickers(market_region);

-- 2. PRICE DATA ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS price_realtime (
    id         SERIAL PRIMARY KEY,
    ticker     VARCHAR(20) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    timestamp  TIMESTAMPTZ NOT NULL,
    open       DECIMAL(12, 4),
    high       DECIMAL(12, 4),
    low        DECIMAL(12, 4),
    close      DECIMAL(12, 4),
    volume     BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_price_realtime_ticker    ON price_realtime(ticker);
CREATE INDEX IF NOT EXISTS idx_price_realtime_timestamp ON price_realtime(timestamp);

CREATE TABLE IF NOT EXISTS price_daily (
    id         SERIAL PRIMARY KEY,
    ticker     VARCHAR(20) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    date       DATE NOT NULL,
    open       DECIMAL(12, 4),
    high       DECIMAL(12, 4),
    low        DECIMAL(12, 4),
    close      DECIMAL(12, 4),
    adj_close  DECIMAL(12, 4),
    volume     BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_price_daily_ticker ON price_daily(ticker);
CREATE INDEX IF NOT EXISTS idx_price_daily_date   ON price_daily(date);

-- 3. FUNDAMENTAL / SENTIMENT ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fundamental_daily (
    id                   SERIAL PRIMARY KEY,
    ticker               VARCHAR(20) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    date                 DATE NOT NULL,
    pe_ratio             DECIMAL(10, 4),
    eps                  DECIMAL(10, 4),
    dividend_yield       DECIMAL(10, 4),
    analyst_target_mean  DECIMAL(12, 2),
    analyst_rating_score DECIMAL(5, 2),
    created_at           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_fundamental_daily_ticker ON fundamental_daily(ticker);
CREATE INDEX IF NOT EXISTS idx_fundamental_daily_date   ON fundamental_daily(date);

-- 4. ML OUTPUTS ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_info (
    id                        SERIAL PRIMARY KEY,
    ticker                    VARCHAR(20) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    date                      DATE NOT NULL,
    rsi                       DECIMAL(10, 4),
    macd                      DECIMAL(10, 4),
    macd_signal               DECIMAL(10, 4),
    macd_hist                 DECIMAL(10, 4),
    bb_upper                  DECIMAL(12, 4),
    bb_middle                 DECIMAL(12, 4),
    bb_lower                  DECIMAL(12, 4),
    prob_active_1w            REAL,
    prob_conservative_1mo     REAL,
    prob_conservative_6mo     REAL,
    prob_experimental         REAL,
    features_active_1w        JSONB,
    features_conservative_1mo JSONB,
    features_conservative_6mo JSONB,
    features_experimental     JSONB,
    created_at                TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_analysis_info_ticker ON analysis_info(ticker);
CREATE INDEX IF NOT EXISTS idx_analysis_info_date   ON analysis_info(date);
