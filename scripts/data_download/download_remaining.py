#!/usr/bin/env python3
"""
Download remaining symbols and complete partial downloads
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
from src.infrastructure.market_data.data_manager import DataManager

async def download_remaining():
    """Download remaining and incomplete symbols"""
    
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
    
    # Setup
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    print("=" * 80)
    print("DOWNLOADING REMAINING AND INCOMPLETE SYMBOLS")
    print("=" * 80)
    
    # Check what we currently have
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT symbol, COUNT(*) as candles
            FROM kline_data
            GROUP BY symbol
            ORDER BY symbol
        """))
        existing_data = {row[0]: row[1] for row in result}
    
    # Define target symbols and expected candles (approximate)
    # Full 3-year data should have ~520k candles
    # Newer coins will have less
    target_symbols = {
        # Failed symbols from Batch 4-5
        '1000BONKUSDT': 400000,  # newer coin
        'JTOUSDT': 400000,       # newer coin
        'UNIUSDT': 520000,       # older coin
        'SUSHIUSDT': 520000,     # older coin
        'CRVUSDT': 520000,       # older coin
        'LDOUSDT': 400000,       # newer coin
        'PENDLEUSDT': 400000,    # newer coin
        'ONDOUSDT': 400000,      # newer coin
        '1000SHIBUSDT': 520000,  # older coin
        
        # Partial downloads that need completion
        'FARTCOINUSDT': 200000,  # very new coin
        'BCHUSDT': 520000,       # should be complete
        'AVAXUSDT': 520000,      # should be complete
        'WIFUSDT': 400000,       # newer coin
        'JUPUSDT': 400000,       # newer coin
    }
    
    # Identify symbols to download
    symbols_to_download = []
    
    for symbol, expected_candles in target_symbols.items():
        current_candles = existing_data.get(symbol, 0)
        # Download if missing or has less than 80% of expected data
        if current_candles < expected_candles * 0.8:
            symbols_to_download.append(symbol)
            print(f"  {symbol}: {current_candles:,} candles (need ~{expected_candles:,})")
    
    if not symbols_to_download:
        print("\nAll symbols are already complete!")
        return True
    
    print(f"\n📊 Symbols to Download/Complete: {len(symbols_to_download)}")
    print(f"   {', '.join(symbols_to_download)}")
    
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
        
        print(f"\n📥 Download Configuration:")
        print(f"   Symbols: {len(symbols_to_download)} symbols")
        print(f"   Intervals: {intervals}")
        print(f"   Workers: 4 parallel downloads")
        print(f"   Note: Will download all available history for each symbol")
        
        # Start download
        print("\n" + "=" * 80)
        print("STARTING DOWNLOAD")
        print("=" * 80)
        
        # Download in batches of 3 symbols (smaller batches for stability)
        batch_size = 3
        total_downloaded = 0
        
        for i in range(0, len(symbols_to_download), batch_size):
            batch = symbols_to_download[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(symbols_to_download) + batch_size - 1) // batch_size
            
            print(f"\n📦 Batch {batch_num}/{total_batches}")
            print(f"   Symbols: {batch}")
            
            for symbol in batch:
                print(f"\n   Downloading {symbol}...")
                
                # For newer coins, adjust start date
                if symbol in ['FARTCOINUSDT']:
                    start_date = end_date - timedelta(days=365)  # 1 year
                elif symbol in ['1000BONKUSDT', 'JTOUSDT', 'LDOUSDT', 'PENDLEUSDT', 
                               'ONDOUSDT', 'WIFUSDT', 'JUPUSDT']:
                    start_date = end_date - timedelta(days=365 * 2)  # 2 years
                else:
                    start_date = end_date - timedelta(days=365 * 3)  # 3 years
                
                try:
                    # Download single symbol
                    stats = await loader.download_historical_data(
                        symbols=[symbol],
                        intervals=intervals,
                        start_date=start_date,
                        end_date=end_date,
                        retry_failed=True  # Retry failed downloads
                    )
                    
                    if stats['total_candles'] > 0:
                        total_downloaded += stats['total_candles']
                        print(f"      ✅ Downloaded {stats['total_candles']:,} candles")
                    else:
                        print(f"      ⚠️ No new data downloaded (may be complete)")
                        
                except Exception as e:
                    print(f"      ❌ Error downloading {symbol}: {str(e)[:100]}")
                    # Continue with next symbol
                
                # Brief pause between symbols
                await asyncio.sleep(5)
            
            # Pause between batches
            if i + batch_size < len(symbols_to_download):
                print("\n⏸️  Pausing 20 seconds before next batch...")
                await asyncio.sleep(20)
        
        # Print summary
        print("\n" + "=" * 80)
        print("DOWNLOAD COMPLETE!")
        print("=" * 80)
        print(f"\n📊 Final Statistics:")
        print(f"   New candles downloaded: {total_downloaded:,}")
        
        # Check final database status
        with engine.connect() as conn:
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
            
            # Show final symbol status
            print("\n📋 Symbol Status:")
            result = conn.execute(text("""
                SELECT symbol, COUNT(*) as candles
                FROM kline_data
                WHERE symbol IN :symbols
                GROUP BY symbol
                ORDER BY symbol
            """), {'symbols': tuple(target_symbols.keys())})
            
            for row in result:
                expected = target_symbols.get(row[0], 520000)
                pct = (row[1] / expected) * 100
                status = "✅" if pct >= 80 else "⚠️"
                print(f"   {status} {row[0]}: {row[1]:,} candles ({pct:.1f}% complete)")
        
        # Save report
        report_file = f"remaining_download_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(report_file, 'w') as f:
            json.dump({
                'attempted_symbols': symbols_to_download,
                'total_candles_downloaded': total_downloaded,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"\n📄 Report saved to: {report_file}")
        
        # Cleanup
        await loader.stop()
        db_session.close()
        engine.dispose()
        
        print("\n✨ Remaining symbols download completed!")
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(download_remaining())
    sys.exit(0 if success else 1)