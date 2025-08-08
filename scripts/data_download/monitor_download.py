#!/usr/bin/env python3
"""
Monitor the download progress in real-time
"""

import os
import sys
import time
from datetime import datetime
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')

def monitor():
    engine = create_engine(DATABASE_URL)
    
    print("\033[2J\033[H")  # Clear screen
    
    while True:
        try:
            with engine.connect() as conn:
                # Total candles
                result = conn.execute(text("SELECT COUNT(*) FROM kline_data"))
                total = result.scalar()
                
                # Count by interval
                result = conn.execute(text("""
                    SELECT interval, COUNT(*) as count 
                    FROM kline_data 
                    GROUP BY interval 
                    ORDER BY interval
                """))
                intervals = {row[0]: row[1] for row in result}
                
                # Count unique symbols
                result = conn.execute(text("""
                    SELECT COUNT(DISTINCT symbol) FROM kline_data
                """))
                symbols = result.scalar()
                
                # Get recent additions
                result = conn.execute(text("""
                    SELECT symbol, interval, COUNT(*) as count
                    FROM kline_data
                    WHERE created_at > NOW() - INTERVAL '5 minutes'
                    GROUP BY symbol, interval
                    ORDER BY count DESC
                    LIMIT 5
                """))
                recent = list(result)
                
                # Database size
                result = conn.execute(text("SELECT pg_database_size('tradingbot') / 1024 / 1024 as size_mb"))
                size = result.scalar()
                
                # Display
                print("\033[2J\033[H")  # Clear screen
                print("=" * 60)
                print("DOWNLOAD MONITOR - Press Ctrl+C to stop")
                print("=" * 60)
                print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
                print(f"\n📊 Total Candles: {total:,}")
                print(f"📈 Unique Symbols: {symbols}")
                print(f"💾 Database Size: {size:.1f} MB")
                
                print("\n⏱️  By Interval:")
                for interval in ['5m', '15m', '30m', '1h', '2h', '4h', '1d']:
                    count = intervals.get(interval, 0)
                    bar = "█" * min(40, count // 10000)
                    print(f"  {interval:4s}: {count:7,} {bar}")
                
                if recent:
                    print("\n🔄 Recent Downloads (last 5 min):")
                    for row in recent:
                        print(f"  {row[0]:12s} {row[1]:4s}: {row[2]:,} candles")
                
                # Estimate
                if total > 0:
                    target = 15_600_000  # Target for 30 symbols
                    pct = (total / target) * 100
                    print(f"\n📈 Progress: {pct:.1f}% of estimated target")
                    print(f"   Remaining: {(target - total):,} candles")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(5)  # Update every 5 seconds
    
    print("\nMonitoring stopped.")

if __name__ == "__main__":
    monitor()