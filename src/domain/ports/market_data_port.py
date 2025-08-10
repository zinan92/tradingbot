"""
Market Data Port interface for accessing price data.

This port defines the contract for all market data sources,
including live, historical, and replay adapters.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TimeFrame(Enum):
    """Supported timeframes for klines."""
    TICK = "tick"
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


@dataclass
class Tick:
    """Individual price tick."""
    symbol: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Decimal
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "bid": str(self.bid),
            "ask": str(self.ask),
            "last": str(self.last),
            "volume": str(self.volume)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tick':
        """Create from dictionary."""
        return cls(
            symbol=data["symbol"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            bid=Decimal(data["bid"]),
            ask=Decimal(data["ask"]),
            last=Decimal(data["last"]),
            volume=Decimal(data["volume"])
        )


@dataclass
class Kline:
    """OHLCV candlestick data."""
    symbol: str
    timeframe: TimeFrame
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "timestamp": self.timestamp.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume),
            "trades": self.trades
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Kline':
        """Create from dictionary."""
        return cls(
            symbol=data["symbol"],
            timeframe=TimeFrame(data["timeframe"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            open=Decimal(data["open"]),
            high=Decimal(data["high"]),
            low=Decimal(data["low"]),
            close=Decimal(data["close"]),
            volume=Decimal(data["volume"]),
            trades=data.get("trades", 0)
        )


@dataclass
class MarketDataConfig:
    """Configuration for market data source."""
    symbols: List[str]
    timeframes: List[TimeFrame]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    replay_speed: float = 1.0  # 1.0 = realtime, 0 = as fast as possible
    deterministic: bool = False  # For testing
    record_mode: bool = False  # Whether to record data
    record_path: Optional[str] = None


class MarketDataPort(ABC):
    """
    Abstract port for market data access.
    
    All market data sources must implement this interface.
    """
    
    @abstractmethod
    async def connect(self, config: MarketDataConfig) -> bool:
        """
        Connect to market data source.
        
        Args:
            config: Configuration for connection
            
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from market data source.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to market data source.
        
        Returns:
            True if connected
        """
        pass
    
    @abstractmethod
    async def get_tick(self, symbol: str) -> Optional[Tick]:
        """
        Get latest tick for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Latest tick or None if not available
        """
        pass
    
    @abstractmethod
    async def get_kline(self, symbol: str, timeframe: TimeFrame) -> Optional[Kline]:
        """
        Get latest kline for symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Kline timeframe
            
        Returns:
            Latest kline or None if not available
        """
        pass
    
    @abstractmethod
    async def get_klines(
        self, 
        symbol: str, 
        timeframe: TimeFrame,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Kline]:
        """
        Get historical klines.
        
        Args:
            symbol: Trading symbol
            timeframe: Kline timeframe
            limit: Maximum number of klines
            start_time: Start time for historical data
            end_time: End time for historical data
            
        Returns:
            List of klines
        """
        pass
    
    @abstractmethod
    async def stream_ticks(self, symbols: List[str]) -> AsyncIterator[Tick]:
        """
        Stream live ticks for symbols.
        
        Args:
            symbols: List of symbols to stream
            
        Yields:
            Ticks as they arrive
        """
        pass
    
    @abstractmethod
    async def stream_klines(
        self, 
        symbols: List[str], 
        timeframe: TimeFrame
    ) -> AsyncIterator[Kline]:
        """
        Stream live klines for symbols.
        
        Args:
            symbols: List of symbols to stream
            timeframe: Kline timeframe
            
        Yields:
            Klines as they complete
        """
        pass
    
    @abstractmethod
    def subscribe_tick(self, symbol: str, callback: Callable[[Tick], None]):
        """
        Subscribe to tick updates.
        
        Args:
            symbol: Symbol to subscribe
            callback: Function to call with new ticks
        """
        pass
    
    @abstractmethod
    def subscribe_kline(
        self, 
        symbol: str, 
        timeframe: TimeFrame, 
        callback: Callable[[Kline], None]
    ):
        """
        Subscribe to kline updates.
        
        Args:
            symbol: Symbol to subscribe
            timeframe: Kline timeframe
            callback: Function to call with new klines
        """
        pass
    
    @abstractmethod
    def unsubscribe_all(self):
        """Unsubscribe from all subscriptions."""
        pass
    
    @abstractmethod
    def get_adapter_name(self) -> str:
        """
        Get the name of this adapter.
        
        Returns:
            Adapter name
        """
        pass
    
    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get adapter statistics.
        
        Returns:
            Statistics dictionary
        """
        pass