#!/usr/bin/env python3
"""
Test database connection and setup before running full download
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

# Add parent directory to path
# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.infrastructure.persistence.postgres.market_data_tables import Base
from src.infrastructure.market_data.bulk_data_loader import BulkDataLoader

async def test_connection():
    """Test database connection and basic functionality"""
    
    # Database URL - update this with your actual credentials
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost/tradingbot')
    
    print("=" * 60)
    print("Testing Database Connection and Setup")
    print("=" * 60)
    
    try:
        # Test database connection
        print(f"\n1. Testing connection to: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"   ✅ Connected to PostgreSQL")
            print(f"   Version: {version[:50]}...")
        
        # Create tables
        print("\n2. Creating database tables...")
        Base.metadata.create_all(engine)
        print("   ✅ Tables created/verified")
        
        # List tables
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('kline_data', 'indicator_values', 'market_metrics', 'symbol_info')
            """))
            tables = [row[0] for row in result]
            print(f"   Found tables: {', '.join(tables)}")
        
        # Test Binance connection
        print("\n3. Testing Binance API connection...")
        Session = sessionmaker(bind=engine)
        db_session = Session()
        
        loader = BulkDataLoader(db_session)
        await loader.start()
        
        # Get top symbols
        print("   Fetching top 3 symbols by volume...")
        symbols = await loader.get_top_futures_symbols(3)
        print(f"   ✅ Top symbols: {symbols}")
        
        # Test small data download
        print("\n4. Testing small data download (1 day of 1h data for BTCUSDT)...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        result = await loader.download_historical_data(
            symbols=['BTCUSDT'],
            intervals=['1h'],
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"   ✅ Downloaded {result['total_candles']} candles")
        
        # Check data in database
        from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository
        repo = MarketDataRepository(db_session)
        
        count = repo.count_klines('BTCUSDT', '1h')
        print(f"   ✅ Database contains {count} BTCUSDT 1h candles")
        
        # Cleanup
        await loader.stop()
        db_session.close()
        engine.dispose()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! Ready to run full download.")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nPlease check:")
        print("1. PostgreSQL is running")
        print("2. Database credentials are correct")
        print("3. Database 'tradingbot' exists")
        print("\nTo create database: createdb tradingbot")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)