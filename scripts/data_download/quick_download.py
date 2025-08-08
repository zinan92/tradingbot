#!/usr/bin/env python3
"""
Quick download script for testing - downloads 7 days of data for 2 symbols
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
from src.infrastructure.indicators.indicator_service import IndicatorService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.market_data.data_manager import DataManager

async def quick_download():
    """Quick download for testing"""
    
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    
    # Setup
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 60)
    print("Quick Download - 7 days of data for BTCUSDT and ETHUSDT")
    print("=" * 60)
    
    try:
        # Initialize services
        loader = BulkDataLoader(db_session)
        await loader.start()
        
        event_bus = InMemoryEventBus()
        indicator_service = IndicatorService(db_session, event_bus)
        data_manager = DataManager(db_session)
        
        # Check storage
        storage = data_manager.check_storage_space()
        print(f"\n📊 Storage: {storage['free_gb']:.1f} GB free")
        
        # Download parameters
        symbols = ['BTCUSDT', 'ETHUSDT']
        intervals = ['1h', '4h', '1d']  # Just 3 intervals for quick test
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)  # Only 7 days
        
        print(f"\n📥 Downloading:")
        print(f"   Symbols: {symbols}")
        print(f"   Intervals: {intervals}")
        print(f"   Period: {start_date.date()} to {end_date.date()}")
        
        # Download data
        print("\n⏳ Downloading market data...")
        download_stats = await loader.download_historical_data(
            symbols=symbols,
            intervals=intervals,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"\n✅ Downloaded {download_stats['total_candles']} candles")
        print(f"   Successful: {download_stats['successful']}/{download_stats['total_tasks']}")
        
        # Calculate indicators
        print("\n📊 Calculating indicators...")
        indicator_stats = await indicator_service.batch_calculate_historical(
            symbols=symbols,
            intervals=intervals,
            start_date=start_date,
            end_date=end_date,
            parallel_workers=2
        )
        
        print(f"✅ Calculated {indicator_stats.get('total_indicators', 0)} indicators")
        
        # Validate data
        print("\n🔍 Validating data...")
        validation = data_manager.validate_data_integrity(
            symbols=symbols,
            intervals=intervals,
            start_date=start_date,
            end_date=end_date
        )
        
        if 'summary' in validation:
            summary = validation['summary']
            print(f"✅ Validation complete:")
            print(f"   Total tasks: {summary.get('total_tasks', 0)}")
            print(f"   Complete: {summary.get('complete', 0)}")
            print(f"   Incomplete: {summary.get('incomplete', 0)}")
            if 'completeness_pct' in summary:
                print(f"   Completeness: {summary['completeness_pct']:.1f}%")
        else:
            print("✅ Validation complete")
        
        # Get some stats
        from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository
        repo = MarketDataRepository(db_session)
        
        print("\n📈 Database Statistics:")
        for symbol in symbols:
            for interval in intervals:
                count = repo.count_klines(symbol, interval, start_date, end_date)
                print(f"   {symbol} {interval}: {count} candles")
        
        # Get latest price
        latest = repo.get_latest_kline('BTCUSDT', '1h')
        if latest:
            print(f"\n💰 Latest BTC Price: ${latest.close_price:,.2f}")
        
        # Cleanup
        await loader.stop()
        await indicator_service.stop()
        db_session.close()
        engine.dispose()
        
        print("\n" + "=" * 60)
        print("✨ Quick download completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(quick_download())
    sys.exit(0 if success else 1)