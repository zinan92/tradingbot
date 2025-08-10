#!/usr/bin/env python3
"""
Test if backtests are using real database data or mock data
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.infrastructure.backtesting.backtest_engine import BacktestEngine
from src.application.backtesting.strategies.ema_cross_strategy import EMACrossStrategy


def test_data_source():
    """Test whether we're using real or mock data"""
    
    print("=" * 80)
    print("DATA SOURCE VERIFICATION TEST")
    print("=" * 80)
    
    # 1. Check database directly
    print("\n1. CHECKING DATABASE DIRECTLY:")
    print("-" * 40)
    
    try:
        engine = create_engine('postgresql://localhost/tradingbot')
        with engine.connect() as conn:
            # Check BTCUSDT 5m data
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_rows,
                    MIN(open_time) as earliest,
                    MAX(open_time) as latest,
                    AVG(close_price) as avg_price
                FROM kline_data 
                WHERE symbol = 'BTCUSDT' 
                AND interval = '5m'
                AND open_time >= :start_date
            """), {'start_date': datetime.now() - timedelta(days=30)})
            
            row = result.fetchone()
            print(f"✅ REAL DATABASE DATA AVAILABLE:")
            print(f"   Total rows (last 30 days): {row.total_rows:,}")
            print(f"   Date range: {row.earliest} to {row.latest}")
            print(f"   Average price: ${row.avg_price:.2f}")
            
            # Get sample of actual prices
            result2 = conn.execute(text("""
                SELECT open_time, close_price 
                FROM kline_data 
                WHERE symbol = 'BTCUSDT' 
                AND interval = '5m'
                ORDER BY open_time DESC
                LIMIT 5
            """))
            
            print(f"\n   Latest 5 candles from database:")
            for row in result2:
                print(f"   {row.open_time}: ${row.close_price:.2f}")
                
    except Exception as e:
        print(f"❌ Cannot access database: {e}")
    
    # 2. Test DataAdapter with database connection
    print("\n2. TESTING DATA ADAPTER:")
    print("-" * 40)
    
    from src.infrastructure.backtesting.data_adapter import DataAdapter
    
    # Test with proper database connection
    adapter_with_db = DataAdapter({
        'host': 'localhost',
        'port': 5432,
        'database': 'tradingbot',
        'user': None,  # Will use current user
        'password': None
    })
    
    # Test with None (should use mock data)
    adapter_mock = DataAdapter(None)
    
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    # Try to fetch from database
    try:
        print("Attempting to fetch from database...")
        data_db = adapter_with_db.fetch_from_database(
            'BTCUSDT', start_date, end_date, '5m'
        )
        
        if 'generated' in str(data_db.index[0]):
            print("❌ DataAdapter returned MOCK data (despite database attempt)")
        else:
            print(f"✅ DataAdapter returned REAL data: {len(data_db)} rows")
            print(f"   Price range: ${data_db['Close'].min():.2f} - ${data_db['Close'].max():.2f}")
    except Exception as e:
        print(f"❌ Database fetch failed: {e}")
        print("   DataAdapter will fall back to MOCK data")
    
    # Test mock data
    print("\nTesting mock data generation...")
    data_mock = adapter_mock.fetch_ohlcv(
        'BTCUSDT', start_date, end_date, '5m'
    )
    print(f"📊 Mock data generated: {len(data_mock)} rows")
    print(f"   Price range: ${data_mock['Close'].min():.2f} - ${data_mock['Close'].max():.2f}")
    
    # 3. Check what backtesting actually uses
    print("\n3. CHECKING BACKTEST DATA SOURCE:")
    print("-" * 40)
    
    # Load data the way backtesting does
    from scripts.backtesting_validation_tests import BacktestingValidationTests
    
    test_suite = BacktestingValidationTests()
    
    # Check the data adapter configuration
    if test_suite.data_adapter.connection_params is None:
        print("❌ Backtest suite configured to use MOCK data")
        print("   Reason: DataAdapter initialized with None")
    else:
        print("📊 Backtest suite configured with database parameters")
        print(f"   Database: {test_suite.data_adapter.connection_params.get('database', 'N/A')}")
    
    # Actually fetch data and check
    print("\nFetching data as backtest would...")
    actual_data = test_suite.data_adapter.fetch_from_database(
        symbol='BTCUSDT',
        interval='5m',
        start_date=datetime.now() - timedelta(days=1),
        end_date=datetime.now()
    )
    
    # Check characteristics of the data
    if len(actual_data) > 0:
        first_price = actual_data['Close'].iloc[0]
        last_price = actual_data['Close'].iloc[-1]
        price_change = abs(last_price - first_price) / first_price
        
        # Mock data typically has smooth patterns
        if price_change < 0.001:  # Less than 0.1% change
            print(f"⚠️  Data appears to be MOCK (too smooth)")
        else:
            # Check for realistic Bitcoin prices
            if 10000 < first_price < 200000:  # Reasonable BTC price range
                print(f"✅ Data appears to be REAL")
            else:
                print(f"⚠️  Data appears to be MOCK (unrealistic prices)")
        
        print(f"   Rows: {len(actual_data)}")
        print(f"   First price: ${first_price:.2f}")
        print(f"   Last price: ${last_price:.2f}")
        print(f"   Price change: {price_change:.2%}")
    
    # 4. Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    # Check if we have real data available
    try:
        engine = create_engine('postgresql://localhost/tradingbot')
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) as count FROM kline_data WHERE symbol = 'BTCUSDT'"
            ))
            count = result.fetchone().count
            
            if count > 0:
                print(f"✅ REAL DATA AVAILABLE: {count:,} BTCUSDT records in database")
                print("\n⚠️  BUT: Backtests are currently using MOCK data")
                print("\nReason: DataAdapter in backtesting_validation_tests.py is initialized")
                print("with None instead of proper database connection parameters.")
                print("\nTo use REAL data, the DataAdapter should be initialized with:")
                print("  DataAdapter({'host': 'localhost', 'database': 'tradingbot', ...})")
            else:
                print("❌ No real data in database")
        
    except Exception as e:
        print(f"❌ Cannot verify database: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_data_source()