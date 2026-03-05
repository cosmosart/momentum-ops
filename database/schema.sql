-- ==============================================================================
-- 1. TICKERS & METADATA
-- ==============================================================================
CREATE TABLE IF NOT EXISTS tickers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,       -- Expanded to 20 for complex index tickers (e.g., ^M-WD)
    market_region VARCHAR(10) NOT NULL,       -- 'KR', 'JP', 'US', 'GLOBAL'
    asset_class VARCHAR(20) DEFAULT 'stock',  -- 'stock', 'etf', 'index'
    is_active BOOLEAN DEFAULT true,           -- Determines if real-time fetching is enabled
    is_base_index BOOLEAN DEFAULT false,      -- Identifies foundational indices (S&P500, Nikkei, KODEX)
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tickers_active ON tickers(is_active);
CREATE INDEX IF NOT EXISTS idx_tickers_market ON tickers(market_region);

-- ==============================================================================
-- 2. PRICE DATA (TIME SERIES)
-- ==============================================================================
-- Stores high-frequency data for active trading (e.g., 1m/5m Korean market data)
CREATE TABLE IF NOT EXISTS price_realtime (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(12, 4),
    high DECIMAL(12, 4),
    low DECIMAL(12, 4),
    close DECIMAL(12, 4),
    volume BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_price_realtime_ticker ON price_realtime(ticker);
CREATE INDEX IF NOT EXISTS idx_price_realtime_timestamp ON price_realtime(timestamp);

-- Stores daily aggregated price data for foundational trends and backtesting
CREATE TABLE IF NOT EXISTS price_daily (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    date DATE NOT NULL,
    open DECIMAL(12, 4),
    high DECIMAL(12, 4),
    low DECIMAL(12, 4),
    close DECIMAL(12, 4),
    adj_close DECIMAL(12, 4),
    volume BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_price_daily_ticker ON price_daily(ticker);
CREATE INDEX IF NOT EXISTS idx_price_daily_date ON price_daily(date);

-- ==============================================================================
-- 3. FUNDAMENTAL & SENTIMENT DATA (NEW)
-- ==============================================================================
-- Stores the new ML features (Value + Analyst Sentiment)
CREATE TABLE IF NOT EXISTS fundamental_daily (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    date DATE NOT NULL,
    pe_ratio DECIMAL(10, 4),
    eps DECIMAL(10, 4),
    dividend_yield DECIMAL(10, 4),
    analyst_target_mean DECIMAL(12, 2),       -- Wisdom of crowds target price
    analyst_rating_score DECIMAL(5, 2),       -- e.g., 1.0 (Strong Buy) to 5.0 (Strong Sell)
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_fundamental_daily_ticker ON fundamental_daily(ticker);
CREATE INDEX IF NOT EXISTS idx_fundamental_daily_date ON fundamental_daily(date);

-- ==============================================================================
-- 4. MACHINE LEARNING OUTPUTS
-- ==============================================================================
-- Stores technical indicators, ML probabilities, and local explanations (SHAP)
CREATE TABLE IF NOT EXISTS analysis_info (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    date DATE NOT NULL,
    
    -- Technical Features
    rsi DECIMAL(10, 4),
    macd DECIMAL(10, 4),
    macd_signal DECIMAL(10, 4),
    macd_hist DECIMAL(10, 4),
    bb_upper DECIMAL(12, 4),
    bb_middle DECIMAL(12, 4),
    bb_lower DECIMAL(12, 4),
    
    -- Targeted Strategy Probabilities
    prob_active_1w REAL,               -- High-risk short-term momentum
    prob_conservative_1mo REAL,        -- Foundational mid-term
    prob_conservative_6mo REAL,        -- Foundational long-term
    prob_experimental REAL,            -- Next-business-day directional
    
    -- Interpretability (SHAP values)
    features_active_1w JSONB,
    features_conservative_1mo JSONB,
    features_conservative_6mo JSONB,
    features_experimental JSONB,
    
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_analysis_info_ticker ON analysis_info(ticker);
CREATE INDEX IF NOT EXISTS idx_analysis_info_date ON analysis_info(date);