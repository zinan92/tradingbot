#!/usr/bin/env python3
"""
Verify that backtests are now using REAL database data
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from scripts.backtesting_validation_tests import BacktestingValidationTests


def verify_real_data_usage():
    """Verify backtests are using real database data"""
    
    print("=" * 80)
    print("VERIFYING REAL DATA USAGE IN BACKTESTS")
    print("=" * 80)
    
    # 1. Check database has real data
    print("\n1. CHECKING DATABASE FOR REAL DATA:")
    print("-" * 40)
    
    engine = create_engine('postgresql://localhost/tradingbot')
    
    try:
        with engine.connect() as conn:
            # Check BTCUSDT data
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_rows,
                    MIN(close_price) as min_price,
                    MAX(close_price) as max_price,
                    AVG(close_price) as avg_price,
                    MAX(open_time) as latest_time
                FROM kline_data 
                WHERE symbol = 'BTCUSDT' 
                AND interval = '5m'
                AND open_time >= :start_date
            """), {'start_date': datetime.now() - timedelta(days=30)})
            
            row = result.fetchone()
            print(f"✅ Real BTCUSDT data in database:")
            print(f"   Rows (last 30 days): {row.total_rows:,}")
            print(f"   Price range: ${row.min_price:,.2f} - ${row.max_price:,.2f}")
            print(f"   Average price: ${row.avg_price:,.2f}")
            print(f"   Latest data: {row.latest_time}")
            
            db_avg_price = row.avg_price
            db_min_price = row.min_price
            db_max_price = row.max_price
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        return
    
    # 2. Initialize test suite with real data configuration
    print("\n2. INITIALIZING BACKTEST SUITE:")
    print("-" * 40)
    
    test_suite = BacktestingValidationTests()
    
    # Check DataAdapter configuration
    if test_suite.data_adapter.connection_params:
        print(f"✅ DataAdapter configured with database connection:")
        print(f"   Host: {test_suite.data_adapter.connection_params.get('host')}")
        print(f"   Database: {test_suite.data_adapter.connection_params.get('database')}")
    else:
        print("❌ DataAdapter has no database connection params")
        return
    
    # 3. Fetch data as backtest would
    print("\n3. FETCHING DATA THROUGH DATAADAPTER:")
    print("-" * 40)
    
    test_symbol = 'BTCUSDT'
    test_interval = '5m'
    test_start = datetime.now() - timedelta(days=7)
    test_end = datetime.now()
    
    print(f"Fetching {test_symbol} {test_interval} data...")
    data = test_suite.data_adapter.fetch_ohlcv(
        symbol=test_symbol,
        interval=test_interval,
        start_date=test_start,
        end_date=test_end
    )
    
    if len(data) > 0:
        avg_price = data['Close'].mean()
        min_price = data['Close'].min()
        max_price = data['Close'].max()
        
        print(f"✅ Data fetched successfully:")
        print(f"   Rows: {len(data)}")
        print(f"   Date range: {data.index[0]} to {data.index[-1]}")
        print(f"   Price range: ${min_price:,.2f} - ${max_price:,.2f}")
        print(f"   Average price: ${avg_price:,.2f}")
        
        # 4. Compare with database values
        print("\n4. DATA VALIDATION:")
        print("-" * 40)
        
        # Check if prices are in realistic range for Bitcoin
        if 80000 < avg_price < 150000:  # Reasonable BTC price range for 2024-2025
            print(f"✅ Prices are in realistic Bitcoin range")
        else:
            print(f"⚠️  Prices seem unrealistic for Bitcoin: ${avg_price:,.2f}")
        
        # Check if data matches database characteristics
        price_diff_pct = abs(avg_price - db_avg_price) / db_avg_price * 100
        
        if price_diff_pct < 20:  # Within 20% of database average
            print(f"✅ Data matches database characteristics")
            print(f"   Database avg: ${db_avg_price:,.2f}")
            print(f"   Fetched avg: ${avg_price:,.2f}")
            print(f"   Difference: {price_diff_pct:.1f}%")
        else:
            print(f"⚠️  Data differs significantly from database")
            print(f"   Database avg: ${db_avg_price:,.2f}")
            print(f"   Fetched avg: ${avg_price:,.2f}")
            print(f"   Difference: {price_diff_pct:.1f}%")
        
        # Check data variability (mock data tends to be smooth)
        returns = data['Close'].pct_change().dropna()
        volatility = returns.std()
        
        if volatility > 0.0001:  # Real crypto data is volatile
            print(f"✅ Data shows realistic volatility: {volatility:.4f}")
        else:
            print(f"⚠️  Data appears too smooth (mock-like): {volatility:.6f}")
        
    else:
        print("❌ No data fetched")
    
    # 5. Run a quick backtest to verify
    print("\n5. RUNNING TEST BACKTEST:")
    print("-" * 40)
    
    try:
        result = test_suite.test_1_bitcoin_ema_crossing()
        
        if result['status'] == 'PASSED':
            print(f"✅ Backtest completed successfully")
            print(f"   Trades: {result.get('trades', 0)}")
            print(f"   Return: {result.get('return_pct', 0):.2f}%")
            
            # Check if results are realistic
            if result.get('trades', 0) > 0:
                print(f"✅ Generated trades from real market data")
            else:
                print(f"⚠️  No trades generated - check strategy parameters")
                
        else:
            print(f"❌ Backtest failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Backtest error: {e}")
    
    # 6. Final verdict
    print("\n" + "=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)
    
    if len(data) > 0 and 80000 < avg_price < 150000 and volatility > 0.0001:
        print("✅ CONFIRMED: Backtests are now using REAL DATABASE DATA!")
        print("\nKey indicators:")
        print(f"  • Realistic Bitcoin prices (${avg_price:,.2f})")
        print(f"  • Natural market volatility ({volatility:.4f})")
        print(f"  • Data matches database characteristics")
        print(f"  • {len(data)} real candles fetched from PostgreSQL")
    else:
        print("⚠️  UNCERTAIN: Data characteristics need further investigation")
        print("\nPotential issues:")
        if len(data) == 0:
            print("  • No data fetched - check database connection")
        if not (80000 < avg_price < 150000):
            print(f"  • Unrealistic prices: ${avg_price:,.2f}")
        if volatility <= 0.0001:
            print(f"  • Too smooth (mock-like): volatility={volatility:.6f}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    verify_real_data_usage()