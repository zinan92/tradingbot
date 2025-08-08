#!/usr/bin/env python3
"""
Simple direct download for remaining symbols
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.persistence.postgres.market_data_tables import Base
from src.infrastructure.market_data.bulk_data_loader import BulkDataLoader

async def simple_download():
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 80)
    print("SIMPLE DOWNLOAD FOR REMAINING SYMBOLS")
    print("=" * 80)
    
    # List of symbols to download
    remaining_symbols = [
        # Missing completely
        '1000BONKUSDT', 'JTOUSDT', 'UNIUSDT', 'SUSHIUSDT', 'CRVUSDT',
        'LDOUSDT', 'PENDLEUSDT', 'ONDOUSDT', '1000SHIBUSDT',
        # Need more data
        'AVAXUSDT', 'BCHUSDT', 'FARTCOINUSDT', 'JUPUSDT', 'WIFUSDT'
    ]
    
    print(f"\nSymbols to download: {len(remaining_symbols)}")
    print(f"{', '.join(remaining_symbols)}\n")
    
    loader = BulkDataLoader(db_session)
    await loader.start()
    
    intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '1d']
    end_date = datetime.now()
    
    total_downloaded = 0
    
    # Process each symbol individually
    for i, symbol in enumerate(remaining_symbols, 1):
        print(f"\n[{i}/{len(remaining_symbols)}] Downloading {symbol}...")
        
        # Determine start date based on symbol age
        if symbol == 'FARTCOINUSDT':
            start_date = end_date - timedelta(days=180)  # 6 months
        elif symbol in ['1000BONKUSDT', 'JTOUSDT', 'WIFUSDT', 'JUPUSDT', 
                       'LDOUSDT', 'PENDLEUSDT', 'ONDOUSDT']:
            start_date = end_date - timedelta(days=365 * 1.5)  # 1.5 years
        else:
            start_date = end_date - timedelta(days=365 * 3)  # 3 years
        
        print(f"  Period: {start_date.date()} to {end_date.date()}")
        
        try:
            stats = await loader.download_historical_data(
                symbols=[symbol],
                intervals=intervals,
                start_date=start_date,
                end_date=end_date
            )
            
            if stats['total_candles'] > 0:
                total_downloaded += stats['total_candles']
                print(f"  ✅ Downloaded {stats['total_candles']:,} candles")
                print(f"  Success rate: {stats['successful']}/{stats['total_tasks']}")
            else:
                print(f"  ⚠️ No new data")
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
        
        # Small pause between symbols
        await asyncio.sleep(10)
    
    await loader.stop()
    db_session.close()
    engine.dispose()
    
    print(f"\n{'='*80}")
    print(f"✅ Total downloaded: {total_downloaded:,} candles")
    print("Download complete!")
    
    return True

if __name__ == "__main__":
    asyncio.run(simple_download())