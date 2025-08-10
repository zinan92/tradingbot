#!/usr/bin/env python3
"""
Fix missing indicators for failed tests
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.indicators.indicator_service import IndicatorService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository

DATABASE_URL = 'postgresql://localhost/tradingbot'


async def fix_missing_indicators():
    """Calculate missing indicators for failed tests"""
    
    print("Fixing missing indicators...")
    
    # Setup database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    # Setup services
    event_bus = InMemoryEventBus()
    indicator_service = IndicatorService(
        db_session=db_session,
        event_bus=event_bus
    )
    repository = MarketDataRepository(db_session)
    
    # Update enabled indicators to include the ones we need
    indicator_service.enabled_indicators = [
        'rsi', 'macd', 'macd_signal', 'macd_histogram', 
        'ema_12', 'ema_50', 'ema_200', 'atr'
    ]
    
    # Fix 1: Calculate all indicators for Solana 15m (including MACD components)
    print("\n1. Fixing Solana MACD (calculating all components)...")
    
    await indicator_service.calculate_and_publish(
        symbol='SOLUSDT',
        interval='15m',
        lookback_periods=500
    )
    print("  - Calculated indicators for SOLUSDT 15m")
    
    # Fix 2: Calculate indicators for BNB 1h
    print("\n2. Calculating indicators for BNB 1h...")
    
    await indicator_service.calculate_and_publish(
        symbol='BNBUSDT',
        interval='1h',
        lookback_periods=500
    )
    print("  - Calculated indicators for BNBUSDT 1h")
    
    # Verify the fixes
    print("\n4. Verifying fixes...")
    
    with engine.connect() as conn:
        # Check Solana MACD components
        result = conn.execute(text("""
            SELECT indicator_name, COUNT(*) as count 
            FROM indicator_values 
            WHERE symbol = 'SOLUSDT' 
                AND timeframe = '15m' 
                AND indicator_name IN ('macd', 'macd_signal', 'macd_histogram')
            GROUP BY indicator_name
            ORDER BY indicator_name
        """))
        
        print("\nSolana MACD components:")
        for row in result:
            print(f"  - {row.indicator_name}: {row.count:,} data points")
        
        # Check BNB EMA indicators
        result = conn.execute(text("""
            SELECT indicator_name, COUNT(*) as count 
            FROM indicator_values 
            WHERE symbol = 'BNBUSDT' 
                AND timeframe = '1h' 
                AND indicator_name LIKE 'ema%'
            GROUP BY indicator_name
            ORDER BY indicator_name
        """))
        
        print("\nBNB EMA indicators:")
        for row in result:
            print(f"  - {row.indicator_name}: {row.count:,} data points")
    
    # Clean up
    for task_id in list(indicator_service.calculation_tasks.keys()):
        indicator_service.calculation_tasks[task_id].cancel()
    
    db_session.close()
    engine.dispose()
    
    print("\n✅ Indicator fixes complete!")


if __name__ == "__main__":
    asyncio.run(fix_missing_indicators())