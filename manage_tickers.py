#!/usr/bin/env python3
"""
CLI tool for managing tickers.
Usage:
    python manage_tickers.py list              # List all tickers
    python manage_tickers.py add AAPL          # Add a ticker
    python manage_tickers.py add AAPL 1542.T   # Add multiple tickers
    python manage_tickers.py remove AAPL       # Deactivate a ticker
    python manage_tickers.py activate AAPL     # Reactivate a ticker
"""

import sys
import argparse
from database.db import Database


def list_tickers():
    """List all tickers and their status."""
    db = Database()
    if not db.connect():
        print("Error: Failed to connect to database")
        return 1
    
    try:
        all_tickers = db.get_all_tickers()
        active_tickers = db.get_active_tickers()
        
        if not all_tickers:
            print("No tickers configured.")
            return 0
        
        print("\n📋 Ticker List:")
        print("=" * 50)
        for ticker in all_tickers:
            status = "✅ Active" if ticker in active_tickers else "🔴 Inactive"
            print(f"  {ticker:<15} {status}")
        print("=" * 50)
        print(f"\nTotal: {len(all_tickers)} tickers ({len(active_tickers)} active, {len(all_tickers) - len(active_tickers)} inactive)")
        return 0
    finally:
        db.close()


def add_tickers(ticker_list):
    """Add one or more tickers."""
    db = Database()
    if not db.connect():
        print("Error: Failed to connect to database")
        return 1
    
    try:
        for ticker in ticker_list:
            ticker = ticker.upper().strip()
            db.add_ticker(ticker)
            print(f"✅ Added/Activated ticker: {ticker}")
        return 0
    finally:
        db.close()


def remove_tickers(ticker_list):
    """Deactivate one or more tickers."""
    db = Database()
    if not db.connect():
        print("Error: Failed to connect to database")
        return 1
    
    try:
        for ticker in ticker_list:
            ticker = ticker.upper().strip()
            db.deactivate_ticker(ticker)
            print(f"🔴 Deactivated ticker: {ticker}")
        return 0
    finally:
        db.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage stock tickers for momentum-ops",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                    # List all tickers
  %(prog)s add AAPL                # Add AAPL
  %(prog)s add AAPL GOOGL MSFT     # Add multiple tickers
  %(prog)s add 1542.T              # Add Japanese stock
  %(prog)s remove AAPL             # Deactivate AAPL
  %(prog)s activate AAPL           # Reactivate AAPL
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # List command
    subparsers.add_parser('list', help='List all tickers')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add one or more tickers')
    add_parser.add_argument('tickers', nargs='+', help='Ticker symbol(s) to add')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Deactivate one or more tickers')
    remove_parser.add_argument('tickers', nargs='+', help='Ticker symbol(s) to deactivate')
    
    # Activate command (alias for add)
    activate_parser = subparsers.add_parser('activate', help='Reactivate one or more tickers')
    activate_parser.add_argument('tickers', nargs='+', help='Ticker symbol(s) to reactivate')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'list':
        return list_tickers()
    elif args.command == 'add' or args.command == 'activate':
        return add_tickers(args.tickers)
    elif args.command == 'remove':
        return remove_tickers(args.tickers)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
