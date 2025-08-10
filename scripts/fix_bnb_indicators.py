#!/usr/bin/env python3
"""
Fix BNB indicators by properly saving from calculator results
"""

import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.indicators.indicator_calculator import IndicatorCalculator
from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository

DATABASE_URL = 'postgresql://localhost/tradingbot'


def main():
    """Fix BNB indicators"""
    
    print("Fixing BNB 1h indicators...")
    
    # Setup database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    repository = MarketDataRepository(db_session)
    calculator = IndicatorCalculator()
    
    # Get BNB 1h data
    klines = repository.get_klines(
        symbol='BNBUSDT',
        interval='1h',
        limit=500
    )
    
    print(f"Processing {len(klines)} klines for BNBUSDT 1h")
    
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
        
        # Prepare dataframe
        df = calculator.prepare_dataframe(kline_data)
        timestamps = df.index.tolist()
        
        # Calculate all indicators - returns a dictionary
        indicators = calculator.calculate_all_indicators(df)
        
        # Save EMA indicators
        for period in [12, 50, 200]:
            ema_key = f'ema_{period}' if period != 26 else 'ema_26'
            
            if ema_key in indicators:
                values = indicators[ema_key]
                
                if isinstance(values, pd.Series):
                    print(f"  Saving {values.notna().sum()} EMA_{period} values...")
                    
                    for i in range(len(values)):
                        if not pd.isna(values.iloc[i]):
                            indicator_data = {
                                'symbol': 'BNBUSDT',
                                'indicator_name': f'ema_{period}',
                                'timeframe': '1h',
                                'timestamp': timestamps[i],
                                'value': float(values.iloc[i]),
                                'parameters': json.dumps({'period': period})
                            }
                            repository.save_indicator_value(indicator_data)
        
        # Save RSI
        if 'rsi' in indicators:
            rsi_values = indicators['rsi']
            if isinstance(rsi_values, pd.Series):
                print(f"  Saving {rsi_values.notna().sum()} RSI values...")
                
                for i in range(len(rsi_values)):
                    if not pd.isna(rsi_values.iloc[i]):
                        indicator_data = {
                            'symbol': 'BNBUSDT',
                            'indicator_name': 'rsi',
                            'timeframe': '1h',
                            'timestamp': timestamps[i],
                            'value': float(rsi_values.iloc[i]),
                            'parameters': json.dumps({'period': 14})
                        }
                        repository.save_indicator_value(indicator_data)
        
        # Save MACD components
        for component in ['macd', 'macd_signal', 'macd_histogram']:
            if component in indicators:
                values = indicators[component]
                if isinstance(values, pd.Series):
                    print(f"  Saving {values.notna().sum()} {component} values...")
                    
                    for i in range(len(values)):
                        if not pd.isna(values.iloc[i]):
                            indicator_data = {
                                'symbol': 'BNBUSDT',
                                'indicator_name': component,
                                'timeframe': '1h',
                                'timestamp': timestamps[i],
                                'value': float(values.iloc[i]),
                                'parameters': json.dumps({'fast': 12, 'slow': 26, 'signal': 9})
                            }
                            repository.save_indicator_value(indicator_data)
        
        # Save ATR
        if 'atr' in indicators:
            atr_values = indicators['atr']
            if isinstance(atr_values, pd.Series):
                print(f"  Saving {atr_values.notna().sum()} ATR values...")
                
                for i in range(len(atr_values)):
                    if not pd.isna(atr_values.iloc[i]):
                        indicator_data = {
                            'symbol': 'BNBUSDT',
                            'indicator_name': 'atr',
                            'timeframe': '1h',
                            'timestamp': timestamps[i],
                            'value': float(atr_values.iloc[i]),
                            'parameters': json.dumps({'period': 14})
                        }
                        repository.save_indicator_value(indicator_data)
        
        db_session.commit()
        print("  ✓ Indicators saved for BNBUSDT 1h")
    
    # Verify the fix
    print("\nVerifying BNB indicators...")
    
    with engine.connect() as conn:
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
    
    print("\n✅ BNB indicators fixed!")


if __name__ == "__main__":
    main()