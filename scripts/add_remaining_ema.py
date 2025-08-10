#!/usr/bin/env python3
"""
Add remaining EMA indicators for BNB
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository

DATABASE_URL = 'postgresql://localhost/tradingbot'


def main():
    """Add EMA_50 and EMA_200 for BNB"""
    
    print("Adding EMA_50 and EMA_200 for BNBUSDT 1h...")
    
    # Setup database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    repository = MarketDataRepository(db_session)
    
    # Get BNB data - using the method correctly
    from datetime import datetime, timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    klines = repository.get_klines(
        symbol='BNBUSDT',
        interval='1h',
        start_time=start_date,
        end_time=end_date,
        limit=1000
    )
    
    print(f"Processing {len(klines)} klines")
    
    if klines:
        # Prepare data in chronological order
        klines = list(reversed(klines))
        timestamps = [k.open_time for k in klines]
        close_prices = pd.Series([k.close_price for k in klines])
        
        # Calculate EMA 50 and 200
        ema_50 = close_prices.ewm(span=50, adjust=False).mean()
        ema_200 = close_prices.ewm(span=200, adjust=False).mean()
        
        # Save EMA_50
        saved_50 = 0
        for i in range(len(ema_50)):
            if not pd.isna(ema_50.iloc[i]):
                indicator_data = {
                    'symbol': 'BNBUSDT',
                    'indicator_name': 'ema_50',
                    'timeframe': '1h',
                    'timestamp': timestamps[i],
                    'value': float(ema_50.iloc[i]),
                    'parameters': json.dumps({'period': 50})
                }
                repository.save_indicator_value(indicator_data)
                saved_50 += 1
        
        print(f"  Saved {saved_50} EMA_50 values")
        
        # Save EMA_200
        saved_200 = 0
        for i in range(len(ema_200)):
            if not pd.isna(ema_200.iloc[i]):
                indicator_data = {
                    'symbol': 'BNBUSDT',
                    'indicator_name': 'ema_200',
                    'timeframe': '1h',
                    'timestamp': timestamps[i],
                    'value': float(ema_200.iloc[i]),
                    'parameters': json.dumps({'period': 200})
                }
                repository.save_indicator_value(indicator_data)
                saved_200 += 1
        
        print(f"  Saved {saved_200} EMA_200 values")
        
        db_session.commit()
        print("\n✅ EMA indicators added successfully!")
    
    db_session.close()
    engine.dispose()


if __name__ == "__main__":
    main()