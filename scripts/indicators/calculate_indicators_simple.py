#!/usr/bin/env python3
"""
Simple indicator calculation for completed symbols
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, text
import ta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')

def calculate_indicators_for_symbol(symbol, interval):
    """Calculate indicators for a single symbol and interval"""
    
    engine = create_engine(DATABASE_URL)
    
    # Load kline data
    query = text("""
        SELECT 
            id,
            open_time as timestamp,
            open_price,
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
    
    # Calculate indicators
    try:
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close_price'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(close=df['close_price'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(close=df['close_price'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        
        # Moving Averages
        df['sma_20'] = ta.trend.SMAIndicator(close=df['close_price'], window=20).sma_indicator()
        df['sma_50'] = ta.trend.SMAIndicator(close=df['close_price'], window=50).sma_indicator()
        df['ema_12'] = ta.trend.EMAIndicator(close=df['close_price'], window=12).ema_indicator()
        df['ema_26'] = ta.trend.EMAIndicator(close=df['close_price'], window=26).ema_indicator()
        
        # ATR
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high_price'],
            low=df['low_price'],
            close=df['close_price'],
            window=14
        ).average_true_range()
        
        # ADX
        adx = ta.trend.ADXIndicator(
            high=df['high_price'],
            low=df['low_price'],
            close=df['close_price'],
            window=14
        )
        df['adx'] = adx.adx()
        
        # OBV
        df['obv'] = ta.volume.OnBalanceVolumeIndicator(
            close=df['close_price'],
            volume=df['volume']
        ).on_balance_volume()
        
        # VWAP (simple calculation)
        df['vwap'] = (df['close_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        
    except Exception as e:
        print(f"  Error calculating indicators: {e}")
        return 0
    
    # Prepare data for insertion
    indicators_to_insert = []
    indicator_names = ['rsi', 'macd', 'macd_signal', 'macd_diff', 
                      'bb_upper', 'bb_middle', 'bb_lower',
                      'sma_20', 'sma_50', 'ema_12', 'ema_26',
                      'atr', 'adx', 'obv', 'vwap']
    
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
        # Delete existing indicators first
        with engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM indicator_values 
                WHERE symbol = :symbol AND timeframe = :interval
            """), {'symbol': symbol, 'interval': interval})
            conn.commit()
        
        # Insert new indicators in batches
        batch_size = 1000
        for i in range(0, len(indicators_to_insert), batch_size):
            batch = indicators_to_insert[i:i+batch_size]
            df_batch = pd.DataFrame(batch)
            df_batch.to_sql('indicator_values', engine, if_exists='append', index=False)
        
        print(f"  ✅ Inserted {len(indicators_to_insert)} indicator values")
        return len(indicators_to_insert)
    
    return 0

def main():
    print("=" * 80)
    print("CALCULATING INDICATORS FOR COMPLETED SYMBOLS")
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
                COUNT(DISTINCT timeframe) as intervals,
                COUNT(DISTINCT indicator_name) as indicators,
                COUNT(*) as total_values
            FROM indicator_values
            WHERE symbol IN ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
            GROUP BY symbol
            ORDER BY symbol
        """))
        
        print("\n📊 Verification:")
        for row in result:
            print(f"  {row[0]}: {row[1]} intervals, {row[2]} indicators, {row[3]:,} values")

if __name__ == "__main__":
    main()