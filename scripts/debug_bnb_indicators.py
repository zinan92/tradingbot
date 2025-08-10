#!/usr/bin/env python3
"""
Debug BNB indicator calculation
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.indicators.indicator_calculator import IndicatorCalculator
from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository

DATABASE_URL = 'postgresql://localhost/tradingbot'


def main():
    """Debug BNB indicator calculation"""
    
    print("Debugging BNB indicator calculation...")
    
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
    
    print(f"Found {len(klines)} klines for BNBUSDT 1h")
    
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
        print(f"\nDataFrame shape: {df.shape}")
        print(f"DataFrame columns before calculation: {list(df.columns)}")
        
        # Calculate indicators
        indicators = calculator.calculate_all_indicators(df)
        print(f"\nDataFrame columns after calculation: {list(df.columns)}")
        
        # Check specific indicators
        print("\nChecking specific indicators:")
        for col in ['ema_12', 'ema_50', 'ema_200', 'rsi', 'macd', 'macd_signal', 'macd_histogram', 'atr']:
            if col in df.columns:
                non_null_count = df[col].notna().sum()
                print(f"  {col}: {non_null_count} non-null values")
                if non_null_count > 0:
                    print(f"    Latest value: {df[col].iloc[-1]:.4f}")
            else:
                print(f"  {col}: NOT FOUND in dataframe")
        
        # Get latest indicators
        latest = calculator.get_latest_indicators(df)
        print(f"\nLatest indicators: {list(latest.keys())}")
    
    db_session.close()
    engine.dispose()


if __name__ == "__main__":
    main()