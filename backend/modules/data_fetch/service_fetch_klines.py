"""
Service for one-shot kline fetching operations

This service handles:
- Single kline fetch requests
- Live WebSocket streaming
- Real-time data subscriptions
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Protocol
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class MarketDataPort(Protocol):
    """Port for market data operations"""
    async def subscribe_symbol(self, symbol: str, data_types: List[str], interval: str) -> None:
        ...
    
    async def unsubscribe_symbol(self, symbol: str) -> None:
        ...
    
    async def get_latest_kline(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        ...
    
    async def validate_symbols(self, symbols: List[str]) -> List[str]:
        ...


class EventBusPort(Protocol):
    """Port for event publishing"""
    def publish(self, event: Any) -> None:
        ...


@dataclass
class KlineFetchConfig:
    """Configuration for kline fetching"""
    symbols: List[str]
    intervals: List[str] = None
    enable_indicators: bool = False
    enable_trades: bool = True
    enable_depth: bool = True


class KlineFetchService:
    """
    Service for fetching market data klines in real-time
    """
    
    def __init__(
        self,
        market_data: MarketDataPort,
        event_bus: EventBusPort,
        config: Optional[KlineFetchConfig] = None
    ):
        self.market_data = market_data
        self.event_bus = event_bus
        self.config = config or KlineFetchConfig(symbols=[])
        
        # State tracking
        self.active_subscriptions: Dict[str, List[str]] = {}
        self.streaming_status: Dict[str, bool] = {}
        self.last_update_times: Dict[str, datetime] = {}
        self.background_tasks: List[asyncio.Task] = []
        
    async def start_live_streaming(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Start live WebSocket streaming for specified symbols
        
        Args:
            symbols: List of symbols to stream (uses config if None)
        
        Returns:
            Status of streaming initialization
        """
        try:
            # Use config defaults if not specified
            symbols = symbols or self.config.symbols
            intervals = self.config.intervals or ['1m', '5m', '15m', '1h', '1d']
            
            # Validate symbols
            validated_symbols = await self.market_data.validate_symbols(symbols)
            
            logger.info(f"Starting live streaming for {len(validated_symbols)} symbols")
            
            # Subscribe to each symbol
            for symbol in validated_symbols:
                # Subscribe to kline streams for each interval
                for interval in intervals:
                    await self.market_data.subscribe_symbol(
                        symbol=symbol,
                        data_types=['kline'],
                        interval=interval
                    )
                
                # Track subscriptions
                if symbol not in self.active_subscriptions:
                    self.active_subscriptions[symbol] = []
                self.active_subscriptions[symbol].extend(intervals)
                
                # Subscribe to additional data types if enabled
                if self.config.enable_trades or self.config.enable_depth:
                    data_types = []
                    if self.config.enable_trades:
                        data_types.extend(['trade', 'ticker'])
                    if self.config.enable_depth:
                        data_types.extend(['depth', 'mark_price'])
                    
                    if data_types:
                        await self.market_data.subscribe_symbol(
                            symbol=symbol,
                            data_types=data_types,
                            interval=intervals[0]  # Use smallest interval
                        )
                
                self.streaming_status[symbol] = True
                self.last_update_times[symbol] = datetime.now()
            
            # Publish streaming started event
            self.event_bus.publish({
                'type': 'streaming_started',
                'symbols': validated_symbols,
                'intervals': intervals,
                'timestamp': datetime.now()
            })
            
            return {
                'status': 'success',
                'symbols': validated_symbols,
                'intervals': intervals,
                'active_subscriptions': len(self.active_subscriptions)
            }
            
        except Exception as e:
            logger.error(f"Error starting live streaming: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def stop_streaming(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Stop live streaming for specified symbols
        
        Args:
            symbols: List of symbols to stop (stops all if None)
        
        Returns:
            Status of streaming termination
        """
        try:
            symbols_to_stop = symbols or list(self.active_subscriptions.keys())
            
            logger.info(f"Stopping streaming for {len(symbols_to_stop)} symbols")
            
            for symbol in symbols_to_stop:
                await self.market_data.unsubscribe_symbol(symbol)
                
                if symbol in self.active_subscriptions:
                    del self.active_subscriptions[symbol]
                if symbol in self.streaming_status:
                    self.streaming_status[symbol] = False
            
            # Cancel background tasks
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()
            self.background_tasks.clear()
            
            # Publish streaming stopped event
            self.event_bus.publish({
                'type': 'streaming_stopped',
                'symbols': symbols_to_stop,
                'timestamp': datetime.now()
            })
            
            return {
                'status': 'success',
                'stopped_symbols': symbols_to_stop,
                'active_subscriptions': len(self.active_subscriptions)
            }
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def fetch_latest_kline(self, symbol: str, interval: str = '1m') -> Optional[Dict[str, Any]]:
        """
        Fetch the latest kline for a symbol
        
        Args:
            symbol: Trading symbol
            interval: Kline interval
        
        Returns:
            Latest kline data or None
        """
        try:
            kline = await self.market_data.get_latest_kline(symbol, interval)
            
            if kline:
                self.last_update_times[symbol] = datetime.now()
                
                # Publish kline fetched event
                self.event_bus.publish({
                    'type': 'kline_fetched',
                    'symbol': symbol,
                    'interval': interval,
                    'kline': kline,
                    'timestamp': datetime.now()
                })
            
            return kline
            
        except Exception as e:
            logger.error(f"Error fetching latest kline for {symbol}: {e}")
            return None
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """
        Get current streaming status
        
        Returns:
            Dictionary with streaming status information
        """
        return {
            'active_symbols': list(self.active_subscriptions.keys()),
            'total_subscriptions': sum(len(intervals) for intervals in self.active_subscriptions.values()),
            'streaming_status': self.streaming_status.copy(),
            'last_updates': {
                symbol: timestamp.isoformat() 
                for symbol, timestamp in self.last_update_times.items()
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on streaming connections
        
        Returns:
            Health status information
        """
        healthy_symbols = []
        unhealthy_symbols = []
        
        for symbol in self.active_subscriptions:
            if symbol in self.last_update_times:
                time_since_update = (datetime.now() - self.last_update_times[symbol]).total_seconds()
                if time_since_update < 60:  # Consider healthy if updated within 60 seconds
                    healthy_symbols.append(symbol)
                else:
                    unhealthy_symbols.append(symbol)
            else:
                unhealthy_symbols.append(symbol)
        
        return {
            'status': 'healthy' if not unhealthy_symbols else 'degraded',
            'healthy_symbols': healthy_symbols,
            'unhealthy_symbols': unhealthy_symbols,
            'total_active': len(self.active_subscriptions),
            'timestamp': datetime.now().isoformat()
        }