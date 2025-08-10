"""
Port definitions for market data operations
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal


class MarketDataPort(ABC):
    """Port for fetching market data from external sources"""
    
    @abstractmethod
    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch latest klines for a symbol"""
        pass
        
    @abstractmethod
    async def fetch_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch historical klines for a time range"""
        pass
        
    @abstractmethod
    async def fetch_ticker_price(
        self,
        symbol: str
    ) -> Decimal:
        """Fetch current ticker price"""
        pass
        
    @abstractmethod
    async def fetch_order_book(
        self,
        symbol: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Fetch order book depth"""
        pass
        
    @abstractmethod
    async def fetch_24h_ticker(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """Fetch 24-hour ticker statistics"""
        pass


class MarketDataRepositoryPort(ABC):
    """Port for persisting market data"""
    
    @abstractmethod
    async def bulk_insert_klines(
        self,
        klines: List[Dict[str, Any]],
        symbol: str,
        interval: str
    ) -> int:
        """Bulk insert kline data"""
        pass
        
    @abstractmethod
    async def find_data_gaps(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, datetime]]:
        """Find gaps in historical data"""
        pass
        
    @abstractmethod
    async def count_records(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> int:
        """Count records in a time range"""
        pass
        
    @abstractmethod
    async def find_duplicates(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> int:
        """Find duplicate records"""
        pass
        
    @abstractmethod
    async def delete_old_records(
        self,
        cutoff_date: datetime
    ) -> int:
        """Delete records older than cutoff date"""
        pass
        
    @abstractmethod
    async def get_latest_kline(
        self,
        symbol: str,
        interval: str
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent kline for a symbol"""
        pass
        
    @abstractmethod
    async def get_klines_range(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get klines within a time range"""
        pass