"""
Unified Data Manager for managing both historical downloads and live streaming

This module provides a single interface for:
- Historical data downloading
- Live WebSocket streaming
- Data gap detection and filling
- Automatic failover between historical and live modes
"""

import asyncio
import logging
import yaml
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .bulk_data_loader import BulkDataLoader
from .market_data_service import MarketDataService
from .data_manager import DataManager
from ..persistence.postgres.market_data_repository import MarketDataRepository
from ..persistence.postgres.market_data_tables import Base
from ..messaging.in_memory_event_bus import InMemoryEventBus
from ..indicators.indicator_service import IndicatorService

logger = logging.getLogger(__name__)

class UnifiedDataManager:
    """
    Unified manager for all market data operations
    """
    
    def __init__(self, config_path: str = None, database_url: str = None):
        """
        Initialize the unified data manager
        
        Args:
            config_path: Path to configuration file
            database_url: Database connection URL
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Database setup
        self.database_url = database_url or self.config.get('database', {}).get('url', 'postgresql://localhost/tradingbot')
        self.engine = create_engine(self.database_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db_session = Session()
        
        # Repository
        self.repository = MarketDataRepository(self.db_session)
        
        # Event bus
        self.event_bus = InMemoryEventBus()
        
        # Services
        self.bulk_loader = BulkDataLoader(self.db_session)
        self.market_service = MarketDataService(
            db_session=self.db_session,
            event_bus=self.event_bus
        )
        self.data_manager = DataManager(self.db_session)
        self.indicator_service = IndicatorService(
            db_session=self.db_session,
            event_bus=self.event_bus
        )
        
        # State tracking
        self.mode = 'idle'  # idle, historical, live, hybrid
        self.active_symbols: Set[str] = set()
        self.download_progress: Dict[str, float] = {}
        self.streaming_status: Dict[str, bool] = {}
        self.last_update_times: Dict[str, datetime] = {}
        
        # Tasks
        self.background_tasks: List[asyncio.Task] = []
        self.health_check_task: Optional[asyncio.Task] = None
        self.gap_fill_task: Optional[asyncio.Task] = None
        
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if config_path is None:
            # Try default locations
            possible_paths = [
                Path('/Users/park/tradingbot_v2/config/market_data_config.yaml'),
                Path('./config/market_data_config.yaml'),
                Path('../config/market_data_config.yaml')
            ]
            
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        else:
            logger.warning("No configuration file found, using defaults")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
            'intervals': ['5m', '15m', '1h', '4h', '1d'],
            'historical': {
                'days_back': 30,
                'batch_size': 1000,
                'parallel_workers': 4
            },
            'live': {
                'auto_reconnect': True,
                'reconnect_delay': 5,
                'max_reconnect_attempts': 10,
                'store_to_db': True,
                'publish_events': True
            },
            'indicators': {
                'enabled': True,
                'calculate_on_close': True,
                'intervals_to_calculate': ['5m', '15m', '1h'],
                'list': [
                    {'name': 'RSI', 'period': 14},
                    {'name': 'MACD', 'fast': 12, 'slow': 26, 'signal': 9},
                    {'name': 'ATR', 'period': 14},
                    {'name': 'EMA', 'periods': [12, 50, 200]}
                ]
            }
        }
    
    async def start(self):
        """Start the unified data manager"""
        try:
            logger.info("Starting Unified Data Manager...")
            
            # Start services
            await self.bulk_loader.start()
            await self.market_service.start()
            
            # Start background tasks
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            self.gap_fill_task = asyncio.create_task(self._gap_detection_loop())
            
            self.mode = 'idle'
            logger.info("Unified Data Manager started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Unified Data Manager: {e}")
            raise
    
    async def stop(self):
        """Stop the unified data manager"""
        try:
            logger.info("Stopping Unified Data Manager...")
            
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
            
            if self.health_check_task:
                self.health_check_task.cancel()
            
            if self.gap_fill_task:
                self.gap_fill_task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
            
            # Stop services
            await self.bulk_loader.stop()
            await self.market_service.stop()
            await self.indicator_service.stop()
            
            # Close database
            self.db_session.close()
            self.engine.dispose()
            
            self.mode = 'idle'
            logger.info("Unified Data Manager stopped")
            
        except Exception as e:
            logger.error(f"Error stopping Unified Data Manager: {e}")
    
    async def download_historical(self, 
                                 symbols: List[str] = None,
                                 intervals: List[str] = None,
                                 days_back: int = None):
        """
        Download historical data for specified symbols
        
        Args:
            symbols: List of symbols to download (uses config if None)
            intervals: List of intervals to download (uses config if None)
            days_back: Number of days of history to download
        """
        try:
            self.mode = 'historical'
            
            # Use config defaults if not specified
            symbols = symbols or self.config.get('symbols', [])
            intervals = intervals or self.config.get('intervals', [])
            days_back = days_back or self.config.get('historical', {}).get('days_back', 30)
            
            # Validate symbols exist on exchange
            symbols = await self._validate_symbols(symbols)
            
            logger.info(f"Starting historical download for {len(symbols)} symbols, {days_back} days")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Track progress
            total_tasks = len(symbols) * len(intervals)
            completed_tasks = 0
            
            # Download in batches
            batch_size = self.config.get('historical', {}).get('batch_size', 5)
            
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i + batch_size]
                
                logger.info(f"Downloading batch {i//batch_size + 1}: {batch_symbols}")
                
                stats = await self.bulk_loader.download_historical_data(
                    symbols=batch_symbols,
                    intervals=intervals,
                    start_date=start_date,
                    end_date=end_date
                )
                
                completed_tasks += len(batch_symbols) * len(intervals)
                progress = (completed_tasks / total_tasks) * 100
                
                logger.info(f"Progress: {progress:.1f}% - Downloaded {stats['total_candles']:,} candles")
                
                # Update progress tracking
                for symbol in batch_symbols:
                    self.download_progress[symbol] = 100.0
                    self.active_symbols.add(symbol)
                
                # Small delay between batches
                await asyncio.sleep(2)
            
            # Calculate indicators if enabled
            if self.config.get('indicators', {}).get('enabled', False):
                logger.info("Calculating indicators for downloaded data...")
                await self._calculate_indicators(symbols, intervals)
            
            logger.info(f"Historical download complete for {len(symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Error downloading historical data: {e}")
            raise
        finally:
            if self.mode == 'historical':
                self.mode = 'idle'
    
    async def start_live_streaming(self, symbols: List[str] = None):
        """
        Start live WebSocket streaming for specified symbols
        
        Args:
            symbols: List of symbols to stream (uses config if None)
        """
        try:
            self.mode = 'live'
            
            # Use config defaults if not specified
            symbols = symbols or self.config.get('symbols', [])
            intervals = self.config.get('intervals', [])
            
            # Validate symbols
            symbols = await self._validate_symbols(symbols)
            
            logger.info(f"Starting live streaming for {len(symbols)} symbols")
            
            # Subscribe to each symbol
            for symbol in symbols:
                # Subscribe to kline streams for each interval
                for interval in intervals:
                    await self.market_service.subscribe_symbol(
                        symbol=symbol,
                        data_types=['kline'],
                        interval=interval
                    )
                
                # Also subscribe to trade and depth data for smallest interval
                await self.market_service.subscribe_symbol(
                    symbol=symbol,
                    data_types=['trade', 'depth', 'ticker', 'mark_price'],
                    interval='5m'
                )
                
                self.streaming_status[symbol] = True
                self.active_symbols.add(symbol)
                
                logger.info(f"Subscribed to live streams for {symbol}")
                
                # Small delay to avoid overwhelming the API
                await asyncio.sleep(0.5)
            
            # Start periodic indicator calculation if enabled
            if self.config.get('indicators', {}).get('enabled', False):
                for symbol in symbols:
                    for interval in self.config.get('indicators', {}).get('intervals_to_calculate', ['5m']):
                        await self.indicator_service.start_periodic_calculation(
                            symbol=symbol,
                            interval=interval,
                            calculate_every=60  # Calculate every minute
                        )
            
            logger.info(f"Live streaming active for {len(symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Error starting live streaming: {e}")
            raise
    
    async def start_hybrid_mode(self, symbols: List[str] = None):
        """
        Start hybrid mode: download historical then switch to live streaming
        
        Args:
            symbols: List of symbols (uses config if None)
        """
        try:
            self.mode = 'hybrid'
            
            symbols = symbols or self.config.get('symbols', [])
            
            logger.info(f"Starting hybrid mode for {len(symbols)} symbols")
            
            # Step 1: Download historical data
            await self.download_historical(symbols=symbols)
            
            # Step 2: Check for gaps and fill them
            await self._fill_data_gaps(symbols)
            
            # Step 3: Start live streaming
            await self.start_live_streaming(symbols=symbols)
            
            logger.info("Hybrid mode active - historical data loaded and live streaming started")
            
        except Exception as e:
            logger.error(f"Error in hybrid mode: {e}")
            raise
    
    async def _validate_symbols(self, symbols: List[str]) -> List[str]:
        """Validate that symbols exist on the exchange"""
        valid_symbols = []
        
        try:
            exchange_info = await self.market_service.client.get_exchange_info()
            exchange_symbols = {s['symbol'] for s in exchange_info.get('symbols', [])}
            
            for symbol in symbols:
                if symbol.upper() in exchange_symbols:
                    valid_symbols.append(symbol.upper())
                else:
                    logger.warning(f"Symbol {symbol} not found on exchange, skipping")
            
            return valid_symbols
            
        except Exception as e:
            logger.error(f"Error validating symbols: {e}")
            return symbols  # Return original list if validation fails
    
    async def _fill_data_gaps(self, symbols: List[str]):
        """Detect and fill gaps in data"""
        try:
            logger.info("Checking for data gaps...")
            
            for symbol in symbols:
                for interval in self.config.get('intervals', []):
                    # Get latest data timestamp
                    latest = self.repository.get_latest_kline(symbol, interval)
                    
                    if latest:
                        gap_start = latest.close_time
                        gap_end = datetime.now()
                        gap_hours = (gap_end - gap_start).total_seconds() / 3600
                        
                        if gap_hours > 1:  # Gap larger than 1 hour
                            logger.info(f"Found gap for {symbol} {interval}: {gap_hours:.1f} hours")
                            
                            # Download missing data
                            stats = await self.bulk_loader.download_historical_data(
                                symbols=[symbol],
                                intervals=[interval],
                                start_date=gap_start,
                                end_date=gap_end
                            )
                            
                            logger.info(f"Filled gap with {stats['total_candles']} candles")
            
        except Exception as e:
            logger.error(f"Error filling data gaps: {e}")
    
    async def _calculate_indicators(self, symbols: List[str], intervals: List[str]):
        """Calculate indicators for downloaded data"""
        try:
            indicator_config = self.config.get('indicators', {})
            
            for symbol in symbols:
                for interval in intervals:
                    if interval in indicator_config.get('intervals_to_calculate', []):
                        await self.indicator_service.calculate_and_publish(symbol, interval)
                        logger.debug(f"Calculated indicators for {symbol} {interval}")
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
    
    async def _health_check_loop(self):
        """Background task to monitor health of connections"""
        interval = self.config.get('monitoring', {}).get('health_check_interval', 60)
        
        while True:
            try:
                await asyncio.sleep(interval)
                
                # Check WebSocket connections
                active_streams = len(self.market_service.client.active_streams)
                
                # Check database connection
                db_alive = self.repository.is_connection_alive()
                
                # Check for stale data
                stale_symbols = []
                for symbol in self.active_symbols:
                    latest = self.repository.get_latest_kline(symbol, '5m')
                    if latest:
                        minutes_old = (datetime.now() - latest.close_time).total_seconds() / 60
                        if minutes_old > 10:
                            stale_symbols.append(symbol)
                            self.last_update_times[symbol] = latest.close_time
                
                # Log health status
                logger.info(f"Health Check - Mode: {self.mode}, Active Streams: {active_streams}, "
                          f"DB: {'OK' if db_alive else 'ERROR'}, Stale: {len(stale_symbols)}")
                
                # Attempt to reconnect stale symbols
                if stale_symbols and self.mode == 'live':
                    logger.warning(f"Reconnecting stale symbols: {stale_symbols}")
                    for symbol in stale_symbols:
                        await self.market_service.unsubscribe_symbol(symbol)
                        await asyncio.sleep(1)
                        await self.market_service.subscribe_symbol(
                            symbol=symbol,
                            data_types=['kline'],
                            interval='5m'
                        )
                
            except Exception as e:
                logger.error(f"Error in health check: {e}")
    
    async def _gap_detection_loop(self):
        """Background task to detect and fill data gaps"""
        interval = 300  # Check every 5 minutes
        
        while True:
            try:
                await asyncio.sleep(interval)
                
                if self.mode in ['live', 'hybrid'] and self.active_symbols:
                    # Check for gaps in active symbols
                    for symbol in self.active_symbols:
                        latest = self.repository.get_latest_kline(symbol, '5m')
                        if latest:
                            gap_minutes = (datetime.now() - latest.close_time).total_seconds() / 60
                            
                            if gap_minutes > 15:  # Gap larger than 15 minutes
                                logger.warning(f"Detected gap for {symbol}: {gap_minutes:.1f} minutes")
                                
                                # Fill the gap
                                await self.bulk_loader.download_historical_data(
                                    symbols=[symbol],
                                    intervals=['5m'],
                                    start_date=latest.close_time,
                                    end_date=datetime.now()
                                )
                
            except Exception as e:
                logger.error(f"Error in gap detection: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the data manager"""
        status = {
            'mode': self.mode,
            'active_symbols': list(self.active_symbols),
            'download_progress': self.download_progress,
            'streaming_status': self.streaming_status,
            'market_service_stats': self.market_service.get_stats(),
            'database_stats': self.data_manager.get_storage_statistics(),
            'last_updates': {}
        }
        
        # Get last update times for each symbol
        for symbol in self.active_symbols:
            latest = self.repository.get_latest_kline(symbol, '5m')
            if latest:
                status['last_updates'][symbol] = {
                    'timestamp': latest.close_time.isoformat(),
                    'minutes_ago': (datetime.now() - latest.close_time).total_seconds() / 60
                }
        
        return status
    
    async def check_data_completeness(self) -> Dict[str, Any]:
        """Check data completeness for all configured symbols"""
        report = {
            'symbols': {},
            'summary': {
                'total_symbols': 0,
                'complete_symbols': 0,
                'incomplete_symbols': 0,
                'total_candles': 0
            }
        }
        
        symbols = self.config.get('symbols', [])
        intervals = self.config.get('intervals', [])
        
        for symbol in symbols:
            symbol_data = {
                'intervals': {},
                'total_candles': 0,
                'is_complete': True
            }
            
            for interval in intervals:
                count = self.repository.count_klines(
                    symbol, interval,
                    datetime.now() - timedelta(days=30),
                    datetime.now()
                )
                
                expected = self.data_manager._calculate_expected_candles(
                    interval,
                    datetime.now() - timedelta(days=30),
                    datetime.now()
                )
                
                completeness = (count / expected * 100) if expected > 0 else 0
                
                symbol_data['intervals'][interval] = {
                    'count': count,
                    'expected': expected,
                    'completeness_pct': completeness
                }
                
                symbol_data['total_candles'] += count
                
                if completeness < 95:
                    symbol_data['is_complete'] = False
            
            report['symbols'][symbol] = symbol_data
            report['summary']['total_candles'] += symbol_data['total_candles']
            
            if symbol_data['is_complete']:
                report['summary']['complete_symbols'] += 1
            else:
                report['summary']['incomplete_symbols'] += 1
        
        report['summary']['total_symbols'] = len(symbols)
        
        return report