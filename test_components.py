#!/usr/bin/env python3
"""
Test script for momentum-ops components.
Validates core functionality without requiring database connection.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from models.models import calculate_indicators, generate_predictions


def test_indicators():
    """Test technical indicators calculation."""
    print("=" * 50)
    print("Testing Technical Indicators")
    print("=" * 50)
    
    # Create sample data
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 2)
    
    df = pd.DataFrame({
        'Date': dates,
        'Close': prices,
        'Open': prices - 1,
        'High': prices + 2,
        'Low': prices - 2,
        'Volume': np.random.randint(1000000, 10000000, 100)
    })
    
    # Calculate indicators
    indicators = calculate_indicators(df)
    
    # Validate
    assert not indicators.empty, "Indicators DataFrame should not be empty"
    assert 'RSI' in indicators.columns, "RSI column should exist"
    assert 'MACD' in indicators.columns, "MACD column should exist"
    assert 'MACD_signal' in indicators.columns, "MACD_signal column should exist"
    assert 'MACD_hist' in indicators.columns, "MACD_hist column should exist"
    
    print("✓ RSI calculation: PASSED")
    print("✓ MACD calculation: PASSED")
    print(f"  Latest RSI: {indicators.iloc[-1]['RSI']:.2f}")
    print(f"  Latest MACD: {indicators.iloc[-1]['MACD']:.4f}")
    print()


def test_predictions():
    """Test prediction generation."""
    print("=" * 50)
    print("Testing Predictions")
    print("=" * 50)
    
    # Create sample data
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 2)
    
    df = pd.DataFrame({
        'Date': dates,
        'Close': prices,
        'Open': prices - 1,
        'High': prices + 2,
        'Low': prices - 2,
        'Volume': np.random.randint(1000000, 10000000, 100)
    })
    
    # Generate predictions
    predictions = generate_predictions(df)
    
    # Validate
    assert predictions is not None, "Predictions should not be None"
    assert '1d' in predictions, "1d prediction should exist"
    assert '1w' in predictions, "1w prediction should exist"
    assert '1m' in predictions, "1m prediction should exist"
    assert '1y' in predictions, "1y prediction should exist"
    
    print("✓ Prediction generation: PASSED")
    print(f"  1-day forecast: ${predictions['1d']:.2f}")
    print(f"  1-week forecast: ${predictions['1w']:.2f}")
    print(f"  1-month forecast: ${predictions['1m']:.2f}")
    print(f"  1-year forecast: ${predictions['1y']:.2f}")
    print()


def test_data_fetcher():
    """Test data fetcher module."""
    print("=" * 50)
    print("Testing Data Fetcher")
    print("=" * 50)
    
    from ingestion.fetcher import DataFetcher
    
    # Create fetcher instance
    fetcher = DataFetcher('AAPL')
    assert fetcher.ticker == 'AAPL', "Ticker should be set correctly"
    
    print("✓ DataFetcher initialization: PASSED")
    print("  Note: Actual data fetching requires internet access")
    print()


def test_database_module():
    """Test database module."""
    print("=" * 50)
    print("Testing Database Module")
    print("=" * 50)
    
    from database.db import Database
    
    # Create database instance
    db = Database()
    assert db.host is not None, "Database host should be configured"
    assert db.database is not None, "Database name should be configured"
    
    print("✓ Database initialization: PASSED")
    print("  Note: Actual database operations require PostgreSQL")
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 50)
    print("MOMENTUM-OPS COMPONENT TESTS")
    print("=" * 50 + "\n")
    
    try:
        test_indicators()
        test_predictions()
        test_data_fetcher()
        test_database_module()
        
        print("=" * 50)
        print("ALL TESTS PASSED ✓")
        print("=" * 50)
        print("\nThe momentum-ops application is ready to use!")
        print("\nNext steps:")
        print("1. Set up PostgreSQL database")
        print("2. Configure .env file with database credentials")
        print("3. Run: docker-compose up -d")
        print("4. Access dashboard at: http://localhost:8501")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
