#!/usr/bin/env python3
"""
Comprehensive Data and Indicator Validation Test Suite

This script runs 10 different test scenarios to validate:
- Data completeness and accuracy
- Indicator calculations
- Data consistency across timeframes
- Gap detection and data integrity
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from tabulate import tabulate
import warnings
warnings.filterwarnings('ignore')

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
engine = create_engine(DATABASE_URL)

class DataValidationTests:
    """Test suite for market data validation"""
    
    def __init__(self):
        self.engine = engine
        self.results = []
        self.test_count = 0
        self.passed_count = 0
        
    def calculate_expected_candles(self, start_date: datetime, end_date: datetime, interval: str) -> int:
        """Calculate expected number of candles for a given period and interval"""
        duration = end_date - start_date
        minutes = duration.total_seconds() / 60
        
        interval_minutes = {
            '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240,
            '1d': 1440, '1w': 10080
        }
        
        if interval in interval_minutes:
            return int(minutes / interval_minutes[interval])
        return 0
    
    def run_test(self, test_name: str, test_func):
        """Run a test and record results"""
        self.test_count += 1
        print(f"\n{'='*80}")
        print(f"Test {self.test_count}: {test_name}")
        print('='*80)
        
        try:
            result = test_func()
            if result['passed']:
                self.passed_count += 1
                status = "✅ PASSED"
            else:
                status = "❌ FAILED"
            
            result['test_name'] = test_name
            result['status'] = status
            self.results.append(result)
            
            # Print result summary
            print(f"\nStatus: {status}")
            if 'details' in result:
                print(f"Details: {result['details']}")
            if 'metrics' in result:
                print("\nMetrics:")
                for key, value in result['metrics'].items():
                    print(f"  {key}: {value}")
                    
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            self.results.append({
                'test_name': test_name,
                'status': '❌ ERROR',
                'error': str(e),
                'passed': False
            })
    
    def test_1_bitcoin_5min_data(self) -> Dict:
        """Test 1: Bitcoin 5-minute data from Aug 1, 2024 to Aug 1, 2025"""
        with self.engine.connect() as conn:
            # Note: Since we only have data up to today (Aug 8, 2025), adjust the date range
            start_date = datetime(2024, 8, 1)
            end_date = datetime(2025, 8, 1)  # Future date, will use latest available
            
            # Get actual latest date
            latest_result = conn.execute(text("""
                SELECT MAX(open_time) as latest 
                FROM kline_data 
                WHERE symbol = 'BTCUSDT' AND interval = '5m'
            """))
            latest_date = latest_result.fetchone().latest
            
            # Adjust end date if it's in the future
            if latest_date and latest_date < end_date:
                end_date = latest_date
            
            # Query data
            result = conn.execute(text("""
                SELECT COUNT(*) as count,
                       MIN(open_time) as earliest,
                       MAX(open_time) as latest,
                       COUNT(DISTINCT DATE(open_time)) as days_covered
                FROM kline_data
                WHERE symbol = 'BTCUSDT' 
                AND interval = '5m'
                AND open_time >= :start_date
                AND open_time <= :end_date
            """), {'start_date': start_date, 'end_date': end_date})
            
            row = result.fetchone()
            actual_count = row.count
            
            # Calculate expected candles
            expected_count = self.calculate_expected_candles(start_date, end_date, '5m')
            
            # Check for gaps
            gaps_result = conn.execute(text("""
                WITH time_series AS (
                    SELECT open_time,
                           LAG(open_time) OVER (ORDER BY open_time) as prev_time
                    FROM kline_data
                    WHERE symbol = 'BTCUSDT' 
                    AND interval = '5m'
                    AND open_time >= :start_date
                    AND open_time <= :end_date
                )
                SELECT COUNT(*) as gap_count
                FROM time_series
                WHERE prev_time IS NOT NULL
                AND open_time - prev_time > INTERVAL '5 minutes'
            """), {'start_date': start_date, 'end_date': end_date})
            
            gaps = gaps_result.fetchone().gap_count
            
            # Calculate completeness
            completeness = (actual_count / expected_count * 100) if expected_count > 0 else 0
            
            print(f"Date Range: {start_date.date()} to {end_date.date()}")
            print(f"Expected Candles: {expected_count:,}")
            print(f"Actual Candles: {actual_count:,}")
            print(f"Completeness: {completeness:.2f}%")
            print(f"Data Gaps: {gaps}")
            
            return {
                'passed': completeness >= 95 and gaps == 0,
                'metrics': {
                    'expected_candles': expected_count,
                    'actual_candles': actual_count,
                    'completeness_pct': f"{completeness:.2f}%",
                    'gaps_found': gaps,
                    'days_covered': row.days_covered
                },
                'details': f"Bitcoin 5m data from {start_date.date()} to {end_date.date()}"
            }
    
    def test_2_ethereum_rsi(self) -> Dict:
        """Test 2: Ethereum RSI for past 3 months on hourly data"""
        with self.engine.connect() as conn:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            
            # Get RSI data
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as rsi_count,
                    MIN(value) as min_rsi,
                    MAX(value) as max_rsi,
                    AVG(value) as avg_rsi,
                    STDDEV(value) as std_rsi
                FROM indicator_values
                WHERE symbol = 'ETHUSDT'
                AND indicator_name = 'rsi'
                AND timeframe = '1h'
                AND timestamp >= :start_date
            """), {'start_date': start_date})
            
            row = result.fetchone()
            
            # Get candle count for comparison
            candle_result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM kline_data
                WHERE symbol = 'ETHUSDT'
                AND interval = '1h'
                AND open_time >= :start_date
            """), {'start_date': start_date})
            
            candle_count = candle_result.fetchone().count
            expected_candles = 90 * 24  # 90 days * 24 hours
            
            # Validate RSI values
            rsi_valid = True
            if row.rsi_count > 0:
                rsi_valid = (0 <= row.min_rsi <= 100) and (0 <= row.max_rsi <= 100)
            
            print(f"Period: Past 90 days (hourly)")
            print(f"RSI Data Points: {row.rsi_count:,}")
            print(f"Candles Available: {candle_count:,}")
            print(f"RSI Range: {row.min_rsi:.2f} - {row.max_rsi:.2f}")
            print(f"Average RSI: {row.avg_rsi:.2f}")
            print(f"RSI Std Dev: {row.std_rsi:.2f}")
            
            return {
                'passed': row.rsi_count > 0 and rsi_valid,
                'metrics': {
                    'rsi_data_points': row.rsi_count,
                    'candles_available': candle_count,
                    'min_rsi': f"{row.min_rsi:.2f}" if row.min_rsi else 'N/A',
                    'max_rsi': f"{row.max_rsi:.2f}" if row.max_rsi else 'N/A',
                    'avg_rsi': f"{row.avg_rsi:.2f}" if row.avg_rsi else 'N/A',
                    'rsi_valid_range': rsi_valid
                },
                'details': f"ETH RSI validation for past 3 months"
            }
    
    def test_3_solana_macd(self) -> Dict:
        """Test 3: Solana MACD for past week on 15-minute intervals"""
        with self.engine.connect() as conn:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            # Get MACD data
            result = conn.execute(text("""
                SELECT 
                    indicator_name,
                    COUNT(*) as count,
                    MIN(value) as min_val,
                    MAX(value) as max_val
                FROM indicator_values
                WHERE symbol = 'SOLUSDT'
                AND indicator_name IN ('macd', 'macd_signal', 'macd_histogram')
                AND timeframe = '15m'
                AND timestamp >= :start_date
                GROUP BY indicator_name
            """), {'start_date': start_date})
            
            macd_data = {row.indicator_name: {
                'count': row.count,
                'min': row.min_val,
                'max': row.max_val
            } for row in result}
            
            expected_candles = 7 * 24 * 4  # 7 days * 24 hours * 4 per hour
            
            # Check for MACD crossovers
            crossover_result = conn.execute(text("""
                WITH macd_values AS (
                    SELECT 
                        timestamp,
                        MAX(CASE WHEN indicator_name = 'macd' THEN value END) as macd,
                        MAX(CASE WHEN indicator_name = 'macd_signal' THEN value END) as signal
                    FROM indicator_values
                    WHERE symbol = 'SOLUSDT'
                    AND indicator_name IN ('macd', 'macd_signal')
                    AND timeframe = '15m'
                    AND timestamp >= :start_date
                    GROUP BY timestamp
                ),
                crossovers AS (
                    SELECT 
                        timestamp,
                        macd,
                        signal,
                        LAG(macd) OVER (ORDER BY timestamp) as prev_macd,
                        LAG(signal) OVER (ORDER BY timestamp) as prev_signal
                    FROM macd_values
                )
                SELECT COUNT(*) as crossover_count
                FROM crossovers
                WHERE (prev_macd < prev_signal AND macd > signal)  -- Bullish crossover
                   OR (prev_macd > prev_signal AND macd < signal)  -- Bearish crossover
            """), {'start_date': start_date})
            
            crossovers = crossover_result.fetchone().crossover_count
            
            print(f"Period: Past 7 days (15-minute intervals)")
            print(f"Expected Candles: {expected_candles}")
            print(f"MACD Data Points: {macd_data.get('macd', {}).get('count', 0)}")
            print(f"Signal Data Points: {macd_data.get('macd_signal', {}).get('count', 0)}")
            print(f"Histogram Data Points: {macd_data.get('macd_histogram', {}).get('count', 0)}")
            print(f"Crossovers Detected: {crossovers}")
            
            has_all_components = all(k in macd_data for k in ['macd', 'macd_signal', 'macd_histogram'])
            
            return {
                'passed': has_all_components and all(v['count'] > 0 for v in macd_data.values()),
                'metrics': {
                    'expected_candles': expected_candles,
                    'macd_points': macd_data.get('macd', {}).get('count', 0),
                    'signal_points': macd_data.get('macd_signal', {}).get('count', 0),
                    'histogram_points': macd_data.get('macd_histogram', {}).get('count', 0),
                    'crossovers': crossovers
                },
                'details': f"SOL MACD analysis for past week"
            }
    
    def test_4_dogecoin_atr(self) -> Dict:
        """Test 4: Dogecoin ATR for past month on 4-hour candles"""
        with self.engine.connect() as conn:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            # Get ATR data
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as atr_count,
                    MIN(value) as min_atr,
                    MAX(value) as max_atr,
                    AVG(value) as avg_atr,
                    STDDEV(value) as std_atr
                FROM indicator_values
                WHERE symbol = 'DOGEUSDT'
                AND indicator_name = 'atr'
                AND timeframe = '4h'
                AND timestamp >= :start_date
            """), {'start_date': start_date})
            
            row = result.fetchone()
            expected_candles = 30 * 6  # 30 days * 6 candles per day
            
            # Check for volatility correlation
            volatility_result = conn.execute(text("""
                SELECT 
                    DATE(timestamp) as date,
                    MAX(value) as daily_max_atr,
                    AVG(value) as daily_avg_atr
                FROM indicator_values
                WHERE symbol = 'DOGEUSDT'
                AND indicator_name = 'atr'
                AND timeframe = '4h'
                AND timestamp >= :start_date
                GROUP BY DATE(timestamp)
                ORDER BY daily_max_atr DESC
                LIMIT 5
            """), {'start_date': start_date})
            
            high_volatility_days = [
                {'date': r.date, 'max_atr': r.daily_max_atr, 'avg_atr': r.daily_avg_atr}
                for r in volatility_result
            ]
            
            print(f"Period: Past 30 days (4-hour intervals)")
            print(f"Expected Candles: {expected_candles}")
            print(f"ATR Data Points: {row.atr_count}")
            print(f"ATR Range: {row.min_atr:.6f} - {row.max_atr:.6f}")
            print(f"Average ATR: {row.avg_atr:.6f}")
            print(f"\nTop 5 High Volatility Days:")
            for day in high_volatility_days:
                print(f"  {day['date']}: Max ATR = {day['max_atr']:.6f}")
            
            # ATR should always be positive
            atr_valid = row.min_atr > 0 if row.atr_count > 0 else False
            
            return {
                'passed': row.atr_count > 0 and atr_valid,
                'metrics': {
                    'expected_candles': expected_candles,
                    'atr_data_points': row.atr_count,
                    'min_atr': f"{row.min_atr:.6f}" if row.min_atr else 'N/A',
                    'max_atr': f"{row.max_atr:.6f}" if row.max_atr else 'N/A',
                    'avg_atr': f"{row.avg_atr:.6f}" if row.avg_atr else 'N/A',
                    'atr_positive': atr_valid
                },
                'details': f"DOGE ATR volatility analysis for past month"
            }
    
    def test_5_bnb_ema_crossovers(self) -> Dict:
        """Test 5: BNB EMA crossovers for past 2 weeks on hourly data"""
        with self.engine.connect() as conn:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=14)
            
            # Get EMA data
            result = conn.execute(text("""
                SELECT 
                    indicator_name,
                    COUNT(*) as count
                FROM indicator_values
                WHERE symbol = 'BNBUSDT'
                AND indicator_name IN ('ema_12', 'ema_50', 'ema_200')
                AND timeframe = '1h'
                AND timestamp >= :start_date
                GROUP BY indicator_name
            """), {'start_date': start_date})
            
            ema_counts = {row.indicator_name: row.count for row in result}
            expected_candles = 14 * 24  # 14 days * 24 hours
            
            # Detect crossovers
            crossover_result = conn.execute(text("""
                WITH ema_values AS (
                    SELECT 
                        timestamp,
                        MAX(CASE WHEN indicator_name = 'ema_12' THEN value END) as ema12,
                        MAX(CASE WHEN indicator_name = 'ema_50' THEN value END) as ema50,
                        MAX(CASE WHEN indicator_name = 'ema_200' THEN value END) as ema200
                    FROM indicator_values
                    WHERE symbol = 'BNBUSDT'
                    AND indicator_name IN ('ema_12', 'ema_50', 'ema_200')
                    AND timeframe = '1h'
                    AND timestamp >= :start_date
                    GROUP BY timestamp
                ),
                crossovers AS (
                    SELECT 
                        timestamp,
                        ema12, ema50, ema200,
                        LAG(ema12) OVER (ORDER BY timestamp) as prev_ema12,
                        LAG(ema50) OVER (ORDER BY timestamp) as prev_ema50,
                        LAG(ema200) OVER (ORDER BY timestamp) as prev_ema200
                    FROM ema_values
                    WHERE ema12 IS NOT NULL AND ema50 IS NOT NULL
                )
                SELECT 
                    COUNT(CASE WHEN prev_ema12 < prev_ema50 AND ema12 > ema50 THEN 1 END) as golden_cross_12_50,
                    COUNT(CASE WHEN prev_ema12 > prev_ema50 AND ema12 < ema50 THEN 1 END) as death_cross_12_50,
                    COUNT(CASE WHEN prev_ema50 < prev_ema200 AND ema50 > ema200 
                               AND ema200 IS NOT NULL AND prev_ema200 IS NOT NULL THEN 1 END) as golden_cross_50_200,
                    COUNT(CASE WHEN prev_ema50 > prev_ema200 AND ema50 < ema200 
                               AND ema200 IS NOT NULL AND prev_ema200 IS NOT NULL THEN 1 END) as death_cross_50_200
                FROM crossovers
            """), {'start_date': start_date})
            
            crosses = crossover_result.fetchone()
            
            print(f"Period: Past 14 days (hourly)")
            print(f"Expected Candles: {expected_candles}")
            print(f"EMA-12 Points: {ema_counts.get('ema_12', 0)}")
            print(f"EMA-50 Points: {ema_counts.get('ema_50', 0)}")
            print(f"EMA-200 Points: {ema_counts.get('ema_200', 0)}")
            print(f"\nCrossovers Detected:")
            print(f"  Golden Cross (12/50): {crosses.golden_cross_12_50}")
            print(f"  Death Cross (12/50): {crosses.death_cross_12_50}")
            print(f"  Golden Cross (50/200): {crosses.golden_cross_50_200}")
            print(f"  Death Cross (50/200): {crosses.death_cross_50_200}")
            
            has_all_emas = all(k in ema_counts for k in ['ema_12', 'ema_50', 'ema_200'])
            
            return {
                'passed': has_all_emas and all(v > 0 for v in ema_counts.values()),
                'metrics': {
                    'expected_candles': expected_candles,
                    'ema12_points': ema_counts.get('ema_12', 0),
                    'ema50_points': ema_counts.get('ema_50', 0),
                    'ema200_points': ema_counts.get('ema_200', 0),
                    'golden_cross_12_50': crosses.golden_cross_12_50,
                    'death_cross_12_50': crosses.death_cross_12_50,
                    'golden_cross_50_200': crosses.golden_cross_50_200,
                    'death_cross_50_200': crosses.death_cross_50_200
                },
                'details': f"BNB EMA crossover analysis for past 2 weeks"
            }
    
    def test_6_xrp_volume_analysis(self) -> Dict:
        """Test 6: XRP volume analysis for past 6 months on daily candles"""
        with self.engine.connect() as conn:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            
            # Get volume data
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as candle_count,
                    SUM(volume) as total_volume,
                    AVG(volume) as avg_volume,
                    MAX(volume) as max_volume,
                    MIN(volume) as min_volume,
                    STDDEV(volume) as std_volume
                FROM kline_data
                WHERE symbol = 'XRPUSDT'
                AND interval = '1d'
                AND open_time >= :start_date
            """), {'start_date': start_date})
            
            row = result.fetchone()
            expected_candles = 180
            
            # Find volume spikes (days with volume > 2 std dev above mean)
            spike_result = conn.execute(text("""
                WITH volume_stats AS (
                    SELECT 
                        AVG(volume) as mean_vol,
                        STDDEV(volume) as std_vol
                    FROM kline_data
                    WHERE symbol = 'XRPUSDT'
                    AND interval = '1d'
                    AND open_time >= :start_date
                )
                SELECT 
                    DATE(open_time) as date,
                    volume,
                    close_price - open_price as price_change,
                    ((close_price - open_price) / open_price * 100) as price_change_pct
                FROM kline_data, volume_stats
                WHERE symbol = 'XRPUSDT'
                AND interval = '1d'
                AND open_time >= :start_date
                AND volume > (mean_vol + 2 * std_vol)
                ORDER BY volume DESC
                LIMIT 5
            """), {'start_date': start_date})
            
            volume_spikes = [
                {
                    'date': r.date,
                    'volume': r.volume,
                    'price_change': r.price_change,
                    'price_change_pct': r.price_change_pct
                }
                for r in spike_result
            ]
            
            print(f"Period: Past 180 days (daily)")
            print(f"Expected Candles: {expected_candles}")
            print(f"Actual Candles: {row.candle_count}")
            print(f"Total Volume: {row.total_volume:,.0f}")
            print(f"Average Daily Volume: {row.avg_volume:,.0f}")
            print(f"Max Daily Volume: {row.max_volume:,.0f}")
            print(f"\nTop Volume Spike Days:")
            for spike in volume_spikes:
                print(f"  {spike['date']}: Volume = {spike['volume']:,.0f}, "
                      f"Price Change = {spike['price_change_pct']:.2f}%")
            
            completeness = (row.candle_count / expected_candles * 100) if expected_candles > 0 else 0
            
            return {
                'passed': row.candle_count > 0 and completeness >= 90,
                'metrics': {
                    'expected_candles': expected_candles,
                    'actual_candles': row.candle_count,
                    'completeness_pct': f"{completeness:.2f}%",
                    'total_volume': f"{row.total_volume:,.0f}",
                    'avg_daily_volume': f"{row.avg_volume:,.0f}",
                    'volume_spike_days': len(volume_spikes)
                },
                'details': f"XRP volume analysis for past 6 months"
            }
    
    def test_7_avax_yearly_highs_lows(self) -> Dict:
        """Test 7: AVAX yearly highs and lows with weekly aggregation"""
        with self.engine.connect() as conn:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            
            # Get daily data and aggregate to weekly
            result = conn.execute(text("""
                WITH weekly_data AS (
                    SELECT 
                        DATE_TRUNC('week', open_time) as week,
                        MAX(high_price) as weekly_high,
                        MIN(low_price) as weekly_low,
                        AVG(close_price) as weekly_avg,
                        SUM(volume) as weekly_volume
                    FROM kline_data
                    WHERE symbol = 'AVAXUSDT'
                    AND interval = '1d'
                    AND open_time >= :start_date
                    GROUP BY DATE_TRUNC('week', open_time)
                )
                SELECT 
                    COUNT(*) as week_count,
                    MAX(weekly_high) as year_high,
                    MIN(weekly_low) as year_low,
                    AVG(weekly_avg) as year_avg,
                    MAX(weekly_high) - MIN(weekly_low) as year_range
                FROM weekly_data
            """), {'start_date': start_date})
            
            row = result.fetchone()
            expected_weeks = 52
            
            # Find 52-week high and low dates
            extremes_result = conn.execute(text("""
                SELECT 
                    MAX(CASE WHEN high_price = (
                        SELECT MAX(high_price) FROM kline_data 
                        WHERE symbol = 'AVAXUSDT' AND interval = '1d' 
                        AND open_time >= :start_date
                    ) THEN DATE(open_time) END) as high_date,
                    MAX(CASE WHEN low_price = (
                        SELECT MIN(low_price) FROM kline_data 
                        WHERE symbol = 'AVAXUSDT' AND interval = '1d' 
                        AND open_time >= :start_date
                    ) THEN DATE(open_time) END) as low_date,
                    MAX(high_price) as year_high,
                    MIN(low_price) as year_low
                FROM kline_data
                WHERE symbol = 'AVAXUSDT'
                AND interval = '1d'
                AND open_time >= :start_date
            """), {'start_date': start_date})
            
            extremes = extremes_result.fetchone()
            
            print(f"Period: Past 365 days (weekly aggregation)")
            print(f"Expected Weeks: {expected_weeks}")
            print(f"Actual Weeks: {row.week_count}")
            print(f"\n52-Week Statistics:")
            print(f"  High: ${extremes.year_high:.2f} on {extremes.high_date}")
            print(f"  Low: ${extremes.year_low:.2f} on {extremes.low_date}")
            print(f"  Range: ${row.year_range:.2f}")
            print(f"  Average: ${row.year_avg:.2f}")
            
            completeness = (row.week_count / expected_weeks * 100) if expected_weeks > 0 else 0
            
            return {
                'passed': row.week_count > 0 and completeness >= 80,
                'metrics': {
                    'expected_weeks': expected_weeks,
                    'actual_weeks': row.week_count,
                    'completeness_pct': f"{completeness:.2f}%",
                    '52_week_high': f"${extremes.year_high:.2f}",
                    '52_week_low': f"${extremes.year_low:.2f}",
                    'year_range': f"${row.year_range:.2f}",
                    'year_average': f"${row.year_avg:.2f}"
                },
                'details': f"AVAX 52-week high/low analysis"
            }
    
    def test_8_link_intraday_data(self) -> Dict:
        """Test 8: LINK complete intraday data for yesterday across all intervals"""
        with self.engine.connect() as conn:
            # Get yesterday's date
            yesterday = (datetime.now() - timedelta(days=1)).date()
            start_time = datetime.combine(yesterday, datetime.min.time())
            end_time = datetime.combine(yesterday, datetime.max.time())
            
            intervals = ['5m', '15m', '30m', '1h']
            expected_counts = {
                '5m': 288,   # 24 hours * 12 per hour
                '15m': 96,   # 24 hours * 4 per hour
                '30m': 48,   # 24 hours * 2 per hour
                '1h': 24     # 24 hours
            }
            
            results = {}
            for interval in intervals:
                result = conn.execute(text("""
                    SELECT 
                        COUNT(*) as count,
                        MIN(open_price) as min_price,
                        MAX(high_price) as max_price,
                        AVG(volume) as avg_volume
                    FROM kline_data
                    WHERE symbol = 'LINKUSDT'
                    AND interval = :interval
                    AND open_time >= :start_time
                    AND open_time < :end_time
                """), {'interval': interval, 'start_time': start_time, 'end_time': end_time})
                
                row = result.fetchone()
                results[interval] = {
                    'count': row.count,
                    'expected': expected_counts[interval],
                    'completeness': (row.count / expected_counts[interval] * 100) if expected_counts[interval] > 0 else 0,
                    'min_price': row.min_price,
                    'max_price': row.max_price,
                    'avg_volume': row.avg_volume
                }
            
            # Check consistency across timeframes
            consistency_result = conn.execute(text("""
                WITH price_ranges AS (
                    SELECT 
                        interval,
                        MIN(low_price) as day_low,
                        MAX(high_price) as day_high
                    FROM kline_data
                    WHERE symbol = 'LINKUSDT'
                    AND interval IN ('5m', '15m', '30m', '1h')
                    AND open_time >= :start_time
                    AND open_time < :end_time
                    GROUP BY interval
                )
                SELECT 
                    COUNT(DISTINCT day_low) = 1 as low_consistent,
                    COUNT(DISTINCT day_high) = 1 as high_consistent
                FROM price_ranges
            """), {'start_time': start_time, 'end_time': end_time})
            
            consistency = consistency_result.fetchone()
            
            print(f"Date: {yesterday}")
            print(f"\nData Completeness by Interval:")
            total_actual = 0
            total_expected = 0
            for interval, data in results.items():
                total_actual += data['count']
                total_expected += data['expected']
                print(f"  {interval:3}: {data['count']:3}/{data['expected']:3} candles "
                      f"({data['completeness']:.1f}%) - "
                      f"Range: ${data['min_price']:.2f}-${data['max_price']:.2f}")
            
            print(f"\nTotal Candles: {total_actual}/{total_expected}")
            print(f"Cross-timeframe Consistency:")
            print(f"  Daily Low Consistent: {'✅' if consistency.low_consistent else '❌'}")
            print(f"  Daily High Consistent: {'✅' if consistency.high_consistent else '❌'}")
            
            all_complete = all(r['completeness'] >= 90 for r in results.values())
            
            return {
                'passed': all_complete and consistency.low_consistent and consistency.high_consistent,
                'metrics': {
                    'date': str(yesterday),
                    'total_candles': total_actual,
                    'expected_total': total_expected,
                    '5m_completeness': f"{results['5m']['completeness']:.1f}%",
                    '15m_completeness': f"{results['15m']['completeness']:.1f}%",
                    '30m_completeness': f"{results['30m']['completeness']:.1f}%",
                    '1h_completeness': f"{results['1h']['completeness']:.1f}%",
                    'consistency_check': consistency.low_consistent and consistency.high_consistent
                },
                'details': f"LINK intraday data consistency check for {yesterday}"
            }
    
    def test_9_multi_symbol_rsi_comparison(self) -> Dict:
        """Test 9: Multi-symbol RSI comparison for past 24 hours on 5-minute data"""
        with self.engine.connect() as conn:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)
            symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
            
            results = {}
            for symbol in symbols:
                result = conn.execute(text("""
                    SELECT 
                        COUNT(*) as rsi_count,
                        AVG(value) as avg_rsi,
                        MIN(value) as min_rsi,
                        MAX(value) as max_rsi,
                        STDDEV(value) as std_rsi
                    FROM indicator_values
                    WHERE symbol = :symbol
                    AND indicator_name = 'rsi'
                    AND timeframe = '5m'
                    AND timestamp >= :start_time
                """), {'symbol': symbol, 'start_time': start_time})
                
                row = result.fetchone()
                results[symbol] = {
                    'count': row.rsi_count,
                    'avg': row.avg_rsi,
                    'min': row.min_rsi,
                    'max': row.max_rsi,
                    'std': row.std_rsi
                }
            
            # Calculate RSI correlation
            correlation_result = conn.execute(text("""
                WITH rsi_data AS (
                    SELECT 
                        timestamp,
                        MAX(CASE WHEN symbol = 'BTCUSDT' THEN value END) as btc_rsi,
                        MAX(CASE WHEN symbol = 'ETHUSDT' THEN value END) as eth_rsi,
                        MAX(CASE WHEN symbol = 'SOLUSDT' THEN value END) as sol_rsi
                    FROM indicator_values
                    WHERE symbol IN ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
                    AND indicator_name = 'rsi'
                    AND timeframe = '5m'
                    AND timestamp >= :start_time
                    GROUP BY timestamp
                )
                SELECT 
                    CORR(btc_rsi, eth_rsi) as btc_eth_corr,
                    CORR(btc_rsi, sol_rsi) as btc_sol_corr,
                    CORR(eth_rsi, sol_rsi) as eth_sol_corr
                FROM rsi_data
                WHERE btc_rsi IS NOT NULL 
                AND eth_rsi IS NOT NULL 
                AND sol_rsi IS NOT NULL
            """), {'start_time': start_time})
            
            correlations = correlation_result.fetchone()
            expected_candles = 288  # 24 hours * 12 per hour
            
            print(f"Period: Past 24 hours (5-minute intervals)")
            print(f"Expected Candles per Symbol: {expected_candles}")
            print(f"\nRSI Statistics by Symbol:")
            for symbol, data in results.items():
                print(f"  {symbol}:")
                print(f"    Count: {data['count']}")
                print(f"    Average: {data['avg']:.2f}" if data['avg'] else "    Average: N/A")
                print(f"    Range: {data['min']:.2f} - {data['max']:.2f}" if data['min'] else "    Range: N/A")
            
            print(f"\nRSI Correlations:")
            print(f"  BTC-ETH: {correlations.btc_eth_corr:.3f}" if correlations.btc_eth_corr else "  BTC-ETH: N/A")
            print(f"  BTC-SOL: {correlations.btc_sol_corr:.3f}" if correlations.btc_sol_corr else "  BTC-SOL: N/A")
            print(f"  ETH-SOL: {correlations.eth_sol_corr:.3f}" if correlations.eth_sol_corr else "  ETH-SOL: N/A")
            
            all_have_data = all(r['count'] > 0 for r in results.values())
            
            return {
                'passed': all_have_data,
                'metrics': {
                    'expected_candles': expected_candles,
                    'btc_rsi_points': results['BTCUSDT']['count'],
                    'eth_rsi_points': results['ETHUSDT']['count'],
                    'sol_rsi_points': results['SOLUSDT']['count'],
                    'btc_eth_correlation': f"{correlations.btc_eth_corr:.3f}" if correlations.btc_eth_corr else 'N/A',
                    'btc_sol_correlation': f"{correlations.btc_sol_corr:.3f}" if correlations.btc_sol_corr else 'N/A',
                    'eth_sol_correlation': f"{correlations.eth_sol_corr:.3f}" if correlations.eth_sol_corr else 'N/A'
                },
                'details': f"Multi-symbol RSI correlation analysis for past 24 hours"
            }
    
    def test_10_data_completeness_audit(self) -> Dict:
        """Test 10: Data completeness audit for BTCUSDT past 30 days hourly"""
        with self.engine.connect() as conn:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            # Check for gaps
            gaps_result = conn.execute(text("""
                WITH hourly_series AS (
                    SELECT 
                        open_time,
                        close_time,
                        LAG(close_time) OVER (ORDER BY open_time) as prev_close,
                        open_price,
                        high_price,
                        low_price,
                        close_price,
                        volume
                    FROM kline_data
                    WHERE symbol = 'BTCUSDT'
                    AND interval = '1h'
                    AND open_time >= :start_date
                    ORDER BY open_time
                )
                SELECT 
                    COUNT(*) as total_candles,
                    COUNT(CASE WHEN open_time - prev_close > INTERVAL '1 hour' THEN 1 END) as gaps,
                    COUNT(CASE WHEN high_price < low_price THEN 1 END) as invalid_ohlc,
                    COUNT(CASE WHEN volume < 0 THEN 1 END) as negative_volume,
                    COUNT(CASE WHEN volume = 0 THEN 1 END) as zero_volume,
                    MIN(open_time) as first_candle,
                    MAX(close_time) as last_candle
                FROM hourly_series
            """), {'start_date': start_date})
            
            audit = gaps_result.fetchone()
            expected_candles = 30 * 24  # 30 days * 24 hours
            
            # Check for duplicates
            dup_result = conn.execute(text("""
                SELECT COUNT(*) as duplicate_count
                FROM (
                    SELECT open_time, COUNT(*) as cnt
                    FROM kline_data
                    WHERE symbol = 'BTCUSDT'
                    AND interval = '1h'
                    AND open_time >= :start_date
                    GROUP BY open_time
                    HAVING COUNT(*) > 1
                ) duplicates
            """), {'start_date': start_date})
            
            duplicates = dup_result.fetchone().duplicate_count
            
            # Check price continuity
            continuity_result = conn.execute(text("""
                WITH price_changes AS (
                    SELECT 
                        open_time,
                        close_price,
                        LEAD(open_price) OVER (ORDER BY open_time) as next_open,
                        ABS(close_price - LEAD(open_price) OVER (ORDER BY open_time)) / close_price * 100 as gap_pct
                    FROM kline_data
                    WHERE symbol = 'BTCUSDT'
                    AND interval = '1h'
                    AND open_time >= :start_date
                )
                SELECT 
                    COUNT(CASE WHEN gap_pct > 1 THEN 1 END) as large_gaps,
                    MAX(gap_pct) as max_gap_pct
                FROM price_changes
                WHERE next_open IS NOT NULL
            """), {'start_date': start_date})
            
            continuity = continuity_result.fetchone()
            
            completeness = (audit.total_candles / expected_candles * 100) if expected_candles > 0 else 0
            
            print(f"Period: Past 30 days (hourly)")
            print(f"Expected Candles: {expected_candles}")
            print(f"Actual Candles: {audit.total_candles}")
            print(f"Completeness: {completeness:.2f}%")
            print(f"\nData Quality Audit:")
            print(f"  Time Gaps: {audit.gaps}")
            print(f"  Duplicates: {duplicates}")
            print(f"  Invalid OHLC: {audit.invalid_ohlc}")
            print(f"  Negative Volume: {audit.negative_volume}")
            print(f"  Zero Volume: {audit.zero_volume}")
            print(f"  Large Price Gaps (>1%): {continuity.large_gaps}")
            print(f"  Max Price Gap: {continuity.max_gap_pct:.2f}%" if continuity.max_gap_pct else "  Max Price Gap: N/A")
            print(f"\nData Range:")
            print(f"  First: {audit.first_candle}")
            print(f"  Last: {audit.last_candle}")
            
            # Pass if completeness >= 95% and no major issues
            issues = audit.gaps + duplicates + audit.invalid_ohlc + audit.negative_volume
            
            return {
                'passed': completeness >= 95 and issues == 0,
                'metrics': {
                    'expected_candles': expected_candles,
                    'actual_candles': audit.total_candles,
                    'completeness_pct': f"{completeness:.2f}%",
                    'time_gaps': audit.gaps,
                    'duplicates': duplicates,
                    'invalid_ohlc': audit.invalid_ohlc,
                    'zero_volume_candles': audit.zero_volume,
                    'large_price_gaps': continuity.large_gaps,
                    'data_quality_issues': issues
                },
                'details': f"BTCUSDT data completeness and quality audit for past 30 days"
            }
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("\n" + "="*80)
        print("COMPREHENSIVE DATA VALIDATION TEST SUITE")
        print("="*80)
        print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run each test
        self.run_test("Bitcoin 5-minute data validation", self.test_1_bitcoin_5min_data)
        self.run_test("Ethereum RSI validation (3 months)", self.test_2_ethereum_rsi)
        self.run_test("Solana MACD analysis (1 week)", self.test_3_solana_macd)
        self.run_test("Dogecoin ATR volatility (1 month)", self.test_4_dogecoin_atr)
        self.run_test("BNB EMA crossovers (2 weeks)", self.test_5_bnb_ema_crossovers)
        self.run_test("XRP volume analysis (6 months)", self.test_6_xrp_volume_analysis)
        self.run_test("AVAX yearly highs/lows", self.test_7_avax_yearly_highs_lows)
        self.run_test("LINK intraday data consistency", self.test_8_link_intraday_data)
        self.run_test("Multi-symbol RSI comparison (24h)", self.test_9_multi_symbol_rsi_comparison)
        self.run_test("BTCUSDT completeness audit (30 days)", self.test_10_data_completeness_audit)
        
        # Print summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"Total Tests: {self.test_count}")
        print(f"Passed: {self.passed_count}")
        print(f"Failed: {self.test_count - self.passed_count}")
        print(f"Success Rate: {(self.passed_count/self.test_count*100):.1f}%")
        
        print("\nDetailed Results:")
        print("-"*80)
        
        # Create summary table
        summary_data = []
        for i, result in enumerate(self.results, 1):
            summary_data.append([
                i,
                result['test_name'][:40] + '...' if len(result['test_name']) > 40 else result['test_name'],
                result['status'],
                result.get('details', '')[:30] + '...' if result.get('details', '') and len(result.get('details', '')) > 30 else result.get('details', '')
            ])
        
        print(tabulate(summary_data, headers=['#', 'Test Name', 'Status', 'Details'], tablefmt='grid'))
        
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return {
            'total_tests': self.test_count,
            'passed': self.passed_count,
            'failed': self.test_count - self.passed_count,
            'success_rate': (self.passed_count/self.test_count*100),
            'results': self.results
        }


def main():
    """Main execution function"""
    validator = DataValidationTests()
    results = validator.run_all_tests()
    
    # Return exit code based on results
    if results['success_rate'] == 100:
        print("\n✅ All tests passed successfully!")
        sys.exit(0)
    else:
        print(f"\n⚠️ {results['failed']} test(s) failed. Please review the results.")
        sys.exit(1)


if __name__ == "__main__":
    main()