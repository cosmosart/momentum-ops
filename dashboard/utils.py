"""
Utility functions for the dashboard.
"""


def get_currency_info(ticker: str) -> tuple:
    """
    Get currency symbol and decimal places based on ticker.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        tuple: (currency_symbol, decimal_places)
    """
    ticker_upper = ticker.upper()
    
    # Japanese stocks (Tokyo Stock Exchange)
    if ticker_upper.endswith('.T'):
        return ('JPY', 0)
    
    # Korean stocks (KRX - Korea Exchange)
    if ticker_upper.endswith('.KS') or ticker_upper.endswith('.KQ'):
        return ('KRW', 0)
    
    # Indian stocks
    if ticker_upper.endswith('.NS') or ticker_upper.endswith('.BO'):
        return ('INR', 2)
    
    # Hong Kong stocks
    if ticker_upper.endswith('.HK'):
        return ('HKD', 2)
    
    # Default to USD
    return ('USD', 2)


def format_price(price: float, ticker: str) -> str:
    """
    Format price with appropriate currency symbol and decimal places.
    
    Args:
        price: Price value
        ticker: Stock ticker symbol
        
    Returns:
        str: Formatted price string
    """
    currency, decimals = get_currency_info(ticker)
    
    if decimals == 0:
        return f"{price:,.0f} {currency}"
    else:
        return f"{price:,.{decimals}f} {currency}"


def format_price_change(change: float, ticker: str) -> str:
    """
    Format price change with appropriate currency symbol and decimal places.
    
    Args:
        change: Price change value
        ticker: Stock ticker symbol
        
    Returns:
        str: Formatted price change string
    """
    currency, decimals = get_currency_info(ticker)
    
    if decimals == 0:
        return f"{change:,.0f} {currency}"
    else:
        return f"{change:,.{decimals}f} {currency}"
