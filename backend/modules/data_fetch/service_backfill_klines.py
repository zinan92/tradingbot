"""
Service for historical data backfilling operations

This service handles:
- Historical data downloading
- Gap detection and filling
- Batch data loading
- Data integrity validation
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Protocol, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MarketDataRepositoryPort(Protocol):
    """Port for market data repository operations"""
    async def bulk_insert_klines(self, klines: List[Dict[str, Any]]) -> int:
        ...
    
    async def get_data_gaps(self, symbol: str, interval: str, start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]:
        ...
    
    async def get_latest_timestamp(self, symbol: str, interval: str) -> Optional[datetime]:
        ...
    
    async def validate_data_integrity(self, symbol: str, interval: str) -> Dict[str, Any]:
        ...


class ExchangePort(Protocol):
    """Port for exchange operations"""
    async def fetch_historical_klines(
        self, 
        symbol: str, 
        interval: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        ...
    
    async def validate_symbols(self, symbols: List[str]) -> List[str]:
        ...


class FetchPlannerPort(Protocol):
    """Port for fetch planning operations"""
    def create_fetch_plan(
        self, 
        symbols: List[str], 
        intervals: List[str], 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        ...


@dataclass
class BackfillConfig:
    """Configuration for data backfilling"""
    batch_size: int = 5
    max_retries: int = 3
    retry_delay: int = 5
    parallel_downloads: int = 3
    chunk_size: int = 1000
    enable_validation: bool = True
    enable_gap_detection: bool = True


class BackfillKlinesService:
    """
    Service for backfilling historical market data
    """
    
    def __init__(
        self,
        repository: MarketDataRepositoryPort,
        exchange: ExchangePort,
        fetch_planner: FetchPlannerPort,
        config: Optional[BackfillConfig] = None
    ):
        self.repository = repository
        self.exchange = exchange
        self.fetch_planner = fetch_planner
        self.config = config or BackfillConfig()
        
        # Progress tracking
        self.download_progress: Dict[str, float] = {}
        self.total_candles_downloaded = 0
        self.active_downloads: Dict[str, bool] = {}
        
    async def download_historical_data(
        self,
        symbols: List[str],
        intervals: List[str],
        start_date: datetime,
        end_date: Optional[datetime] = None,
        days_back: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Download historical data for specified symbols and intervals
        
        Args:
            symbols: List of trading symbols
            intervals: List of kline intervals
            start_date: Start date for historical data
            end_date: End date for historical data (defaults to now)
            days_back: Alternative to start_date, number of days back from now
        
        Returns:
            Statistics about the download operation
        """
        try:
            # Handle date parameters
            if days_back:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days_back)
            elif not end_date:
                end_date = datetime.now()
            
            # Validate symbols
            validated_symbols = await self.exchange.validate_symbols(symbols)
            if not validated_symbols:
                raise ValueError("No valid symbols to download")
            
            logger.info(
                f"Starting historical download for {len(validated_symbols)} symbols, "
                f"{len(intervals)} intervals, from {start_date} to {end_date}"
            )
            
            # Create fetch plan
            fetch_plan = self.fetch_planner.create_fetch_plan(
                symbols=validated_symbols,
                intervals=intervals,
                start_date=start_date,
                end_date=end_date
            )
            
            # Initialize statistics
            stats = {
                'total_candles': 0,
                'total_batches': len(fetch_plan),
                'successful_batches': 0,
                'failed_batches': 0,
                'symbols_processed': set(),
                'intervals_processed': set(),
                'start_time': datetime.now(),
                'errors': []
            }
            
            # Process fetch plan in parallel batches
            batch_size = self.config.parallel_downloads
            for i in range(0, len(fetch_plan), batch_size):
                batch = fetch_plan[i:i + batch_size]
                
                # Create tasks for parallel download
                tasks = [
                    self._download_batch(item)
                    for item in batch
                ]
                
                # Execute batch
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for item, result in zip(batch, results):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to download {item['symbol']} {item['interval']}: {result}")
                        stats['failed_batches'] += 1
                        stats['errors'].append(str(result))
                    else:
                        stats['successful_batches'] += 1
                        stats['total_candles'] += result['candles_count']
                        stats['symbols_processed'].add(item['symbol'])
                        stats['intervals_processed'].add(item['interval'])
                        
                        # Update progress
                        self._update_progress(item['symbol'], item['interval'], 100.0)
                
                # Small delay between batch groups
                if i + batch_size < len(fetch_plan):
                    await asyncio.sleep(self.config.retry_delay)
            
            # Convert sets to lists for JSON serialization
            stats['symbols_processed'] = list(stats['symbols_processed'])
            stats['intervals_processed'] = list(stats['intervals_processed'])
            stats['end_time'] = datetime.now()
            stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()
            
            logger.info(
                f"Historical download complete: {stats['total_candles']} candles, "
                f"{stats['successful_batches']}/{stats['total_batches']} batches successful"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in historical data download: {e}")
            raise
    
    async def _download_batch(self, fetch_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download a single batch of historical data
        
        Args:
            fetch_item: Dictionary with symbol, interval, start, end
        
        Returns:
            Result of the download operation
        """
        symbol = fetch_item['symbol']
        interval = fetch_item['interval']
        start = fetch_item['start']
        end = fetch_item['end']
        
        # Mark as active download
        download_key = f"{symbol}_{interval}"
        self.active_downloads[download_key] = True
        
        try:
            # Fetch data from exchange
            klines = await self.exchange.fetch_historical_klines(
                symbol=symbol,
                interval=interval,
                start_time=start,
                end_time=end
            )
            
            if not klines:
                logger.warning(f"No data returned for {symbol} {interval} from {start} to {end}")
                return {'candles_count': 0}
            
            # Bulk insert into repository
            inserted_count = await self.repository.bulk_insert_klines(klines)
            
            logger.debug(f"Downloaded {inserted_count} candles for {symbol} {interval}")
            
            return {
                'candles_count': inserted_count,
                'symbol': symbol,
                'interval': interval
            }
            
        finally:
            # Mark as inactive
            self.active_downloads[download_key] = False
    
    async def detect_and_fill_gaps(
        self,
        symbols: List[str],
        intervals: List[str],
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """
        Detect and fill data gaps for specified symbols
        
        Args:
            symbols: List of trading symbols
            intervals: List of kline intervals
            lookback_days: Number of days to look back for gaps
        
        Returns:
            Statistics about gaps detected and filled
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            
            logger.info(f"Detecting gaps for {len(symbols)} symbols, {len(intervals)} intervals")
            
            gaps_stats = {
                'total_gaps': 0,
                'gaps_filled': 0,
                'gaps_by_symbol': {},
                'errors': []
            }
            
            for symbol in symbols:
                for interval in intervals:
                    try:
                        # Detect gaps
                        gaps = await self.repository.get_data_gaps(
                            symbol=symbol,
                            interval=interval,
                            start=start_date,
                            end=end_date
                        )
                        
                        if gaps:
                            logger.info(f"Found {len(gaps)} gaps for {symbol} {interval}")
                            gaps_stats['total_gaps'] += len(gaps)
                            
                            if symbol not in gaps_stats['gaps_by_symbol']:
                                gaps_stats['gaps_by_symbol'][symbol] = {}
                            gaps_stats['gaps_by_symbol'][symbol][interval] = len(gaps)
                            
                            # Fill each gap
                            for gap_start, gap_end in gaps:
                                try:
                                    klines = await self.exchange.fetch_historical_klines(
                                        symbol=symbol,
                                        interval=interval,
                                        start_time=gap_start,
                                        end_time=gap_end
                                    )
                                    
                                    if klines:
                                        await self.repository.bulk_insert_klines(klines)
                                        gaps_stats['gaps_filled'] += 1
                                        logger.debug(f"Filled gap for {symbol} {interval}: {gap_start} to {gap_end}")
                                    
                                except Exception as e:
                                    logger.error(f"Error filling gap for {symbol} {interval}: {e}")
                                    gaps_stats['errors'].append(f"{symbol} {interval}: {str(e)}")
                    
                    except Exception as e:
                        logger.error(f"Error detecting gaps for {symbol} {interval}: {e}")
                        gaps_stats['errors'].append(f"{symbol} {interval}: {str(e)}")
            
            logger.info(
                f"Gap detection complete: {gaps_stats['total_gaps']} gaps found, "
                f"{gaps_stats['gaps_filled']} filled"
            )
            
            return gaps_stats
            
        except Exception as e:
            logger.error(f"Error in gap detection and filling: {e}")
            raise
    
    async def validate_data_integrity(
        self,
        symbols: List[str],
        intervals: List[str]
    ) -> Dict[str, Any]:
        """
        Validate data integrity for specified symbols
        
        Args:
            symbols: List of trading symbols
            intervals: List of kline intervals
        
        Returns:
            Validation results
        """
        validation_results = {
            'valid_count': 0,
            'invalid_count': 0,
            'issues': [],
            'details': {}
        }
        
        for symbol in symbols:
            for interval in intervals:
                try:
                    result = await self.repository.validate_data_integrity(symbol, interval)
                    
                    key = f"{symbol}_{interval}"
                    validation_results['details'][key] = result
                    
                    if result.get('is_valid'):
                        validation_results['valid_count'] += 1
                    else:
                        validation_results['invalid_count'] += 1
                        validation_results['issues'].append({
                            'symbol': symbol,
                            'interval': interval,
                            'issues': result.get('issues', [])
                        })
                    
                except Exception as e:
                    logger.error(f"Error validating {symbol} {interval}: {e}")
                    validation_results['issues'].append({
                        'symbol': symbol,
                        'interval': interval,
                        'error': str(e)
                    })
        
        return validation_results
    
    def _update_progress(self, symbol: str, interval: str, progress: float):
        """Update download progress tracking"""
        key = f"{symbol}_{interval}"
        self.download_progress[key] = progress
    
    def get_download_status(self) -> Dict[str, Any]:
        """Get current download status"""
        return {
            'active_downloads': sum(1 for v in self.active_downloads.values() if v),
            'progress': self.download_progress.copy(),
            'total_candles': self.total_candles_downloaded
        }
    
    async def cleanup_old_data(
        self,
        retention_days: int = 365,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Clean up old historical data
        
        Args:
            retention_days: Number of days of data to retain
            dry_run: If True, only report what would be deleted
        
        Returns:
            Cleanup statistics
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Cleaning up data older than {cutoff_date}")
        
        # This would call repository method to delete old data
        # For now, return placeholder
        return {
            'cutoff_date': cutoff_date.isoformat(),
            'dry_run': dry_run,
            'records_affected': 0
        }