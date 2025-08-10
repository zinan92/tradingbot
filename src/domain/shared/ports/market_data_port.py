"""
Market Data Port

Abstract interface for market data operations.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncIterator
from decimal import Decimal


class MarketDataPort(ABC):
    """Abstract interface for market data operations"""
    
    @abstractmethod
    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical kline/candlestick data
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Kline interval (e.g., "1m", "5m", "1h", "1d")
            start_time: Start time for historical data
            end_time: Optional end time for historical data
            limit: Optional limit on number of klines to fetch
            
        Returns:
            List of kline dictionaries with OHLCV data
        """
        pass
    
    @abstractmethod
    async def stream_ticks(
        self,
        symbol: str,
        interval: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream real-time tick data
        
        Args:
            symbol: Trading pair symbol
            interval: Update interval for ticks
            
        Yields:
            Real-time tick data dictionaries
        """
        pass
    
    @abstractmethod
    async def latest_freshness(
        self,
        symbol: str,
        interval: str
    ) -> timedelta:
        """
        Get the freshness of the latest data point
        
        Args:
            symbol: Trading pair symbol
            interval: Data interval
            
        Returns:
            Time delta since the last data update
        """
        pass
    
    @abstractmethod
    async def get_current_price(
        self,
        symbol: str
    ) -> Decimal:
        """
        Get current market price for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Current market price
        """
        pass