#!/usr/bin/env python3
"""
Extract and Display Trading Logs from ATR Grid Strategy Backtest
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

def load_data(symbol, days=30):
    """Load recent data for cleaner demonstration"""
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

def run_backtest_with_logs(symbol, data, initial_capital):
    """Run backtest and extract detailed logs"""
    
    # Adjust parameters based on symbol
    if symbol == 'BTCUSDT':
        atr_mult = 0.3
        capital = 1000000
    else:
        atr_mult = 0.4
        capital = 100000
    
    # Create backtest
    bt = Backtest(
        data,
        SimpleATRGridStrategy,
        cash=capital,
        commission=0.001,
        trade_on_close=False
    )
    
    # Run backtest
    stats = bt.run(
        atr_multiplier=atr_mult,
        grid_levels=3,
        atr_period=14,
        take_profit_atr=1.5,
        stop_loss_atr=3.0
    )
    
    # Extract trades
    trades = stats._trades
    
    return stats, trades

def format_trades(trades_df, symbol):
    """Format trades DataFrame for display"""
    if trades_df.empty:
        return pd.DataFrame()
    
    # Create formatted output
    formatted = pd.DataFrame({
        'Symbol': symbol,
        'Entry Time': trades_df['EntryTime'],
        'Entry Price': trades_df['EntryPrice'].round(2),
        'Exit Time': trades_df['ExitTime'],
        'Exit Price': trades_df['ExitPrice'].round(2),
        'Size': trades_df['Size'].round(4),
        'Duration': trades_df['Duration'],
        'P&L': trades_df['PnL'].round(2),
        'P&L %': trades_df['ReturnPct'].round(2),
        'Cumulative P&L': trades_df['PnL'].cumsum().round(2)
    })
    
    return formatted

def print_summary(symbol, stats, trades_df):
    """Print summary statistics"""
    print(f"\n{'='*80}")
    print(f"{symbol} TRADING SUMMARY")
    print('='*80)
    
    print(f"\nPerformance Metrics:")
    print(f"  Total Return: {stats['Return [%]']:.2f}%")
    print(f"  Total Trades: {len(trades_df)}")
    print(f"  Win Rate: {stats.get('Win Rate [%]', 0):.2f}%")
    print(f"  Avg Trade: {stats.get('Avg. Trade [%]', 0):.2f}%")
    print(f"  Max Drawdown: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  Sharpe Ratio: {stats.get('Sharpe Ratio', 0):.2f}")
    
    if not trades_df.empty:
        print(f"\nTrade Statistics:")
        print(f"  Total P&L: ${trades_df['PnL'].sum():,.2f}")
        print(f"  Best Trade: ${trades_df['PnL'].max():,.2f}")
        print(f"  Worst Trade: ${trades_df['PnL'].min():,.2f}")
        print(f"  Avg Trade P&L: ${trades_df['PnL'].mean():,.2f}")
        print(f"  Avg Duration: {trades_df['Duration'].mean()}")

def main():
    """Main execution"""
    print("\n" + "="*80)
    print("ATR GRID STRATEGY - TRADING LOG ANALYSIS")
    print("="*80)
    
    # Test both symbols
    symbols = ['BTCUSDT', 'ETHUSDT']
    all_trades = []
    
    for symbol in symbols:
        print(f"\n📊 Processing {symbol}...")
        
        # Load data (30 days for cleaner output)
        data = load_data(symbol, days=30)
        
        if data.empty:
            print(f"  ❌ No data available for {symbol}")
            continue
        
        print(f"  ✅ Loaded {len(data)} hours of data")
        print(f"  📈 Price range: ${data['Low'].min():,.2f} - ${data['High'].max():,.2f}")
        
        # Run backtest
        if symbol == 'BTCUSDT':
            capital = 1000000
        else:
            capital = 100000
            
        stats, trades = run_backtest_with_logs(symbol, data, capital)
        
        if trades is not None and not trades.empty:
            # Format trades
            formatted_trades = format_trades(trades, symbol)
            all_trades.append(formatted_trades)
            
            # Print summary
            print_summary(symbol, stats, trades)
            
            # Display first 10 trades
            print(f"\n📋 First 10 Trades for {symbol}:")
            print("-"*80)
            
            display_cols = ['Entry Time', 'Entry Price', 'Exit Time', 'Exit Price', 
                          'P&L', 'P&L %', 'Cumulative P&L']
            
            if len(formatted_trades) > 0:
                print(formatted_trades[display_cols].head(10).to_string(index=False))
            
            # Save to CSV
            csv_filename = f"{symbol.lower()}_trades.csv"
            formatted_trades.to_csv(csv_filename, index=False)
            print(f"\n💾 Full trading log saved to {csv_filename}")
        else:
            print(f"  ⚠️ No trades executed for {symbol}")
    
    # Combine all trades if any
    if all_trades:
        combined = pd.concat(all_trades, ignore_index=True)
        combined.to_csv("all_trades.csv", index=False)
        print(f"\n💾 Combined trading log saved to all_trades.csv")
        
        # Overall statistics
        print("\n" + "="*80)
        print("OVERALL STATISTICS")
        print("="*80)
        print(f"Total Trades: {len(combined)}")
        print(f"Total P&L: ${combined['P&L'].sum():,.2f}")
        print(f"Average P&L per Trade: ${combined['P&L'].mean():,.2f}")
        
        # Group by symbol
        print("\nBy Symbol:")
        for symbol in combined['Symbol'].unique():
            symbol_trades = combined[combined['Symbol'] == symbol]
            print(f"  {symbol}: {len(symbol_trades)} trades, P&L: ${symbol_trades['P&L'].sum():,.2f}")

if __name__ == "__main__":
    main()