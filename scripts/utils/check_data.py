#!/usr/bin/env python3
"""
Check what data is currently in the database
"""

import os
import sys
from sqlalchemy import create_engine, text
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')

def check_data():
    engine = create_engine(DATABASE_URL)
    
    print("=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Total candles
        result = conn.execute(text("SELECT COUNT(*) FROM kline_data"))
        total = result.scalar()
        print(f"\n📊 Total Candles: {total:,}")
        
        # By symbol
        result = conn.execute(text("""
            SELECT symbol, COUNT(*) as count 
            FROM kline_data 
            GROUP BY symbol 
            ORDER BY count DESC 
            LIMIT 10
        """))
        print("\n📈 Top Symbols:")
        for row in result:
            print(f"   {row[0]}: {row[1]:,} candles")
        
        # By interval
        result = conn.execute(text("""
            SELECT interval, COUNT(*) as count 
            FROM kline_data 
            GROUP BY interval 
            ORDER BY count DESC
        """))
        print("\n⏱️  By Interval:")
        for row in result:
            print(f"   {row[0]}: {row[1]:,} candles")
        
        # Date range
        result = conn.execute(text("""
            SELECT MIN(open_time) as earliest, MAX(open_time) as latest 
            FROM kline_data
        """))
        row = result.first()
        if row and row[0]:
            print(f"\n📅 Date Range:")
            print(f"   From: {row[0]}")
            print(f"   To: {row[1]}")
            days = (row[1] - row[0]).days
            print(f"   Duration: {days} days")
        
        # Indicators
        result = conn.execute(text("SELECT COUNT(*) FROM indicator_values"))
        indicators = result.scalar()
        print(f"\n📊 Total Indicators: {indicators:,}")
        
        # Database size
        result = conn.execute(text("SELECT pg_database_size('tradingbot') / 1024 / 1024 as size_mb"))
        size = result.scalar()
        print(f"\n💾 Database Size: {size:.1f} MB")
        
        # Table sizes
        result = conn.execute(text("""
            SELECT 
                tablename,
                pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS size
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(tablename::regclass) DESC
            LIMIT 5
        """))
        print("\n📦 Largest Tables:")
        for row in result:
            print(f"   {row[0]}: {row[1]}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_data()