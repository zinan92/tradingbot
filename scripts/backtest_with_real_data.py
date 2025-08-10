#!/usr/bin/env python3
"""
Run backtest with REAL database data
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.backtesting.backtest_engine import BacktestEngine
from src.application.backtesting.strategies.ema_cross_strategy import EMACrossStrategy


def run_real_data_backtest():
    """Run backtest using real data from database"""
    
    print("=" * 80)
    print("BACKTEST WITH REAL DATABASE DATA")
    print("=" * 80)
    
    # Connect directly to database
    engine = create_engine('postgresql://localhost/tradingbot')
    
    # Configuration
    symbol = "BTCUSDT"
    interval = "5m"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    print(f"\nConfiguration:")
    print(f"  Symbol: {symbol}")
    print(f"  Interval: {interval}")
    print(f"  Period: {start_date.date()} to {end_date.date()}")
    
    # Fetch real data from database
    query = """
    SELECT 
        open_time as timestamp,
        open_price as "Open",
        high_price as "High",
        low_price as "Low",
        close_price as "Close",
        volume as "Volume"
    FROM kline_data
    WHERE symbol = %(symbol)s
      AND interval = %(interval)s
      AND open_time >= %(start)s
      AND open_time <= %(end)s
    ORDER BY open_time
    """
    
    print(f"\nFetching real data from database...")
    data = pd.read_sql_query(
        query, 
        engine,
        params={
            'symbol': symbol,
            'interval': interval,
            'start': start_date,
            'end': end_date
        },
        parse_dates=['timestamp'],
        index_col='timestamp'
    )
    
    print(f"✅ Loaded {len(data)} candles from database")
    print(f"   Date range: {data.index[0]} to {data.index[-1]}")
    print(f"   Price range: ${data['Close'].min():,.2f} - ${data['Close'].max():,.2f}")
    print(f"   Average price: ${data['Close'].mean():,.2f}")
    
    # Show sample of real data
    print(f"\nSample of real data (last 5 candles):")
    for idx, row in data.tail(5).iterrows():
        print(f"   {idx}: Close=${row['Close']:,.2f}, Volume={row['Volume']:,.0f}")
    
    # Strategy parameters
    strategy_params = {
        'fast_period': 12,
        'slow_period': 26,
        'stop_loss_pct': 0.02,
        'take_profit_pct': 0.05,
        'position_size': 0.95
    }
    
    # Run backtest with real data
    print(f"\nRunning backtest with REAL data...")
    backtest_engine = BacktestEngine()
    
    results = backtest_engine.run_backtest(
        data=data,
        strategy_class=EMACrossStrategy,
        initial_cash=1000000,  # $1M to handle Bitcoin prices
        commission=0.001,
        **strategy_params
    )
    
    # Display realistic results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS (WITH REAL DATA)")
    print("=" * 80)
    
    stats = results.stats
    
    print("\n📊 PERFORMANCE:")
    print(f"  Initial Capital:     $1,000,000.00")
    print(f"  Final Equity:        ${stats.get('Equity Final [$]', 0):,.2f}")
    print(f"  Total Return:        {stats.get('Return [%]', 0):.2f}%")
    print(f"  Buy & Hold Return:   {stats.get('Buy & Hold Return [%]', 0):.2f}%")
    
    print("\n📈 RISK METRICS:")
    print(f"  Sharpe Ratio:        {stats.get('Sharpe Ratio', 0):.3f}")
    print(f"  Max Drawdown:        {stats.get('Max. Drawdown [%]', 0):.2f}%")
    print(f"  Win Rate:            {stats.get('Win Rate [%]', 0):.2f}%")
    
    print("\n📊 TRADE STATISTICS:")
    print(f"  Total Trades:        {stats.get('# Trades', 0)}")
    print(f"  Avg Trade:           {stats.get('Avg. Trade [%]', 0):.2f}%")
    print(f"  Best Trade:          {stats.get('Best Trade [%]', 0):.2f}%")
    print(f"  Worst Trade:         {stats.get('Worst Trade [%]', 0):.2f}%")
    print(f"  Profit Factor:       {stats.get('Profit Factor', 0):.2f}")
    
    # Comparison
    print("\n📊 DATA COMPARISON:")
    print(f"  Data Source:         REAL PostgreSQL Database")
    print(f"  Realistic Prices:    ✅ (${data['Close'].min():,.0f} - ${data['Close'].max():,.0f})")
    print(f"  Actual Market Data:  ✅")
    
    print("\n" + "=" * 80)
    print("Note: These results use REAL market data from your database.")
    print("Compare with mock data results to see the difference!")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    try:
        results = run_real_data_backtest()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure your PostgreSQL database is running and accessible.")