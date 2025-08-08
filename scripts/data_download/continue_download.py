#!/usr/bin/env python3
"""
Continue download from Batch 2 onwards, skipping indicator calculation
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
from src.infrastructure.market_data.data_manager import DataManager

async def continue_download():
    """Continue download from Batch 2"""
    
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    
    # Setup
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 80)
    print("CONTINUING DOWNLOAD FROM BATCH 2")
    print("=" * 80)
    
    # Remaining symbols (Batch 2-5)
    remaining_symbols = [
        # Batch 2
        'LTCUSDT', 'ADAUSDT', 'BNBUSDT', 'FARTCOINUSDT', 'LINKUSDT',
        # Batch 3
        'BCHUSDT', 'AVAXUSDT', 'WIFUSDT', 'AAVEUSDT', 'JUPUSDT',
        # Batch 4
        '1000BONKUSDT', 'JTOUSDT', 'UNIUSDT', 'SUSHIUSDT', 'CRVUSDT',
        # Batch 5
        'LDOUSDT', 'PENDLEUSDT', 'ONDOUSDT', '1000SHIBUSDT'
    ]
    
    # Note: BNBUSDT has partial data but we'll re-download fully
    
    print(f"\n📊 Symbols to Download: {len(remaining_symbols)}")
    print(f"   Batch 2: LTCUSDT, ADAUSDT, BNBUSDT, FARTCOINUSDT, LINKUSDT")
    print(f"   Batch 3: BCHUSDT, AVAXUSDT, WIFUSDT, AAVEUSDT, JUPUSDT")
    print(f"   Batch 4: 1000BONKUSDT, JTOUSDT, UNIUSDT, SUSHIUSDT, CRVUSDT")
    print(f"   Batch 5: LDOUSDT, PENDLEUSDT, ONDOUSDT, 1000SHIBUSDT")
    
    print(f"\n⚠️  Skipping indicator calculation to avoid hanging")
    print(f"   Estimated time: {len(remaining_symbols) * 0.2:.1f} - {len(remaining_symbols) * 0.3:.1f} hours")
    
    try:
        # Initialize services
        print("\n🚀 Initializing services...")
        loader = BulkDataLoader(db_session)
        await loader.start()
        
        data_manager = DataManager(db_session)
        
        # Check storage
        storage = data_manager.check_storage_space()
        print(f"📊 Storage: {storage['free_gb']:.1f} GB free")
        
        # Download parameters
        intervals = ['5m', '15m', '30m', '1h', '2h', '4h', '1d']
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * 3)  # 3 years
        
        print(f"\n📥 Download Configuration:")
        print(f"   Symbols: {len(remaining_symbols)} symbols")
        print(f"   Intervals: {intervals}")
        print(f"   Period: {start_date.date()} to {end_date.date()}")
        print(f"   Workers: 4 parallel downloads")
        
        # Start download
        print("\n" + "=" * 80)
        print("STARTING DOWNLOAD")
        print("=" * 80)
        
        # Download in batches of 5 symbols
        batch_size = 5
        total_downloaded = 0
        batch_start = 2  # Starting from batch 2
        
        for i in range(0, len(remaining_symbols), batch_size):
            batch = remaining_symbols[i:i + batch_size]
            batch_num = batch_start + (i // batch_size)
            total_batches = 5  # Total original batches
            
            print(f"\n📦 Batch {batch_num}/{total_batches}")
            print(f"   Symbols: {batch}")
            
            # Download batch
            try:
                stats = await loader.download_historical_data(
                    symbols=batch,
                    intervals=intervals,
                    start_date=start_date,
                    end_date=end_date
                )
                
                total_downloaded += stats['total_candles']
                print(f"   ✅ Downloaded {stats['total_candles']:,} candles")
                print(f"   Success rate: {stats['successful']}/{stats['total_tasks']}")
            except Exception as e:
                print(f"   ⚠️ Error in batch {batch_num}: {e}")
                print("   Continuing with next batch...")
            
            # Brief pause between batches
            if i + batch_size < len(remaining_symbols):
                print("\n⏸️  Pausing 30 seconds before next batch...")
                await asyncio.sleep(30)
        
        # Print summary
        print("\n" + "=" * 80)
        print("DOWNLOAD COMPLETE!")
        print("=" * 80)
        print(f"\n📊 Final Statistics:")
        print(f"   New candles downloaded: {total_downloaded:,}")
        
        # Check final database size
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("""
                SELECT 
                    COUNT(DISTINCT symbol) as symbols,
                    COUNT(*) as total_candles,
                    pg_size_pretty(pg_database_size('tradingbot')) as db_size
                FROM kline_data
            """))
            row = result.first()
            print(f"   Total symbols in database: {row[0]}")
            print(f"   Total candles in database: {row[1]:,}")
            print(f"   Database size: {row[2]}")
        
        # Save report
        report_file = f"download_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(report_file, 'w') as f:
            json.dump({
                'completed_symbols': remaining_symbols,
                'intervals': intervals,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_candles_downloaded': total_downloaded,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\n📄 Report saved to: {report_file}")
        
        # Cleanup
        await loader.stop()
        db_session.close()
        engine.dispose()
        
        print("\n✨ Download completed successfully!")
        print("\nNote: Indicators not calculated. Run calculate_specific_indicators.py separately if needed.")
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
    success = asyncio.run(continue_download())
    sys.exit(0 if success else 1)