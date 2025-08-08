#!/usr/bin/env python3
"""
Run backtest using Daily ATR Grid Strategy
Compares results with 1-hour ATR to show improvement
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from backtesting import Backtest
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

from src.infrastructure.backtesting.strategies.simple_atr_grid import SimpleATRGridStrategy
from src.infrastructure.backtesting.strategies.daily_atr_grid import DailyATRGridStrategy


def load_data(symbol, days=365):
    """Load historical data from database"""
    db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    engine = create_engine(db_url)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
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
      AND interval = '1h'
      AND open_time >= %(start_date)s
      AND open_time <= %(end_date)s
    ORDER BY open_time
    """
    
    df = pd.read_sql(
        query,
        engine,
        params={
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date
        },
        parse_dates=['timestamp']
    )
    
    if not df.empty:
        df.set_index('timestamp', inplace=True)
    
    return df


def run_comparison(symbol, data):
    """Run both strategies and compare results"""
    
    # Determine initial capital based on symbol
    if symbol == 'BTCUSDT':
        initial_capital = 1000000
        atr_mult = 0.5  # Keep same multiplier for fair comparison
    else:
        initial_capital = 100000
        atr_mult = 0.5
    
    print(f"\n{'='*80}")
    print(f"BACKTESTING {symbol} - Comparing 1-Hour vs 1-Day ATR")
    print('='*80)
    print(f"Initial Capital: ${initial_capital:,}")
    print(f"Period: {data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"Total Bars: {len(data):,}")
    print(f"Price Range: ${data['Low'].min():,.2f} - ${data['High'].max():,.2f}")
    
    results = {}
    
    # Test 1: Original 1-Hour ATR Strategy
    print(f"\n📊 Testing 1-HOUR ATR Strategy...")
    bt_hourly = Backtest(
        data,
        SimpleATRGridStrategy,
        cash=initial_capital,
        commission=0.001,
        trade_on_close=False
    )
    
    stats_hourly = bt_hourly.run(
        atr_multiplier=atr_mult,
        grid_levels=5,
        atr_period=14,
        take_profit_atr=1.0,
        stop_loss_atr=2.0
    )
    
    results['1-Hour ATR'] = {
        'Return': stats_hourly['Return [%]'],
        'Trades': len(stats_hourly._trades) if stats_hourly._trades is not None else 0,
        'Win Rate': stats_hourly.get('Win Rate [%]', 0),
        'Max Drawdown': stats_hourly['Max. Drawdown [%]'],
        'Sharpe': stats_hourly.get('Sharpe Ratio', 0),
        'Avg Trade': stats_hourly.get('Avg. Trade [%]', 0)
    }
    
    # Test 2: New 1-Day ATR Strategy
    print(f"\n📊 Testing 1-DAY ATR Strategy...")
    bt_daily = Backtest(
        data,
        DailyATRGridStrategy,
        cash=initial_capital,
        commission=0.001,
        trade_on_close=False
    )
    
    stats_daily = bt_daily.run(
        atr_multiplier=atr_mult,
        grid_levels=5,
        atr_period=14,
        take_profit_atr=1.0,
        stop_loss_atr=2.0
    )
    
    results['1-Day ATR'] = {
        'Return': stats_daily['Return [%]'],
        'Trades': len(stats_daily._trades) if stats_daily._trades is not None else 0,
        'Win Rate': stats_daily.get('Win Rate [%]', 0),
        'Max Drawdown': stats_daily['Max. Drawdown [%]'],
        'Sharpe': stats_daily.get('Sharpe Ratio', 0),
        'Avg Trade': stats_daily.get('Avg. Trade [%]', 0)
    }
    
    # Display comparison
    print(f"\n{'='*80}")
    print("RESULTS COMPARISON")
    print('='*80)
    
    metrics = ['Return', 'Trades', 'Win Rate', 'Avg Trade', 'Max Drawdown', 'Sharpe']
    print(f"\n{'Metric':<15} {'1-Hour ATR':>15} {'1-Day ATR':>15} {'Improvement':>15}")
    print('-'*60)
    
    for metric in metrics:
        hourly_val = results['1-Hour ATR'][metric]
        daily_val = results['1-Day ATR'][metric]
        
        if metric == 'Trades':
            print(f"{metric:<15} {hourly_val:>15} {daily_val:>15} {daily_val-hourly_val:>+15}")
        elif metric in ['Return', 'Win Rate', 'Avg Trade', 'Max Drawdown']:
            improvement = daily_val - hourly_val
            print(f"{metric:<15} {hourly_val:>14.2f}% {daily_val:>14.2f}% {improvement:>+14.2f}%")
        else:  # Sharpe
            improvement = daily_val - hourly_val
            print(f"{metric:<15} {hourly_val:>15.2f} {daily_val:>15.2f} {improvement:>+15.2f}")
    
    # Trade frequency analysis
    if stats_hourly._trades is not None and len(stats_hourly._trades) > 0:
        hourly_trades = stats_hourly._trades
        hourly_avg_duration = hourly_trades['Duration'].mean()
        print(f"\n1-Hour ATR - Avg Trade Duration: {hourly_avg_duration}")
    
    if stats_daily._trades is not None and len(stats_daily._trades) > 0:
        daily_trades = stats_daily._trades
        daily_avg_duration = daily_trades['Duration'].mean()
        print(f"1-Day ATR - Avg Trade Duration: {daily_avg_duration}")
    
    return results, stats_hourly, stats_daily


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("DAILY ATR GRID STRATEGY - BACKTEST COMPARISON")
    print("="*80)
    
    symbols = ['BTCUSDT', 'ETHUSDT']
    all_results = {}
    
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"Processing {symbol}")
        print('='*80)
        
        # Load one year of data
        data = load_data(symbol, days=365)
        
        if data.empty:
            print(f"❌ No data available for {symbol}")
            continue
        
        # Run comparison
        results, stats_hourly, stats_daily = run_comparison(symbol, data)
        all_results[symbol] = results
        
        # Save detailed results
        if stats_daily._trades is not None and len(stats_daily._trades) > 0:
            filename = f"{symbol.lower()}_daily_atr_trades.csv"
            stats_daily._trades.to_csv(filename)
            print(f"\n💾 Daily ATR trades saved to {filename}")
    
    # Overall summary
    print("\n" + "="*80)
    print("OVERALL SUMMARY - 1-DAY ATR IMPROVEMENTS")
    print("="*80)
    
    for symbol in all_results:
        hourly_return = all_results[symbol]['1-Hour ATR']['Return']
        daily_return = all_results[symbol]['1-Day ATR']['Return']
        improvement = daily_return - hourly_return
        
        hourly_trades = all_results[symbol]['1-Hour ATR']['Trades']
        daily_trades = all_results[symbol]['1-Day ATR']['Trades']
        
        print(f"\n{symbol}:")
        print(f"  Return Improvement: {improvement:+.2f}% ({hourly_return:.2f}% → {daily_return:.2f}%)")
        print(f"  Trade Reduction: {hourly_trades - daily_trades} trades ({hourly_trades} → {daily_trades})")
        print(f"  Efficiency: {(daily_trades/hourly_trades)*100:.1f}% of original trade count")
    
    print("\n" + "="*80)
    print("KEY INSIGHTS")
    print("="*80)
    print("""
1. Daily ATR creates wider grids that don't trigger as frequently
2. Fewer trades mean lower transaction costs
3. Wider grids survive normal volatility without consuming all levels
4. Better suited for trending markets where narrow grids get steamrolled
""")


if __name__ == "__main__":
    main()