#!/usr/bin/env python3
"""
Start the full 3-year historical data download for top 30 Binance Futures symbols
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

async def start_full_download():
    """Start the full 3-year download"""
    
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    
    # Setup
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 80)
    print("BINANCE FUTURES HISTORICAL DATA DOWNLOAD")
    print("=" * 80)
    print("\n⚠️  This will download 3 YEARS of data for the TOP 30 symbols")
    print("   Estimated time: 6-10 hours")
    print("   Estimated storage: 3-5 GB")
    print("   Total candles: ~15.6 million")
    
    # Get user confirmation
    if '--yes' not in sys.argv:
        response = input("\nDo you want to continue? (yes/no): ").lower()
        if response != 'yes':
            print("Download cancelled.")
            return False
    
    try:
        # Initialize services
        print("\n🚀 Initializing services...")
        loader = BulkDataLoader(db_session)
        await loader.start()
        
        event_bus = InMemoryEventBus()
        indicator_service = IndicatorService(db_session, event_bus)
        data_manager = DataManager(db_session)
        
        # Check storage
        storage = data_manager.check_storage_space()
        print(f"📊 Storage: {storage['free_gb']:.1f} GB free")
        
        if storage['free_gb'] < 10:
            print("⚠️  WARNING: Less than 10 GB free space!")
            if '--yes' not in sys.argv:
                response = input("Continue anyway? (yes/no): ").lower()
                if response != 'yes':
                    return False
        
        # Get top 30 symbols
        print("\n📈 Fetching top 30 symbols by volume...")
        symbols = await loader.get_top_futures_symbols(30)
        print(f"   Top 5: {symbols[:5]}")
        
        # Download parameters
        intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '1d']
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * 3)  # 3 years
        
        print(f"\n📥 Download Configuration:")
        print(f"   Symbols: {len(symbols)} symbols")
        print(f"   Intervals: {intervals}")
        print(f"   Period: {start_date.date()} to {end_date.date()}")
        print(f"   Workers: 4 parallel downloads")
        
        # Start download
        print("\n" + "=" * 80)
        print("STARTING DOWNLOAD - This will take several hours...")
        print("You can interrupt with Ctrl+C and resume later")
        print("=" * 80)
        
        # Download in batches of 5 symbols
        batch_size = 5
        total_downloaded = 0
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(symbols) + batch_size - 1) // batch_size
            
            print(f"\n📦 Batch {batch_num}/{total_batches}")
            print(f"   Symbols: {batch}")
            
            # Download batch
            stats = await loader.download_historical_data(
                symbols=batch,
                intervals=intervals,
                start_date=start_date,
                end_date=end_date
            )
            
            total_downloaded += stats['total_candles']
            print(f"   ✅ Downloaded {stats['total_candles']:,} candles")
            print(f"   Success rate: {stats['successful']}/{stats['total_tasks']}")
            
            # Calculate indicators for this batch
            print(f"\n📊 Calculating indicators for batch {batch_num}...")
            ind_stats = await indicator_service.batch_calculate_historical(
                symbols=batch,
                intervals=intervals,
                start_date=start_date,
                end_date=end_date,
                parallel_workers=4
            )
            print(f"   ✅ Calculated {ind_stats.get('total_indicators', 0):,} indicators")
            
            # Brief pause between batches
            if i + batch_size < len(symbols):
                print("\n⏸️  Pausing 30 seconds before next batch...")
                await asyncio.sleep(30)
        
        # Final validation
        print("\n" + "=" * 80)
        print("VALIDATING DATA...")
        print("=" * 80)
        
        validation = data_manager.validate_data_integrity(
            symbols=symbols,
            intervals=intervals,
            start_date=start_date,
            end_date=end_date
        )
        
        # Print summary
        print("\n" + "=" * 80)
        print("DOWNLOAD COMPLETE!")
        print("=" * 80)
        print(f"\n📊 Final Statistics:")
        print(f"   Total candles downloaded: {total_downloaded:,}")
        print(f"   Database size: {storage['database_size_mb']:.1f} MB")
        
        if 'summary' in validation:
            s = validation['summary']
            print(f"\n✅ Data Validation:")
            print(f"   Complete: {s.get('complete', 0)}")
            print(f"   Incomplete: {s.get('incomplete', 0)}")
            print(f"   Missing: {s.get('missing', 0)}")
            if 'completeness_pct' in s:
                print(f"   Overall completeness: {s['completeness_pct']:.1f}%")
        
        # Optimize database
        print("\n🔧 Optimizing database...")
        opt_stats = data_manager.optimize_database()
        print(f"   Tables analyzed: {len(opt_stats.get('tables_analyzed', []))}")
        
        # Save report
        report_file = f"download_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(report_file, 'w') as f:
            json.dump({
                'symbols': symbols,
                'intervals': intervals,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_candles': total_downloaded,
                'validation': validation if 'summary' in validation else {}
            }, f, indent=2, default=str)
        
        print(f"\n📄 Report saved to: {report_file}")
        
        # Cleanup
        await loader.stop()
        await indicator_service.stop()
        db_session.close()
        engine.dispose()
        
        print("\n✨ Full download completed successfully!")
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        print("Progress has been saved. Run again to resume.")
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(start_full_download())
    sys.exit(0 if success else 1)