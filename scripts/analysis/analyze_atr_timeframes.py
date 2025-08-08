#\!/usr/bin/env python3
"""
Analyze ATR values across different timeframes for BTC and ETH
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import os

def calculate_atr(df, period=14):
    """Calculate ATR for given dataframe"""
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate ATR
    atr = tr.rolling(window=period).mean()
    
    return atr

def load_data_for_timeframe(symbol, interval, days=30):
    """Load data for specific timeframe"""
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
      AND interval = %(interval)s
      AND open_time >= %(start_date)s
      AND open_time <= %(end_date)s
    ORDER BY open_time
    """
    
    df = pd.read_sql(
        query,
        engine,
        params={
            'symbol': symbol,
            'interval': interval,
            'start_date': start_date,
            'end_date': end_date
        },
        parse_dates=['timestamp']
    )
    
    if not df.empty:
        df.set_index('timestamp', inplace=True)
    
    return df

def analyze_symbol(symbol):
    """Analyze ATR for different timeframes"""
    print(f"\n{'='*80}")
    print(f"ATR ANALYSIS FOR {symbol}")
    print('='*80)
    
    timeframes = [
        ('1h', '1-Hour'),
        ('4h', '4-Hour'),
        ('1d', '1-Day')
    ]
    
    atr_results = {}
    
    for interval, label in timeframes:
        print(f"\n📊 {label} Timeframe:")
        print("-"*40)
        
        # Load data
        data = load_data_for_timeframe(symbol, interval, days=60)
        
        if data.empty:
            print(f"  ❌ No {interval} data available")
            continue
        
        # Calculate ATR
        atr = calculate_atr(data, period=14)
        
        # Get recent price for percentage calculation
        recent_price = data['Close'].iloc[-1]
        recent_atr = atr.iloc[-1]
        
        # Statistics
        atr_mean = atr.dropna().mean()
        atr_std = atr.dropna().std()
        atr_min = atr.dropna().min()
        atr_max = atr.dropna().max()
        
        # Store results
        atr_results[interval] = {
            'current': recent_atr,
            'mean': atr_mean,
            'percentage': (recent_atr / recent_price) * 100
        }
        
        print(f"  Current Price: ${recent_price:,.2f}")
        print(f"  Current ATR: ${recent_atr:,.2f}")
        print(f"  ATR as % of Price: {(recent_atr/recent_price)*100:.2f}%")
        print(f"  Average ATR (30d): ${atr_mean:,.2f}")
        print(f"  ATR Range: ${atr_min:,.2f} - ${atr_max:,.2f}")
        print(f"  ATR Std Dev: ${atr_std:,.2f}")
        
        # Grid range implications
        print(f"\n  Grid Implications (using 0.5x ATR multiplier):")
        grid_spacing = recent_atr * 0.5
        print(f"    Grid Spacing: ${grid_spacing:,.2f}")
        print(f"    5-Level Grid Range: ${grid_spacing * 5:,.2f}")
        print(f"    Range as % of Price: {(grid_spacing * 5 / recent_price)*100:.2f}%")
        
        # Show what this means for actual grid levels
        print(f"\n  Example Grid Levels (from current price):")
        for i in range(-2, 3):
            level_price = recent_price + (i * grid_spacing)
            print(f"    Level {i:+d}: ${level_price:,.2f}")
    
    return atr_results

def compare_timeframes():
    """Compare ATR across timeframes for both symbols"""
    symbols = ['BTCUSDT', 'ETHUSDT']
    all_results = {}
    
    for symbol in symbols:
        all_results[symbol] = analyze_symbol(symbol)
    
    # Comparison table
    print("\n" + "="*80)
    print("ATR COMPARISON SUMMARY")
    print("="*80)
    
    print("\n📊 Current ATR Values:")
    print("-"*60)
    print(f"{'Symbol':<10} {'1-Hour':<15} {'4-Hour':<15} {'1-Day':<15}")
    print("-"*60)
    
    for symbol in symbols:
        results = all_results[symbol]
        row = f"{symbol:<10}"
        for tf in ['1h', '4h', '1d']:
            if tf in results:
                value = results[tf]['current']
                pct = results[tf]['percentage']
                row += f" ${value:>8,.0f} ({pct:.1f}%)"
            else:
                row += f" {'N/A':>15}"
        print(row)
    
    print("\n📈 Grid Range Comparison (5 levels, 0.5x ATR multiplier):")
    print("-"*60)
    print(f"{'Symbol':<10} {'1-Hour':<15} {'4-Hour':<15} {'1-Day':<15}")
    print("-"*60)
    
    for symbol in symbols:
        results = all_results[symbol]
        row = f"{symbol:<10}"
        for tf in ['1h', '4h', '1d']:
            if tf in results:
                range_size = results[tf]['current'] * 0.5 * 5
                row += f" ${range_size:>8,.0f}"
            else:
                row += f" {'N/A':>15}"
        print(row)
    
    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    print("""
Based on the ATR analysis:

1. **1-Hour ATR Issues:**
   - Creates very tight grid ranges (typically 1-2% of price)
   - Leads to frequent triggering and high transaction costs
   - Grid gets consumed quickly in trending markets

2. **4-Hour ATR Benefits:**
   - Provides 3-4x wider grid spacing
   - Better suited for medium-term price movements
   - Reduces overtrading while maintaining responsiveness

3. **1-Day ATR Benefits:**
   - Creates widest grid spacing (5-7% of price typically)
   - Best for longer-term positions
   - Most resistant to whipsaws and false signals

4. **Suggested Approach:**
   - Use 4-hour ATR for active trading (good balance)
   - Use 1-day ATR for more conservative positioning
   - Consider increasing ATR multiplier (0.75-1.0 instead of 0.5)
   - Adjust grid levels based on market conditions
""")

if __name__ == "__main__":
    compare_timeframes()
