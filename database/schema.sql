-- Create database schema for momentum-ops

-- Table: price_realtime
-- Stores real-time price data for stocks
CREATE TABLE IF NOT EXISTS price_realtime (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, timestamp)
);

-- Table: price_daily
-- Stores daily aggregated price data
CREATE TABLE IF NOT EXISTS price_daily (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    adj_close DECIMAL(10, 2),
    volume BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- Table: analysis_info
-- Stores technical indicators and directional-probability output.
-- Four targeted strategy models (single container, multi-model inference):
--   prob_active_1w         — high-risk short-term momentum
--   prob_conservative_1mo  — foundational mid-term
--   prob_conservative_6mo  — foundational long-term
--   prob_experimental      — next-business-day directional prediction
CREATE TABLE IF NOT EXISTS analysis_info (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    rsi DECIMAL(10, 4),
    macd DECIMAL(10, 4),
    macd_signal DECIMAL(10, 4),
    macd_hist DECIMAL(10, 4),
    bb_upper DECIMAL(12, 4),
    bb_middle DECIMAL(12, 4),
    bb_lower DECIMAL(12, 4),
    -- Four targeted strategy-model probabilities
    prob_active_1w         REAL,
    prob_conservative_1mo  REAL,
    prob_conservative_6mo  REAL,
    prob_experimental      REAL,
    -- Per-model local feature contributions (top-3 TreeSHAP values)
    features_active_1w         JSONB,
    features_conservative_1mo  JSONB,
    features_conservative_6mo  JSONB,
    features_experimental      JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE TABLE IF NOT EXISTS tickers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_price_realtime_ticker ON price_realtime(ticker);
CREATE INDEX IF NOT EXISTS idx_price_realtime_timestamp ON price_realtime(timestamp);
CREATE INDEX IF NOT EXISTS idx_price_daily_ticker ON price_daily(ticker);
CREATE INDEX IF NOT EXISTS idx_price_daily_date ON price_daily(date);
CREATE INDEX IF NOT EXISTS idx_analysis_info_ticker ON analysis_info(ticker);
CREATE INDEX IF NOT EXISTS idx_analysis_info_date ON analysis_info(date);
CREATE INDEX IF NOT EXISTS idx_tickers_active ON tickers(is_active);
