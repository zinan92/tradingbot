#!/usr/bin/env python3
"""
Backtest the Optimal Grid Strategy with Midpoint Rules
Compares with previous 4-hour ATR strategy
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from backtesting import Backtest
import os
import sys

# Add project root to path (two levels up from scripts/backtesting/)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.infrastructure.backtesting.strategies.optimal_grid_strategy import OptimalGridStrategy
from src.infrastructure.backtesting.strategies.four_hour_atr_grid import FourHourATRGridStrategy


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


def run_optimal_strategy(symbol, data):
    """Run the optimal grid strategy"""
    
    # Determine initial capital
    if symbol == 'BTCUSDT':
        initial_capital = 1000000
    else:
        initial_capital = 100000
    
    print(f"\n📊 Testing Optimal Grid Strategy (Daily ATR, Midpoint Rules)...")
    print(f"  - Buy only below midpoint")
    print(f"  - Sell only above midpoint")
    print(f"  - 5 grid levels per side")
    print(f"  - Daily range updates")
    
    bt = Backtest(
        data,
        OptimalGridStrategy,
        cash=initial_capital,
        commission=0.0004,  # Correct 0.04% fee
        trade_on_close=False
    )
    
    # Run with optimal parameters
    stats = bt.run(
        atr_period=14,
        grid_levels=5,
        atr_range_multiplier=1.0,  # Full ATR as range
        take_profit_pct=0.02,
        stop_loss_pct=0.05
    )
    
    return stats


def run_comparison(symbol, data):
    """Compare optimal strategy with 4-hour ATR strategy"""
    
    # Determine initial capital
    if symbol == 'BTCUSDT':
        initial_capital = 1000000
    else:
        initial_capital = 100000
    
    print(f"\n{'='*100}")
    print(f"STRATEGY COMPARISON - {symbol}")
    print('='*100)
    print(f"Period: {data.index[0].strftime('%Y-%m-%d')} to {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"Initial Capital: ${initial_capital:,}")
    
    results = {}
    
    # Test 1: Optimal Grid Strategy
    print("\n1️⃣ OPTIMAL GRID STRATEGY (New)")
    optimal_stats = run_optimal_strategy(symbol, data)
    
    results['Optimal Grid'] = {
        'Return': optimal_stats['Return [%]'],
        'Trades': len(optimal_stats._trades) if optimal_stats._trades is not None else 0,
        'Win Rate': optimal_stats.get('Win Rate [%]', 0),
        'Max Drawdown': optimal_stats['Max. Drawdown [%]'],
        'Sharpe': optimal_stats.get('Sharpe Ratio', 0),
        'Avg Trade': optimal_stats.get('Avg. Trade [%]', 0)
    }
    
    # Save trades for analysis
    if optimal_stats._trades is not None and len(optimal_stats._trades) > 0:
        filename = f"{symbol.lower()}_optimal_grid_trades.csv"
        filepath = os.path.join(project_root, "outputs", "trades", filename)
        optimal_stats._trades.to_csv(filepath)
        print(f"  💾 Trades saved to outputs/trades/{filename}")
    
    # Test 2: 4-Hour ATR Strategy (for comparison)
    print(f"\n2️⃣ 4-HOUR ATR STRATEGY (Previous Best)")
    
    bt_4h = Backtest(
        data,
        FourHourATRGridStrategy,
        cash=initial_capital,
        commission=0.0004,
        trade_on_close=False
    )
    
    stats_4h = bt_4h.run(
        atr_multiplier=0.5,
        grid_levels=5,
        atr_period=14,
        take_profit_atr=1.0,
        stop_loss_atr=2.0
    )
    
    results['4-Hour ATR'] = {
        'Return': stats_4h['Return [%]'],
        'Trades': len(stats_4h._trades) if stats_4h._trades is not None else 0,
        'Win Rate': stats_4h.get('Win Rate [%]', 0),
        'Max Drawdown': stats_4h['Max. Drawdown [%]'],
        'Sharpe': stats_4h.get('Sharpe Ratio', 0),
        'Avg Trade': stats_4h.get('Avg. Trade [%]', 0)
    }
    
    return results, optimal_stats


def display_results(all_results):
    """Display comparison results"""
    
    print("\n" + "="*100)
    print("OPTIMAL GRID STRATEGY - RESULTS SUMMARY")
    print("="*100)
    
    for symbol in all_results:
        print(f"\n{'='*100}")
        print(f"{symbol} PERFORMANCE")
        print('='*100)
        
        results = all_results[symbol]
        
        print(f"\n{'Metric':<20} {'Optimal Grid':>20} {'4-Hour ATR':>20} {'Difference':>20}")
        print('-'*80)
        
        # Return
        opt_return = results['Optimal Grid']['Return']
        four_h_return = results['4-Hour ATR']['Return']
        return_diff = opt_return - four_h_return
        print(f"{'Return %':<20} {opt_return:>19.2f}% {four_h_return:>19.2f}% {return_diff:>+19.2f}%")
        
        # Trades
        opt_trades = results['Optimal Grid']['Trades']
        four_h_trades = results['4-Hour ATR']['Trades']
        trades_diff = opt_trades - four_h_trades
        print(f"{'Total Trades':<20} {opt_trades:>20} {four_h_trades:>20} {trades_diff:>+20}")
        
        # Win Rate
        opt_wr = results['Optimal Grid']['Win Rate']
        four_h_wr = results['4-Hour ATR']['Win Rate']
        wr_diff = opt_wr - four_h_wr
        print(f"{'Win Rate %':<20} {opt_wr:>19.2f}% {four_h_wr:>19.2f}% {wr_diff:>+19.2f}%")
        
        # Max Drawdown
        opt_dd = results['Optimal Grid']['Max Drawdown']
        four_h_dd = results['4-Hour ATR']['Max Drawdown']
        dd_diff = opt_dd - four_h_dd
        print(f"{'Max Drawdown %':<20} {opt_dd:>19.2f}% {four_h_dd:>19.2f}% {dd_diff:>+19.2f}%")
        
        # Avg Trade
        opt_avg = results['Optimal Grid']['Avg Trade']
        four_h_avg = results['4-Hour ATR']['Avg Trade']
        avg_diff = opt_avg - four_h_avg
        print(f"{'Avg Trade %':<20} {opt_avg:>19.2f}% {four_h_avg:>19.2f}% {avg_diff:>+19.2f}%")
        
        # Analysis
        print(f"\n📊 Analysis:")
        print("-"*50)
        if opt_return > four_h_return:
            print(f"✅ Optimal Grid outperformed by {return_diff:.2f}%")
        else:
            print(f"❌ 4-Hour ATR performed better by {abs(return_diff):.2f}%")
        
        print(f"Trade frequency: {opt_trades/365:.1f} trades/day (Optimal) vs {four_h_trades/365:.1f} trades/day (4H)")


def main():
    """Main execution"""
    print("\n" + "="*100)
    print("OPTIMAL GRID STRATEGY BACKTEST")
    print("Midpoint-Based Trading with Daily ATR Range")
    print("="*100)
    
    print("\n📋 Strategy Rules:")
    print("-"*50)
    print("• Daily range based on 1-day ATR(14)")
    print("• NEUTRAL regime: bidirectional trading")
    print("• Buy ONLY below midpoint (5 levels)")
    print("• Sell ONLY above midpoint (5 levels)")
    print("• Range updates daily")
    print("• Trading fee: 0.04%")
    
    symbols = ['BTCUSDT', 'ETHUSDT']
    all_results = {}
    
    for symbol in symbols:
        # Load data
        data = load_data(symbol, days=365)
        
        if data.empty:
            print(f"❌ No data available for {symbol}")
            continue
        
        # Run comparison
        results, optimal_stats = run_comparison(symbol, data)
        all_results[symbol] = results
    
    # Display results
    display_results(all_results)
    
    # Final recommendations
    print("\n" + "="*100)
    print("KEY INSIGHTS - OPTIMAL GRID STRATEGY")
    print("="*100)
    
    print("""
🎯 Optimal Grid Strategy Features:

1. **Midpoint-Based Entry Logic:**
   - Prevents buying at high prices
   - Prevents selling at low prices
   - Natural mean reversion bias

2. **Daily Range Updates:**
   - Adapts to changing volatility
   - Fresh grid levels each day
   - Based on 14-day ATR

3. **NEUTRAL Regime Benefits:**
   - Captures moves in both directions
   - Works in ranging markets
   - Reduces directional risk

4. **Potential Improvements:**
   - Add human input for range/regime
   - Implement BULLISH/BEARISH modes
   - Optimize grid spacing
   - Add volatility filters
""")


if __name__ == "__main__":
    main()