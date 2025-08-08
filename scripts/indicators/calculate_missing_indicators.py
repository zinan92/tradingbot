#!/usr/bin/env python3
"""
Calculate missing indicators for completed symbols
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
from src.infrastructure.indicators.indicator_service import IndicatorService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

async def calculate_missing_indicators():
    """Calculate indicators for BTC, ETH, SOL"""
    
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    
    # Setup
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 80)
    print("CALCULATING MISSING INDICATORS")
    print("=" * 80)
    
    # Symbols to process
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '1d']
    
    # Date range (3 years)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 3)
    
    print(f"\n📊 Processing Symbols: {', '.join(symbols)}")
    print(f"⏱️  Intervals: {', '.join(intervals)}")
    print(f"📅 Period: {start_date.date()} to {end_date.date()}")
    print(f"🔧 Workers: 4 parallel processes")
    
    try:
        # Initialize services
        print("\n🚀 Initializing indicator service...")
        event_bus = InMemoryEventBus()
        indicator_service = IndicatorService(db_session, event_bus)
        
        # Process each symbol
        for symbol in symbols:
            print(f"\n{'='*60}")
            print(f"Processing {symbol}")
            print(f"{'='*60}")
            
            # Calculate indicators for all intervals
            print(f"📊 Calculating indicators for {symbol}...")
            
            stats = await indicator_service.batch_calculate_historical(
                symbols=[symbol],
                intervals=intervals,
                start_date=start_date,
                end_date=end_date,
                parallel_workers=4
            )
            
            print(f"✅ Completed {symbol}:")
            print(f"   Total indicators calculated: {stats.get('total_indicators', 0):,}")
            print(f"   Time taken: {stats.get('elapsed_time', 'N/A')}")
            
            if 'errors' in stats and stats['errors']:
                print(f"   ⚠️  Errors: {len(stats['errors'])}")
                for error in stats['errors'][:3]:  # Show first 3 errors
                    print(f"      - {error}")
        
        # Verify results
        print("\n" + "="*80)
        print("VERIFICATION")
        print("="*80)
        
        with engine.connect() as conn:
            from sqlalchemy import text
            
            result = conn.execute(text("""
                SELECT 
                    symbol,
                    timeframe,
                    COUNT(DISTINCT indicator_name) as indicators,
                    COUNT(*) as total_values
                FROM indicator_values
                WHERE symbol IN ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
                GROUP BY symbol, timeframe
                ORDER BY symbol, timeframe
            """))
            
            current_symbol = None
            for row in result:
                if current_symbol != row[0]:
                    if current_symbol:
                        print()
                    print(f"\n{row[0]}:")
                    current_symbol = row[0]
                print(f"  {row[1]:4s}: {row[2]:2d} indicators, {row[3]:,} values")
        
        # Cleanup
        await indicator_service.stop()
        db_session.close()
        engine.dispose()
        
        print("\n✨ Indicator calculation completed successfully!")
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Calculation interrupted by user")
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(calculate_missing_indicators())
    sys.exit(0 if success else 1)