#!/usr/bin/env python3
"""
Finish downloading the last remaining symbols
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.infrastructure.persistence.postgres.market_data_tables import Base
from src.infrastructure.market_data.bulk_data_loader import BulkDataLoader

async def finish_remaining():
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 80)
    print("FINISHING REMAINING SYMBOLS")
    print("=" * 80)
    
    # Check what's still incomplete
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT symbol, COUNT(*) as candles
            FROM kline_data  
            WHERE symbol IN ('SUSHIUSDT', 'CRVUSDT', 'LDOUSDT', 'PENDLEUSDT', 
                           'ONDOUSDT', '1000SHIBUSDT', 'AVAXUSDT', 'BCHUSDT')
            GROUP BY symbol
            ORDER BY symbol
        """))
        existing = {row[0]: row[1] for row in result}
    
    # Symbols that still need downloading or completion
    todo = []
    
    # Check SUSHIUSDT
    if existing.get('SUSHIUSDT', 0) < 400000:
        todo.append('SUSHIUSDT')
    
    # Add completely missing symbols
    for symbol in ['CRVUSDT', 'LDOUSDT', 'PENDLEUSDT', 'ONDOUSDT', '1000SHIBUSDT']:
        if symbol not in existing:
            todo.append(symbol)
    
    # Add incomplete symbols
    if existing.get('AVAXUSDT', 0) < 400000:
        todo.append('AVAXUSDT')
    if existing.get('BCHUSDT', 0) < 400000:
        todo.append('BCHUSDT')
    
    if not todo:
        print("\n✅ All symbols are complete!")
        return True
    
    print(f"\nSymbols to download: {len(todo)}")
    print(f"{', '.join(todo)}\n")
    
    loader = BulkDataLoader(db_session)
    await loader.start()
    
    intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '1d']
    end_date = datetime.now()
    
    total_downloaded = 0
    
    # Process each symbol
    for i, symbol in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] Downloading {symbol}...")
        current = existing.get(symbol, 0)
        print(f"  Current: {current:,} candles")
        
        # Determine start date
        if symbol in ['LDOUSDT', 'PENDLEUSDT', 'ONDOUSDT']:
            start_date = end_date - timedelta(days=365 * 2)  # 2 years
        elif symbol == '1000SHIBUSDT':
            start_date = end_date - timedelta(days=365 * 3)  # 3 years
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
            else:
                print(f"  ⚠️ No new data")
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
        
        # Small pause
        await asyncio.sleep(10)
    
    await loader.stop()
    
    # Final check
    print(f"\n{'='*80}")
    print("FINAL STATUS")
    print("="*80)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                COUNT(DISTINCT symbol) as total_symbols,
                COUNT(*) as total_candles,
                pg_size_pretty(pg_database_size('tradingbot')) as db_size
            FROM kline_data
        """))
        row = result.first()
        print(f"Total symbols: {row[0]}")
        print(f"Total candles: {row[1]:,}")
        print(f"Database size: {row[2]}")
        
        # List all symbols with counts
        print("\nAll symbols in database:")
        result = conn.execute(text("""
            SELECT symbol, COUNT(*) as candles
            FROM kline_data
            GROUP BY symbol
            ORDER BY candles DESC
        """))
        for row in result:
            status = "✅" if row[1] > 200000 else "⚠️"
            print(f"  {status} {row[0]:15s}: {row[1]:,} candles")
    
    db_session.close()
    engine.dispose()
    
    print(f"\n✅ Total downloaded in this session: {total_downloaded:,} candles")
    print("Complete!")
    
    return True

if __name__ == "__main__":
    asyncio.run(finish_remaining())