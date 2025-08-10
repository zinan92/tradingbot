"""
Indicator Port

Abstract interface for technical indicator calculations.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd


class IndicatorPort(ABC):
    """Abstract interface for technical indicator calculations"""
    
    @abstractmethod
    def atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range
        
        Args:
            high: High prices series
            low: Low prices series
            close: Close prices series
            period: ATR period (default: 14)
            
        Returns:
            ATR values series
        """
        pass
    
    @abstractmethod
    def macd(
        self,
        close: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, pd.Series]:
        """
        Calculate MACD indicator
        
        Args:
            close: Close prices series
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
            
        Returns:
            Dictionary with 'macd', 'signal', and 'histogram' series
        """
        pass
    
    @abstractmethod
    def rsi(
        self,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Relative Strength Index
        
        Args:
            close: Close prices series
            period: RSI period (default: 14)
            
        Returns:
            RSI values series
        """
        pass
    
    @abstractmethod
    async def compute_batch(
        self,
        symbol: str,
        interval: str,
        since: datetime,
        indicators: List[str]
    ) -> Dict[str, pd.Series]:
        """
        Compute multiple indicators in batch
        
        Args:
            symbol: Trading pair symbol
            interval: Data interval
            since: Start time for indicator calculation
            indicators: List of indicator names to compute
            
        Returns:
            Dictionary mapping indicator names to their calculated series
        """
        pass
    
    @abstractmethod
    def sma(
        self,
        close: pd.Series,
        period: int
    ) -> pd.Series:
        """
        Calculate Simple Moving Average
        
        Args:
            close: Close prices series
            period: SMA period
            
        Returns:
            SMA values series
        """
        pass
    
    @abstractmethod
    def ema(
        self,
        close: pd.Series,
        period: int
    ) -> pd.Series:
        """
        Calculate Exponential Moving Average
        
        Args:
            close: Close prices series
            period: EMA period
            
        Returns:
            EMA values series
        """
        pass
    
    @abstractmethod
    def bollinger_bands(
        self,
        close: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, pd.Series]:
        """
        Calculate Bollinger Bands
        
        Args:
            close: Close prices series
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            Dictionary with 'upper', 'middle', and 'lower' band series
        """
        pass