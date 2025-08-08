#!/usr/bin/env python3
"""
Calculate only specific indicators: MACD, RSI, ATR, EMA12, EMA50, EMA200
"""

import os
import sys
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
import ta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')

def calculate_indicators_for_symbol(symbol, interval):
    """Calculate only specified indicators for a single symbol and interval"""
    
    engine = create_engine(DATABASE_URL)
    
    # Load kline data
    query = text("""
        SELECT 
            id,
            open_time as timestamp,
            high_price,
            low_price,
            close_price,
            volume
        FROM kline_data
        WHERE symbol = :symbol AND interval = :interval
        ORDER BY open_time
    """)
    
    df = pd.read_sql(query, engine, params={'symbol': symbol, 'interval': interval})
    
    if df.empty:
        print(f"  No data for {symbol} {interval}")
        return 0
    
    print(f"  Processing {len(df)} candles for {symbol} {interval}...")
    
    # Calculate ONLY the requested indicators
    try:
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close_price'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(close=df['close_price'])
        df['macd'] = macd.macd()
        
        # ATR
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high_price'],
            low=df['low_price'],
            close=df['close_price'],
            window=14
        ).average_true_range()
        
        # EMAs
        df['ema_12'] = ta.trend.EMAIndicator(close=df['close_price'], window=12).ema_indicator()
        df['ema_50'] = ta.trend.EMAIndicator(close=df['close_price'], window=50).ema_indicator()
        df['ema_200'] = ta.trend.EMAIndicator(close=df['close_price'], window=200).ema_indicator()
        
    except Exception as e:
        print(f"  Error calculating indicators: {e}")
        return 0
    
    # Prepare data for insertion - ONLY the 6 requested indicators
    indicators_to_insert = []
    indicator_names = ['rsi', 'macd', 'atr', 'ema_12', 'ema_50', 'ema_200']
    
    for idx, row in df.iterrows():
        for indicator in indicator_names:
            if indicator in df.columns and pd.notna(row[indicator]):
                indicators_to_insert.append({
                    'symbol': symbol,
                    'indicator_name': indicator,
                    'timeframe': interval,
                    'timestamp': row['timestamp'],
                    'value': float(row[indicator]),
                    'created_at': datetime.now()
                })
    
    # Insert into database
    if indicators_to_insert:
        # Delete existing indicators for these specific types first
        with engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM indicator_values 
                WHERE symbol = :symbol 
                AND timeframe = :interval
                AND indicator_name IN ('rsi', 'macd', 'atr', 'ema_12', 'ema_50', 'ema_200')
            """), {'symbol': symbol, 'interval': interval})
            conn.commit()
        
        # Insert new indicators in batches
        batch_size = 5000
        for i in range(0, len(indicators_to_insert), batch_size):
            batch = indicators_to_insert[i:i+batch_size]
            df_batch = pd.DataFrame(batch)
            df_batch.to_sql('indicator_values', engine, if_exists='append', index=False)
        
        print(f"  ✅ Inserted {len(indicators_to_insert)} indicator values")
        return len(indicators_to_insert)
    
    return 0

def main():
    print("=" * 80)
    print("CALCULATING SPECIFIC INDICATORS")
    print("Indicators: MACD, RSI, ATR, EMA12, EMA50, EMA200")
    print("=" * 80)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '1d']
    
    total_calculated = 0
    
    for symbol in symbols:
        print(f"\n📊 Processing {symbol}...")
        symbol_total = 0
        
        for interval in intervals:
            count = calculate_indicators_for_symbol(symbol, interval)
            symbol_total += count
            total_calculated += count
        
        print(f"✅ {symbol} complete: {symbol_total:,} indicator values")
    
    print("\n" + "=" * 80)
    print(f"✨ Total indicators calculated: {total_calculated:,}")
    
    # Verify
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                symbol,
                timeframe,
                indicator_name,
                COUNT(*) as count
            FROM indicator_values
            WHERE symbol IN ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
            AND indicator_name IN ('rsi', 'macd', 'atr', 'ema_12', 'ema_50', 'ema_200')
            GROUP BY symbol, timeframe, indicator_name
            ORDER BY symbol, timeframe, indicator_name
            LIMIT 50
        """))
        
        print("\n📊 Sample verification (first 50 entries):")
        current_symbol = None
        for row in result:
            if current_symbol != row[0]:
                print(f"\n{row[0]}:")
                current_symbol = row[0]
            print(f"  {row[1]:4s} - {row[2]:8s}: {row[3]:,} values")

if __name__ == "__main__":
    main()