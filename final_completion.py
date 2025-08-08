#!/usr/bin/env python3
"""
Final completion for AVAXUSDT and BCHUSDT
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.persistence.postgres.market_data_tables import Base
from src.infrastructure.market_data.bulk_data_loader import BulkDataLoader

async def final_completion():
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 80)
    print("FINAL COMPLETION - AVAXUSDT & BCHUSDT")
    print("=" * 80)
    
    # Only these two need completion
    final_symbols = ['AVAXUSDT', 'BCHUSDT']
    
    loader = BulkDataLoader(db_session)
    await loader.start()
    
    intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '1d']
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 3)  # 3 years
    
    total_downloaded = 0
    
    for symbol in final_symbols:
        print(f"\n📥 Downloading {symbol}...")
        print(f"   Period: {start_date.date()} to {end_date.date()}")
        
        try:
            stats = await loader.download_historical_data(
                symbols=[symbol],
                intervals=intervals,
                start_date=start_date,
                end_date=end_date
            )
            
            if stats['total_candles'] > 0:
                total_downloaded += stats['total_candles']
                print(f"   ✅ Downloaded {stats['total_candles']:,} candles")
                print(f"   Success rate: {stats['successful']}/{stats['total_tasks']}")
            else:
                print(f"   ⚠️ No new data")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
        
        await asyncio.sleep(5)
    
    await loader.stop()
    db_session.close()
    engine.dispose()
    
    print(f"\n{'='*80}")
    print(f"✅ Completed! Downloaded {total_downloaded:,} candles")
    
    return True

if __name__ == "__main__":
    asyncio.run(final_completion())