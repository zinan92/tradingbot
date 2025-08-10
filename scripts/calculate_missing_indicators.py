#!/usr/bin/env python3
"""
Calculate missing indicators directly
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
import numpy as np
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.indicators.indicator_calculator import IndicatorCalculator
from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository

DATABASE_URL = 'postgresql://localhost/tradingbot'


def calculate_macd(close_prices, fast=12, slow=26, signal=9):
    """Calculate MACD with all components"""
    exp1 = pd.Series(close_prices).ewm(span=fast, adjust=False).mean()
    exp2 = pd.Series(close_prices).ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist


def calculate_ema(close_prices, period):
    """Calculate EMA"""
    return pd.Series(close_prices).ewm(span=period, adjust=False).mean()


def main():
    """Calculate missing indicators"""
    
    print("Calculating missing indicators...")
    
    # Setup database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    repository = MarketDataRepository(db_session)
    calculator = IndicatorCalculator()
    
    # Fix 1: Calculate MACD components for Solana 15m
    print("\n1. Calculating MACD components for SOLUSDT 15m...")
    
    # Get historical data
    klines = repository.get_klines(
        symbol='SOLUSDT',
        interval='15m',
        limit=500
    )
    
    if klines:
        # Prepare data
        close_prices = [k.close_price for k in reversed(klines)]
        timestamps = [k.open_time for k in reversed(klines)]
        
        # Calculate MACD components
        macd, macd_signal, macd_hist = calculate_macd(close_prices)
        
        # Store MACD signal values
        print(f"  - Storing {len(macd_signal)} MACD signal values...")
        for i in range(len(macd_signal)):
            if not pd.isna(macd_signal.iloc[i]):
                indicator_data = {
                    'symbol': 'SOLUSDT',
                    'indicator_name': 'macd_signal',
                    'timeframe': '15m',
                    'timestamp': timestamps[i],
                    'value': float(macd_signal.iloc[i]),
                    'parameters': json.dumps({'fast': 12, 'slow': 26, 'signal': 9})
                }
                repository.save_indicator_value(indicator_data)
        
        # Store MACD histogram values
        print(f"  - Storing {len(macd_hist)} MACD histogram values...")
        for i in range(len(macd_hist)):
            if not pd.isna(macd_hist.iloc[i]):
                indicator_data = {
                    'symbol': 'SOLUSDT',
                    'indicator_name': 'macd_histogram',
                    'timeframe': '15m',
                    'timestamp': timestamps[i],
                    'value': float(macd_hist.iloc[i]),
                    'parameters': json.dumps({'fast': 12, 'slow': 26, 'signal': 9})
                }
                repository.save_indicator_value(indicator_data)
        
        db_session.commit()
        print("  ✓ MACD components saved for SOLUSDT")
    
    # Fix 2: Calculate EMA indicators for BNB 1h
    print("\n2. Calculating EMA indicators for BNBUSDT 1h...")
    
    # Get historical data
    klines = repository.get_klines(
        symbol='BNBUSDT',
        interval='1h',
        limit=500
    )
    
    if klines:
        # Prepare data
        kline_data = [
            {
                'open_price': k.open_price,
                'high_price': k.high_price,
                'low_price': k.low_price,
                'close_price': k.close_price,
                'volume': k.volume,
                'open_time': k.open_time
            }
            for k in reversed(klines)
        ]
        
        # Use calculator to prepare dataframe and calculate all indicators
        df = calculator.prepare_dataframe(kline_data)
        indicators = calculator.calculate_all_indicators(df)
        
        # Store EMA indicators
        for period in [12, 50, 200]:
            ema_key = f'ema_{period}'
            if ema_key in df.columns:
                values = df[ema_key]
                print(f"  - Storing {len(values)} EMA_{period} values...")
                
                for i in range(len(values)):
                    if not pd.isna(values.iloc[i]):
                        indicator_data = {
                            'symbol': 'BNBUSDT',
                            'indicator_name': f'ema_{period}',
                            'timeframe': '1h',
                            'timestamp': df.index[i],
                            'value': float(values.iloc[i]),
                            'parameters': json.dumps({'period': period})
                        }
                        repository.save_indicator_value(indicator_data)
        
        # Also store other indicators (RSI, MACD, ATR)
        print("  - Storing other indicators...")
        
        # RSI
        if 'rsi' in df.columns:
            rsi_values = df['rsi']
            for i in range(len(rsi_values)):
                if not pd.isna(rsi_values.iloc[i]):
                    indicator_data = {
                        'symbol': 'BNBUSDT',
                        'indicator_name': 'rsi',
                        'timeframe': '1h',
                        'timestamp': df.index[i],
                        'value': float(rsi_values.iloc[i]),
                        'parameters': json.dumps({'period': 14})
                    }
                    repository.save_indicator_value(indicator_data)
        
        # MACD components
        if 'macd' in df.columns:
            macd_values = df['macd']
            macd_signal_values = df.get('macd_signal', pd.Series())
            macd_hist_values = df.get('macd_histogram', pd.Series())
            
            for i in range(len(macd_values)):
                if not pd.isna(macd_values.iloc[i]):
                    # MACD line
                    indicator_data = {
                        'symbol': 'BNBUSDT',
                        'indicator_name': 'macd',
                        'timeframe': '1h',
                        'timestamp': df.index[i],
                        'value': float(macd_values.iloc[i]),
                        'parameters': json.dumps({'fast': 12, 'slow': 26, 'signal': 9})
                    }
                    repository.save_indicator_value(indicator_data)
                    
                    # MACD signal
                    if i < len(macd_signal_values) and not pd.isna(macd_signal_values.iloc[i]):
                        indicator_data = {
                            'symbol': 'BNBUSDT',
                            'indicator_name': 'macd_signal',
                            'timeframe': '1h',
                            'timestamp': df.index[i],
                            'value': float(macd_signal_values.iloc[i]),
                            'parameters': json.dumps({'fast': 12, 'slow': 26, 'signal': 9})
                        }
                        repository.save_indicator_value(indicator_data)
                    
                    # MACD histogram
                    if i < len(macd_hist_values) and not pd.isna(macd_hist_values.iloc[i]):
                        indicator_data = {
                            'symbol': 'BNBUSDT',
                            'indicator_name': 'macd_histogram',
                            'timeframe': '1h',
                            'timestamp': df.index[i],
                            'value': float(macd_hist_values.iloc[i]),
                            'parameters': json.dumps({'fast': 12, 'slow': 26, 'signal': 9})
                        }
                        repository.save_indicator_value(indicator_data)
        
        # ATR
        if 'atr' in df.columns:
            atr_values = df['atr']
            for i in range(len(atr_values)):
                if not pd.isna(atr_values.iloc[i]):
                    indicator_data = {
                        'symbol': 'BNBUSDT',
                        'indicator_name': 'atr',
                        'timeframe': '1h',
                        'timestamp': df.index[i],
                        'value': float(atr_values.iloc[i]),
                        'parameters': json.dumps({'period': 14})
                    }
                    repository.save_indicator_value(indicator_data)
        
        db_session.commit()
        print("  ✓ All indicators saved for BNBUSDT")
    
    # Verify the fixes
    print("\n3. Verifying fixes...")
    
    with engine.connect() as conn:
        # Check Solana MACD components
        result = conn.execute(text("""
            SELECT indicator_name, COUNT(*) as count 
            FROM indicator_values 
            WHERE symbol = 'SOLUSDT' 
                AND timeframe = '15m' 
                AND indicator_name IN ('macd', 'macd_signal', 'macd_histogram')
            GROUP BY indicator_name
            ORDER BY indicator_name
        """))
        
        print("\nSolana MACD components:")
        for row in result:
            print(f"  - {row.indicator_name}: {row.count:,} data points")
        
        # Check BNB indicators
        result = conn.execute(text("""
            SELECT indicator_name, COUNT(*) as count 
            FROM indicator_values 
            WHERE symbol = 'BNBUSDT' 
                AND timeframe = '1h'
            GROUP BY indicator_name
            ORDER BY indicator_name
        """))
        
        print("\nBNB 1h indicators:")
        for row in result:
            print(f"  - {row.indicator_name}: {row.count:,} data points")
    
    db_session.close()
    engine.dispose()
    
    print("\n✅ Indicator calculation complete!")


if __name__ == "__main__":
    main()