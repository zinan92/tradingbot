#!/usr/bin/env python3
"""
Monitor live data updates
"""

import os
import sys
import time
from datetime import datetime
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')

def check_updates():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Check all symbols
        result = conn.execute(text('''
            SELECT 
                symbol,
                MAX(open_time) as latest,
                NOW() AT TIME ZONE 'UTC' as current_time,
                COUNT(*) as total_count
            FROM kline_data
            GROUP BY symbol
            ORDER BY symbol
        '''))
        
        print("\n" + "="*80)
        print(f"Data Update Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        live_count = 0
        delayed_count = 0
        stale_count = 0
        
        for row in result:
            latest = row.latest
            current = row.current_time
            diff = (current - latest).total_seconds() / 60
            
            if diff < 10:
                status = '🟢 LIVE'
                live_count += 1
            elif diff < 60:
                status = '🟡 DELAYED'
                delayed_count += 1
            else:
                status = '🔴 STALE'
                stale_count += 1
            
            print(f'{row.symbol:15} {status:12} Last: {latest.strftime("%H:%M")} ({diff:.0f} min ago) [{row.total_count:,} total]')
        
        print("-"*80)
        print(f'Summary: 🟢 Live: {live_count}  🟡 Delayed: {delayed_count}  🔴 Stale: {stale_count}')
        
        # Check recent activity
        result2 = conn.execute(text('''
            SELECT COUNT(*) as recent_count
            FROM kline_data
            WHERE open_time > NOW() AT TIME ZONE 'UTC' - INTERVAL '10 minutes'
        '''))
        
        recent = result2.fetchone().recent_count
        print(f'Candles added in last 10 minutes: {recent:,}')
    
    engine.dispose()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        # Continuous monitoring
        while True:
            os.system('clear')
            check_updates()
            time.sleep(30)
    else:
        # Single check
        check_updates()