-- Create database schema for momentum-ops

-- Table: price_realtime
-- Stores real-time price data for stocks
CREATE TABLE IF NOT EXISTS price_realtime (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- Table: analysis_info
-- Stores technical analysis indicators and predictions
CREATE TABLE IF NOT EXISTS analysis_info (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    rsi DECIMAL(10, 4),
    macd DECIMAL(10, 4),
    macd_signal DECIMAL(10, 4),
    macd_hist DECIMAL(10, 4),
    prediction_1d DECIMAL(10, 2),
    prediction_1w DECIMAL(10, 2),
    prediction_1m DECIMAL(10, 2),
    prediction_1y DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_price_realtime_ticker ON price_realtime(ticker);
CREATE INDEX IF NOT EXISTS idx_price_realtime_timestamp ON price_realtime(timestamp);
CREATE INDEX IF NOT EXISTS idx_price_daily_ticker ON price_daily(ticker);
CREATE INDEX IF NOT EXISTS idx_price_daily_date ON price_daily(date);
CREATE INDEX IF NOT EXISTS idx_analysis_info_ticker ON analysis_info(ticker);
CREATE INDEX IF NOT EXISTS idx_analysis_info_date ON analysis_info(date);
