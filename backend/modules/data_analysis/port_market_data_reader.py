"""
Port for reading market data for analysis
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd


class MarketDataReaderPort(ABC):
    """Port for reading market data for analysis and indicators"""
    
    @abstractmethod
    async def get_ohlcv_data(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get OHLCV data as a DataFrame
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_time: Start of data range
            end_time: End of data range (optional)
            limit: Maximum number of records
            
        Returns:
            DataFrame with OHLCV data
        """
        pass
        
    @abstractmethod
    async def get_latest_candles(
        self,
        symbol: str,
        interval: str,
        count: int = 100
    ) -> pd.DataFrame:
        """
        Get the latest N candles
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            count: Number of candles to retrieve
            
        Returns:
            DataFrame with latest candles
        """
        pass
        
    @abstractmethod
    async def get_symbols_data(
        self,
        symbols: List[str],
        interval: str,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Get OHLCV data for multiple symbols
        
        Args:
            symbols: List of trading symbols
            interval: Time interval
            start_time: Start of data range
            end_time: End of data range
            
        Returns:
            Dictionary mapping symbols to DataFrames
        """
        pass
        
    @abstractmethod
    async def check_data_availability(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Check data availability for a symbol
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_time: Start of range to check
            end_time: End of range to check
            
        Returns:
            Dictionary with availability information
        """
        pass