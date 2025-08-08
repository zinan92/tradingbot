"""
Bulk Data Loader for downloading large amounts of historical market data from Binance Futures

This module handles:
- Fetching top symbols by volume
- Batch downloading with rate limiting
- Progress tracking and error recovery
- Efficient data storage
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
import time
import json
from collections import defaultdict
import aiohttp
from tqdm.asyncio import tqdm

from .binance_client import BinanceFuturesClient
from .data_normalizer import BinanceDataNormalizer
from ..persistence.postgres.market_data_repository import MarketDataRepository
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class BulkDataLoader:
    """
    Handles bulk downloading of historical market data with rate limiting and progress tracking
    """
    
    def __init__(self, 
                 db_session: Session,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None):
        self.db_session = db_session
        self.repository = MarketDataRepository(db_session)
        self.client = BinanceFuturesClient(api_key, api_secret)
        self.normalizer = BinanceDataNormalizer()
        
        # Rate limiting configuration
        self.max_requests_per_minute = 1200  # Binance limit
        self.request_weight = 1  # Weight per klines request
        self.request_counter = 0
        self.request_timestamps = []
        
        # Progress tracking
        self.download_progress = {}
        self.failed_downloads = []
        self.total_candles_downloaded = 0
        
        # Configuration
        self.batch_size = 1000  # Max klines per request
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        self.parallel_workers = 4  # Number of concurrent downloads
        
    async def start(self):
        """Initialize the Binance client"""
        await self.client.start()
        logger.info("Bulk data loader initialized")
    
    async def stop(self):
        """Clean up resources"""
        await self.client.stop()
        logger.info(f"Bulk data loader stopped. Total candles downloaded: {self.total_candles_downloaded}")
    
    async def get_top_futures_symbols(self, top_n: int = 30) -> List[str]:
        """
        Get the top N futures symbols by 24hr volume
        
        Args:
            top_n: Number of top symbols to return
            
        Returns:
            List of symbol names sorted by volume
        """
        try:
            logger.info(f"Fetching top {top_n} futures symbols by volume...")
            
            # Get 24hr ticker data for all symbols
            tickers = await self.client.get_ticker_24hr()
            
            # Filter for USDT perpetual futures and sort by quote volume
            usdt_futures = [
                ticker for ticker in tickers 
                if ticker['symbol'].endswith('USDT') and 
                not any(ticker['symbol'].endswith(suffix) for suffix in ['_PERP', '_QUARTER', '_BIQUARTER'])
            ]
            
            # Sort by 24hr quote volume (USD value traded)
            sorted_tickers = sorted(
                usdt_futures, 
                key=lambda x: float(x.get('quoteVolume', 0)), 
                reverse=True
            )
            
            # Get top N symbols
            top_symbols = [ticker['symbol'] for ticker in sorted_tickers[:top_n]]
            
            logger.info(f"Top {top_n} symbols by volume: {top_symbols}")
            
            # Log volume information
            for i, ticker in enumerate(sorted_tickers[:top_n]):
                volume_millions = float(ticker['quoteVolume']) / 1_000_000
                logger.info(f"  {i+1}. {ticker['symbol']}: ${volume_millions:.2f}M volume")
            
            return top_symbols
            
        except Exception as e:
            logger.error(f"Error fetching top symbols: {e}")
            raise
    
    async def _rate_limit(self):
        """Implement rate limiting to avoid exceeding API limits"""
        current_time = time.time()
        
        # Remove timestamps older than 1 minute
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts < 60
        ]
        
        # If we've made too many requests, wait
        if len(self.request_timestamps) >= self.max_requests_per_minute:
            wait_time = 60 - (current_time - self.request_timestamps[0])
            if wait_time > 0:
                logger.debug(f"Rate limit: waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
        
        # Record this request
        self.request_timestamps.append(current_time)
        self.request_counter += 1
    
    async def download_historical_data(self,
                                      symbols: List[str],
                                      intervals: List[str],
                                      start_date: datetime,
                                      end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Download historical kline data for multiple symbols and intervals
        
        Args:
            symbols: List of trading symbols
            intervals: List of time intervals (e.g., ['5m', '15m', '1h'])
            start_date: Start date for historical data
            end_date: End date (default: now)
            
        Returns:
            Dictionary with download statistics
        """
        if end_date is None:
            end_date = datetime.now()
        
        total_combinations = len(symbols) * len(intervals)
        logger.info(f"Starting download for {len(symbols)} symbols × {len(intervals)} intervals")
        logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
        logger.info(f"Total download tasks: {total_combinations}")
        
        # Calculate estimated data points
        days = (end_date - start_date).days
        estimated_candles = self._estimate_candles(symbols, intervals, days)
        logger.info(f"Estimated total candles: {estimated_candles:,}")
        
        # Create download tasks
        download_tasks = []
        for symbol in symbols:
            for interval in intervals:
                task_info = {
                    'symbol': symbol,
                    'interval': interval,
                    'start_date': start_date,
                    'end_date': end_date
                }
                download_tasks.append(task_info)
        
        # Initialize progress tracking
        self.download_progress = {
            f"{task['symbol']}_{task['interval']}": {
                'status': 'pending',
                'candles_downloaded': 0,
                'progress_pct': 0
            }
            for task in download_tasks
        }
        
        # Process downloads with worker pool
        semaphore = asyncio.Semaphore(self.parallel_workers)
        
        async def download_with_semaphore(task):
            async with semaphore:
                return await self._download_symbol_interval(
                    task['symbol'],
                    task['interval'],
                    task['start_date'],
                    task['end_date']
                )
        
        # Execute downloads with progress bar
        results = []
        with tqdm(total=total_combinations, desc="Downloading") as pbar:
            tasks = [download_with_semaphore(task) for task in download_tasks]
            
            for future in asyncio.as_completed(tasks):
                result = await future
                results.append(result)
                pbar.update(1)
                
                # Update progress
                if result['success']:
                    pbar.set_description(
                        f"Downloaded {result['symbol']} {result['interval']} "
                        f"({result['candles_count']} candles)"
                    )
        
        # Compile statistics
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        stats = {
            'total_tasks': total_combinations,
            'successful': len(successful),
            'failed': len(failed),
            'total_candles': sum(r['candles_count'] for r in successful),
            'failed_tasks': [
                f"{r['symbol']}_{r['interval']}: {r.get('error', 'Unknown error')}"
                for r in failed
            ],
            'download_time': sum(r.get('download_time', 0) for r in results),
            'details': results
        }
        
        logger.info(f"Download complete: {stats['successful']}/{stats['total_tasks']} successful")
        logger.info(f"Total candles downloaded: {stats['total_candles']:,}")
        
        if stats['failed'] > 0:
            logger.warning(f"Failed downloads: {stats['failed_tasks']}")
        
        return stats
    
    async def _download_symbol_interval(self,
                                       symbol: str,
                                       interval: str,
                                       start_date: datetime,
                                       end_date: datetime) -> Dict[str, Any]:
        """
        Download historical data for a single symbol/interval combination
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_date: Start date
            end_date: End date
            
        Returns:
            Download result dictionary
        """
        task_id = f"{symbol}_{interval}"
        start_time = time.time()
        
        try:
            # Update progress
            self.download_progress[task_id]['status'] = 'downloading'
            
            # Check existing data range
            existing_range = await self._get_existing_data_range(symbol, interval)
            
            # Determine what data we need to download
            download_ranges = self._calculate_download_ranges(
                start_date, end_date, existing_range
            )
            
            if not download_ranges:
                logger.info(f"{task_id}: Data already exists for entire range")
                return {
                    'success': True,
                    'symbol': symbol,
                    'interval': interval,
                    'candles_count': 0,
                    'message': 'Data already exists',
                    'download_time': 0
                }
            
            total_candles = 0
            
            for range_start, range_end in download_ranges:
                candles = await self._download_range_with_retry(
                    symbol, interval, range_start, range_end
                )
                
                if candles:
                    # Save to database in batches
                    await self._save_klines_batch(candles, symbol, interval)
                    total_candles += len(candles)
                    
                    # Update progress
                    self.download_progress[task_id]['candles_downloaded'] = total_candles
            
            # Update global counter
            self.total_candles_downloaded += total_candles
            
            # Update progress
            self.download_progress[task_id]['status'] = 'complete'
            self.download_progress[task_id]['progress_pct'] = 100
            
            download_time = time.time() - start_time
            
            logger.debug(f"{task_id}: Downloaded {total_candles} candles in {download_time:.2f}s")
            
            return {
                'success': True,
                'symbol': symbol,
                'interval': interval,
                'candles_count': total_candles,
                'download_time': download_time
            }
            
        except Exception as e:
            logger.error(f"Error downloading {task_id}: {e}")
            self.download_progress[task_id]['status'] = 'failed'
            self.failed_downloads.append(task_id)
            
            return {
                'success': False,
                'symbol': symbol,
                'interval': interval,
                'candles_count': 0,
                'error': str(e),
                'download_time': time.time() - start_time
            }
    
    async def _download_range_with_retry(self,
                                        symbol: str,
                                        interval: str,
                                        start_date: datetime,
                                        end_date: datetime) -> List[Dict]:
        """
        Download klines for a date range with retry logic
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_date: Start date
            end_date: End date
            
        Returns:
            List of normalized kline data
        """
        all_klines = []
        current_start = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        
        while current_start < end_timestamp:
            for attempt in range(self.max_retries):
                try:
                    # Apply rate limiting
                    await self._rate_limit()
                    
                    # Download batch
                    klines = await self.client.get_historical_klines(
                        symbol=symbol,
                        interval=interval,
                        start_time=current_start,
                        end_time=end_timestamp,
                        limit=self.batch_size
                    )
                    
                    if not klines:
                        break
                    
                    # Normalize the data
                    normalized_klines = [
                        self.normalizer.normalize_historical_kline(k, symbol, interval)
                        for k in klines
                    ]
                    
                    all_klines.extend(normalized_klines)
                    
                    # Move to next batch
                    current_start = klines[-1][0] + 1
                    break
                    
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Retry {attempt + 1}/{self.max_retries} for {symbol} {interval}: {e}")
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise
            
            # Break if no more data
            if not klines:
                break
        
        return all_klines
    
    async def _get_existing_data_range(self, 
                                      symbol: str, 
                                      interval: str) -> Optional[Tuple[datetime, datetime]]:
        """
        Get the date range of existing data in the database
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            
        Returns:
            Tuple of (start_date, end_date) or None if no data exists
        """
        try:
            # Get earliest and latest kline
            earliest = self.repository.get_earliest_kline(symbol, interval)
            latest = self.repository.get_latest_kline(symbol, interval)
            
            if earliest and latest:
                return (earliest.open_time, latest.close_time)
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking existing data for {symbol} {interval}: {e}")
            return None
    
    def _calculate_download_ranges(self,
                                  start_date: datetime,
                                  end_date: datetime,
                                  existing_range: Optional[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
        """
        Calculate what date ranges need to be downloaded
        
        Args:
            start_date: Requested start date
            end_date: Requested end date
            existing_range: Existing data range in database
            
        Returns:
            List of (start, end) tuples for ranges that need downloading
        """
        if not existing_range:
            # No existing data, download entire range
            return [(start_date, end_date)]
        
        existing_start, existing_end = existing_range
        ranges = []
        
        # Check if we need data before existing range
        if start_date < existing_start:
            ranges.append((start_date, existing_start))
        
        # Check if we need data after existing range
        if end_date > existing_end:
            ranges.append((existing_end, end_date))
        
        return ranges
    
    async def _save_klines_batch(self, klines: List[Dict], symbol: str, interval: str):
        """
        Save klines to database in batches
        
        Args:
            klines: List of normalized kline data
            symbol: Trading symbol
            interval: Time interval
        """
        try:
            # Save in batches to avoid memory issues
            batch_size = 1000
            
            for i in range(0, len(klines), batch_size):
                batch = klines[i:i + batch_size]
                
                for kline in batch:
                    # Check if kline already exists (by unique constraint)
                    existing = self.repository.get_kline_by_time(
                        symbol, interval, kline['open_time']
                    )
                    
                    if not existing:
                        self.repository.save_kline(kline)
                
                # Commit batch
                self.db_session.commit()
                
        except Exception as e:
            logger.error(f"Error saving klines batch: {e}")
            self.db_session.rollback()
            raise
    
    def _estimate_candles(self, symbols: List[str], intervals: List[str], days: int) -> int:
        """
        Estimate the total number of candles to download
        
        Args:
            symbols: List of symbols
            intervals: List of intervals
            days: Number of days
            
        Returns:
            Estimated number of candles
        """
        candles_per_day = {
            '1m': 1440,
            '3m': 480,
            '5m': 288,
            '15m': 96,
            '30m': 48,
            '1h': 24,
            '2h': 12,
            '4h': 6,
            '6h': 4,
            '8h': 3,
            '12h': 2,
            '1d': 1,
            '3d': 0.33,
            '1w': 0.14,
            '1M': 0.03
        }
        
        total = 0
        for interval in intervals:
            if interval in candles_per_day:
                total += candles_per_day[interval] * days * len(symbols)
        
        return int(total)
    
    def get_download_stats(self) -> Dict[str, Any]:
        """Get current download statistics"""
        return {
            'total_candles': self.total_candles_downloaded,
            'request_count': self.request_counter,
            'failed_downloads': self.failed_downloads,
            'progress': self.download_progress
        }
    
    async def validate_downloaded_data(self, 
                                      symbols: List[str], 
                                      intervals: List[str],
                                      start_date: datetime,
                                      end_date: datetime) -> Dict[str, Any]:
        """
        Validate the completeness of downloaded data
        
        Args:
            symbols: List of symbols to validate
            intervals: List of intervals to validate
            start_date: Expected start date
            end_date: Expected end date
            
        Returns:
            Validation report dictionary
        """
        validation_report = {
            'complete': [],
            'incomplete': [],
            'missing': [],
            'statistics': {}
        }
        
        for symbol in symbols:
            for interval in intervals:
                task_id = f"{symbol}_{interval}"
                
                # Check if data exists
                existing_range = await self._get_existing_data_range(symbol, interval)
                
                if not existing_range:
                    validation_report['missing'].append(task_id)
                    continue
                
                db_start, db_end = existing_range
                
                # Check if range is complete
                if db_start <= start_date and db_end >= end_date:
                    validation_report['complete'].append(task_id)
                    
                    # Count actual candles
                    candle_count = self.repository.count_klines(
                        symbol, interval, start_date, end_date
                    )
                    
                    expected_count = self._estimate_candles([symbol], [interval], (end_date - start_date).days)
                    completeness_pct = (candle_count / expected_count * 100) if expected_count > 0 else 0
                    
                    validation_report['statistics'][task_id] = {
                        'candle_count': candle_count,
                        'expected_count': expected_count,
                        'completeness_pct': completeness_pct,
                        'date_range': f"{db_start.date()} to {db_end.date()}"
                    }
                else:
                    validation_report['incomplete'].append(task_id)
                    validation_report['statistics'][task_id] = {
                        'actual_range': f"{db_start.date()} to {db_end.date()}",
                        'expected_range': f"{start_date.date()} to {end_date.date()}"
                    }
        
        # Summary statistics
        total_tasks = len(symbols) * len(intervals)
        validation_report['summary'] = {
            'total_tasks': total_tasks,
            'complete': len(validation_report['complete']),
            'incomplete': len(validation_report['incomplete']),
            'missing': len(validation_report['missing']),
            'completeness_pct': (len(validation_report['complete']) / total_tasks * 100) if total_tasks > 0 else 0
        }
        
        return validation_report