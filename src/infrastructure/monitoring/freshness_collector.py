"""
Data Freshness Collector

Background service that monitors data freshness for all symbols.
"""
import asyncio
import time
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
import logging

from src.domain.shared.ports.market_data_port import MarketDataPort
from src.infrastructure.monitoring.metrics_v2 import system_metrics

logger = logging.getLogger(__name__)


class DataFreshnessCollector:
    """
    Monitors data freshness for all active symbols
    
    Tracks the age of the latest data point for each symbol/interval
    combination and updates metrics accordingly.
    """
    
    def __init__(
        self,
        market_data_port: MarketDataPort,
        update_interval: int = 10,
        staleness_threshold: int = 300
    ):
        """
        Initialize freshness collector
        
        Args:
            market_data_port: Port for accessing market data
            update_interval: How often to check freshness (seconds)
            staleness_threshold: Data considered stale after this many seconds
        """
        self.market_data_port = market_data_port
        self.update_interval = update_interval
        self.staleness_threshold = staleness_threshold
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # Track monitored symbols
        self._monitored_symbols: Set[tuple[str, str]] = set()
        
        # Cache last update times
        self._last_updates: Dict[tuple[str, str], datetime] = {}
    
    def add_symbol(self, symbol: str, interval: str):
        """Add a symbol to monitor"""
        self._monitored_symbols.add((symbol, interval))
        logger.info(f"Added {symbol}:{interval} to freshness monitoring")
    
    def remove_symbol(self, symbol: str, interval: str):
        """Remove a symbol from monitoring"""
        self._monitored_symbols.discard((symbol, interval))
        logger.info(f"Removed {symbol}:{interval} from freshness monitoring")
    
    async def start(self):
        """Start the freshness collector"""
        if self._running:
            logger.warning("Freshness collector already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._collection_loop())
        logger.info("Data freshness collector started")
    
    async def stop(self):
        """Stop the freshness collector"""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Data freshness collector stopped")
    
    async def _collection_loop(self):
        """Main collection loop"""
        while self._running:
            try:
                await self._update_freshness_metrics()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in freshness collection: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def _update_freshness_metrics(self):
        """Update freshness metrics for all monitored symbols"""
        current_time = datetime.now()
        
        for symbol, interval in self._monitored_symbols:
            try:
                # Get latest data timestamp
                latest_timestamp = await self._get_latest_timestamp(symbol, interval)
                
                if latest_timestamp:
                    # Calculate age in seconds
                    age_seconds = (current_time - latest_timestamp).total_seconds()
                    
                    # Update metric
                    system_metrics['data_freshness'].labels(
                        symbol=symbol, 
                        interval=interval
                    ).set(age_seconds)
                    
                    # Log if data is stale
                    if age_seconds > self.staleness_threshold:
                        logger.warning(
                            f"Data for {symbol}:{interval} is stale "
                            f"({age_seconds:.1f}s old)"
                        )
                    
                    # Update cache
                    self._last_updates[(symbol, interval)] = latest_timestamp
                else:
                    # No data available
                    system_metrics['data_freshness'].labels(
                        symbol=symbol,
                        interval=interval
                    ).set(float('inf'))
                    logger.warning(f"No data available for {symbol}:{interval}")
                    
            except Exception as e:
                logger.error(f"Error checking freshness for {symbol}:{interval}: {e}")
                # Set to infinity to indicate error
                system_metrics['data_freshness'].labels(
                    symbol=symbol,
                    interval=interval
                ).set(float('inf'))
    
    async def _get_latest_timestamp(self, symbol: str, interval: str) -> Optional[datetime]:
        """
        Get timestamp of latest data point
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            
        Returns:
            Timestamp of latest data or None
        """
        try:
            # Get recent data (last 2 candles)
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=1)
            
            candles = await self.market_data_port.get_candles(
                symbol=symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                limit=2
            )
            
            if candles and len(candles) > 0:
                # Return timestamp of latest candle
                latest = candles[-1]
                return latest.get('timestamp') or latest.get('open_time')
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching latest timestamp for {symbol}:{interval}: {e}")
            return None
    
    def get_freshness_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Get summary of data freshness
        
        Returns:
            Dictionary mapping symbol:interval to age in seconds
        """
        current_time = datetime.now()
        summary = {}
        
        for (symbol, interval), last_update in self._last_updates.items():
            key = f"{symbol}:{interval}"
            if last_update:
                age = (current_time - last_update).total_seconds()
                summary[key] = {
                    'age_seconds': age,
                    'is_stale': age > self.staleness_threshold,
                    'last_update': last_update.isoformat()
                }
            else:
                summary[key] = {
                    'age_seconds': float('inf'),
                    'is_stale': True,
                    'last_update': None
                }
        
        return summary
    
    def simulate_staleness(self, symbol: str, interval: str, age_seconds: float):
        """
        Simulate stale data for testing
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            age_seconds: Simulated age in seconds
        """
        # Update metric with simulated staleness
        system_metrics['data_freshness'].labels(
            symbol=symbol,
            interval=interval
        ).set(age_seconds)
        
        # Update cache with old timestamp
        old_timestamp = datetime.now() - timedelta(seconds=age_seconds)
        self._last_updates[(symbol, interval)] = old_timestamp
        
        logger.info(f"Simulated staleness for {symbol}:{interval}: {age_seconds}s")


class MockMarketDataPort(MarketDataPort):
    """Mock market data port for testing"""
    
    def __init__(self):
        self._latest_timestamps: Dict[tuple[str, str], datetime] = {}
        self._paused = False
    
    async def get_candles(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> list:
        """Get mock candles"""
        if self._paused:
            # Return old data when paused
            timestamp = datetime.now() - timedelta(minutes=30)
        else:
            # Return fresh data
            timestamp = datetime.now() - timedelta(seconds=5)
        
        self._latest_timestamps[(symbol, interval)] = timestamp
        
        return [{
            'timestamp': timestamp,
            'open': 45000,
            'high': 45100,
            'low': 44900,
            'close': 45050,
            'volume': 100
        }]
    
    async def get_ticker(self, symbol: str) -> dict:
        """Get mock ticker"""
        return {
            'symbol': symbol,
            'last': 45000,
            'bid': 44999,
            'ask': 45001,
            'volume': 1000
        }
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> dict:
        """Get mock order book"""
        return {
            'bids': [[44999, 10], [44998, 20]],
            'asks': [[45001, 10], [45002, 20]]
        }
    
    async def subscribe_trades(self, symbol: str, callback: callable):
        """Mock trade subscription"""
        pass
    
    async def subscribe_orderbook(self, symbol: str, callback: callable):
        """Mock orderbook subscription"""
        pass
    
    def pause_updates(self):
        """Pause data updates to simulate staleness"""
        self._paused = True
    
    def resume_updates(self):
        """Resume data updates"""
        self._paused = False