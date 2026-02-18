-- DANGER: Run this first to clear old schema
DROP TABLE IF EXISTS analysis_info CASCADE;
DROP TABLE IF EXISTS price_daily CASCADE;
DROP TABLE IF EXISTS price_realtime CASCADE;

-- 1. Real-time Price (Timezone Critical)
CREATE TABLE price_realtime (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL, -- CHANGED to TIMESTAMPTZ
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, -- CHANGED
    UNIQUE(ticker, timestamp)
);

-- 2. Daily Price (Date is standard)
CREATE TABLE price_daily (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    adj_close DECIMAL(10, 2),
    volume BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, -- CHANGED
    UNIQUE(ticker, date)
);

-- 3. Analysis & Fundamentals (Includes your missing columns)
CREATE TABLE analysis_info (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    -- Technicals
    rsi DECIMAL(10, 4),
    macd DECIMAL(10, 4),
    macd_signal DECIMAL(10, 4),
    macd_hist DECIMAL(10, 4),
    -- Fundamentals
    analyst_rating SMALLINT, -- 0-4 scale
    dividend_yield DECIMAL(5, 2),
    market_cap BIGINT,
    avg_volume BIGINT,
    eps DECIMAL(10, 2),
    pe_ratio DECIMAL(10, 2),
    -- Predictions
    prediction_1d DECIMAL(10, 2),
    prediction_1w DECIMAL(10, 2),
    prediction_1m DECIMAL(10, 2),
    prediction_1y DECIMAL(10, 2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP, -- CHANGED
    UNIQUE(ticker, date)
);

-- Re-create indexes
CREATE INDEX idx_price_realtime_ticker ON price_realtime(ticker);
CREATE INDEX idx_price_realtime_timestamp ON price_realtime(timestamp);
CREATE INDEX idx_price_daily_ticker ON price_daily(ticker);
CREATE INDEX idx_price_daily_date ON price_daily(date);
CREATE INDEX idx_analysis_info_ticker ON analysis_info(ticker);
CREATE INDEX idx_analysis_info_date ON analysis_info(date);