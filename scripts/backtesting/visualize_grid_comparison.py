#\!/usr/bin/env python3
"""
Visualize grid spacing comparison for different ATR timeframes
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import os

def get_latest_prices_and_atr():
    """Get latest prices and ATR values"""
    db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    engine = create_engine(db_url)
    
    # Get latest prices
    query = """
    WITH latest_prices AS (
        SELECT symbol, close_price, open_time
        FROM kline_data
        WHERE interval = '1h'
          AND symbol IN ('BTCUSDT', 'ETHUSDT')
          AND open_time = (
              SELECT MAX(open_time) 
              FROM kline_data 
              WHERE interval = '1h' AND symbol = kline_data.symbol
          )
    )
    SELECT * FROM latest_prices
    """
    
    prices = pd.read_sql(query, engine)
    return prices

def create_grid_comparison():
    """Create detailed grid comparison"""
    
    print("\n" + "="*100)
    print("GRID SPACING COMPARISON - SOLVING THE NARROW RANGE PROBLEM")
    print("="*100)
    
    # Data from our ATR analysis
    atr_data = {
        'BTCUSDT': {
            'price': 115588.80,
            '1h_atr': 345.49,
            '4h_atr': 1023.08,
            '1d_atr': 2463.21
        },
        'ETHUSDT': {
            'price': 3787.08,
            '1h_atr': 27.48,
            '4h_atr': 73.08,
            '1d_atr': 177.99
        }
    }
    
    # Different multiplier scenarios
    multipliers = [0.5, 0.75, 1.0]
    
    for symbol in ['BTCUSDT', 'ETHUSDT']:
        data = atr_data[symbol]
        price = data['price']
        
        print(f"\n{'='*100}")
        print(f"{symbol} - Current Price: ${price:,.2f}")
        print("="*100)
        
        print("\n📊 GRID CONFIGURATIONS COMPARISON:")
        print("-"*100)
        
        # Create comparison table
        timeframes = ['1h', '4h', '1d']
        
        for tf in timeframes:
            atr_key = f'{tf}_atr'
            atr_value = data[atr_key]
            
            print(f"\n{tf.upper()} ATR (${atr_value:.2f} = {atr_value/price*100:.2f}% of price)")
            print("-"*60)
            
            print(f"{'Multiplier':<12} {'Grid Spacing':<15} {'Total Range':<15} {'Range %':<12} {'Trades/Day':<12}")
            print("-"*60)
            
            for mult in multipliers:
                spacing = atr_value * mult
                total_range = spacing * 5  # 5 grid levels
                range_pct = (total_range / price) * 100
                
                # Estimate trades per day based on volatility
                if tf == '1h':
                    trades_estimate = "50-100" if mult == 0.5 else "30-60" if mult == 0.75 else "20-40"
                elif tf == '4h':
                    trades_estimate = "15-30" if mult == 0.5 else "10-20" if mult == 0.75 else "5-15"
                else:  # 1d
                    trades_estimate = "5-10" if mult == 0.5 else "3-7" if mult == 0.75 else "2-5"
                
                print(f"{mult:<12.2f} ${spacing:<14,.0f} ${total_range:<14,.0f} {range_pct:<11.1f}% {trades_estimate:<12}")
        
        print("\n" + "📈 VISUAL GRID REPRESENTATION (using 0.75x multiplier):")
        print("-"*60)
        
        for tf in timeframes:
            atr_key = f'{tf}_atr'
            atr_value = data[atr_key]
            spacing = atr_value * 0.75
            
            print(f"\n{tf.upper()} Grid:")
            
            # Show grid levels
            levels = []
            for i in range(-2, 3):
                level_price = price + (i * spacing)
                pct_from_current = ((level_price - price) / price) * 100
                levels.append((i, level_price, pct_from_current))
            
            # Visual representation
            for level, level_price, pct in levels:
                if level == 0:
                    marker = "█" * 40 + f" <- CURRENT (${level_price:,.0f})"
                else:
                    distance = abs(pct)
                    bars = "░" * int(distance * 5)
                    marker = bars + f" Level {level:+d}: ${level_price:,.0f} ({pct:+.1f}%)"
                print(marker)
    
    # Key insights
    print("\n" + "="*100)
    print("KEY INSIGHTS - WHY YOUR CURRENT SETUP HAD ISSUES")
    print("="*100)
    
    print("""
🔍 **Problem Analysis:**

1. **1-Hour ATR Creates Narrow Grids:**
   - BTC: Only $864 range (0.75% of price) with 5 levels
   - ETH: Only $69 range (1.8% of price) with 5 levels
   - Result: All grid levels trigger within minor price movements
   - Consequence: Rapid position accumulation in trending markets

2. **Why This Led to Losses:**
   - In trending markets, all buy levels get hit quickly
   - No room for price to "breathe" and reverse
   - Stop losses triggered before any meaningful reversal
   - Grid gets "steamrolled" by the trend

3. **4-Hour ATR Solution:**
   - BTC: $2,558 range (2.2% of price) - 3x wider\!
   - ETH: $183 range (4.8% of price) - 2.6x wider\!
   - Benefit: Grid survives normal volatility without triggering all levels

4. **1-Day ATR for Conservative Trading:**
   - BTC: $6,158 range (5.3% of price) - 7x wider than 1h\!
   - ETH: $445 range (11.7% of price) - 6x wider than 1h\!
   - Benefit: Only major moves trigger grid levels

📊 **Recommended Configuration:**

For Active Trading (4-Hour ATR):
- ATR Timeframe: 4h
- ATR Multiplier: 0.75-1.0
- Grid Levels: 5-7
- Expected trades/day: 10-20

For Conservative Trading (1-Day ATR):
- ATR Timeframe: 1d
- ATR Multiplier: 0.5-0.75
- Grid Levels: 3-5
- Expected trades/day: 3-7
""")

if __name__ == "__main__":
    create_grid_comparison()
