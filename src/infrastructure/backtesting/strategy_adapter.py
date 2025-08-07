"""
Strategy Adapter for Backtesting

Base strategy class that extends backtesting.py Strategy.
All custom strategies should inherit from BaseStrategy.
"""

from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from abc import abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(Strategy):
    """
    Base strategy class that all trading strategies should inherit from.
    
    Provides common functionality and ensures compatibility with backtesting.py
    """
    
    # Default parameters (can be overridden in subclasses)
    stop_loss_pct = 0.02  # 2% stop loss
    take_profit_pct = 0.05  # 5% take profit
    position_size = 0.95  # Use 95% of available capital per trade
    
    def init(self):
        """
        Initialize strategy indicators and variables.
        
        This method is called once at the beginning of the backtest.
        Subclasses should override this to add their own indicators.
        """
        # Track trade statistics
        self.trade_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Initialize any custom indicators
        self.initialize_indicators()
    
    @abstractmethod
    def initialize_indicators(self):
        """
        Initialize custom indicators for the strategy.
        
        Must be implemented by subclasses.
        
        Example:
            self.sma_fast = self.I(SMA, self.data.Close, 10)
            self.sma_slow = self.I(SMA, self.data.Close, 20)
        """
        pass
    
    @abstractmethod
    def should_buy(self) -> bool:
        """
        Determine if a buy signal is present.
        
        Must be implemented by subclasses.
        
        Returns:
            True if should buy, False otherwise
        """
        pass
    
    @abstractmethod
    def should_sell(self) -> bool:
        """
        Determine if a sell signal is present.
        
        Must be implemented by subclasses.
        
        Returns:
            True if should sell, False otherwise
        """
        pass
    
    def next(self):
        """
        Main strategy logic executed on each bar.
        
        This method is called for each bar in the data.
        """
        # Skip if we don't have enough data
        if len(self.data) < 2:
            return
        
        # Check for exit conditions first
        if self.position:
            # Check stop loss
            if self.should_apply_stop_loss():
                self.position.close()
                self.on_trade_close(is_win=False)
                return
            
            # Check take profit
            if self.should_apply_take_profit():
                self.position.close()
                self.on_trade_close(is_win=True)
                return
            
            # Check for sell signal
            if self.should_sell():
                self.position.close()
                # Determine if it was a win based on P&L
                is_win = self.position.pl_pct > 0
                self.on_trade_close(is_win=is_win)
                return
        
        # Check for entry conditions
        if not self.position:
            if self.should_buy():
                # Calculate position size
                size = self.calculate_position_size()
                if size > 0:
                    self.buy(size=size)
                    self.on_trade_open()
    
    def should_apply_stop_loss(self) -> bool:
        """
        Check if stop loss should be triggered.
        
        Returns:
            True if stop loss should be applied
        """
        if not self.position or self.stop_loss_pct <= 0:
            return False
        
        # Check if current loss exceeds stop loss threshold
        return self.position.pl_pct <= -self.stop_loss_pct
    
    def should_apply_take_profit(self) -> bool:
        """
        Check if take profit should be triggered.
        
        Returns:
            True if take profit should be applied
        """
        if not self.position or self.take_profit_pct <= 0:
            return False
        
        # Check if current profit exceeds take profit threshold
        return self.position.pl_pct >= self.take_profit_pct
    
    def calculate_position_size(self) -> float:
        """
        Calculate the position size for the next trade.
        
        Returns:
            Position size as a fraction of equity (0.0 to 1.0)
        """
        # Use configured position size
        # Can be overridden for more complex sizing strategies
        return self.position_size
    
    def on_trade_open(self):
        """
        Called when a new trade is opened.
        
        Can be overridden by subclasses for custom logic.
        """
        self.trade_count += 1
        logger.debug(f"Trade #{self.trade_count} opened at {self.data.Close[-1]}")
    
    def on_trade_close(self, is_win: bool):
        """
        Called when a trade is closed.
        
        Args:
            is_win: Whether the trade was profitable
        """
        if is_win:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        logger.debug(f"Trade #{self.trade_count} closed. Win: {is_win}")
    
    def get_trade_stats(self) -> Dict[str, Any]:
        """
        Get trade statistics for the strategy.
        
        Returns:
            Dictionary of trade statistics
        """
        win_rate = (self.winning_trades / self.trade_count * 100) if self.trade_count > 0 else 0
        
        return {
            'total_trades': self.trade_count,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate
        }


class IndicatorMixin:
    """
    Mixin class providing common technical indicators
    """
    
    @staticmethod
    def SMA(series, period: int):
        """Simple Moving Average"""
        # Convert to pandas Series if needed
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
        result = series.rolling(period).mean()
        # Fill NaN values with the first valid value or 0
        result = result.bfill().fillna(0)
        return result.values
    
    @staticmethod
    def EMA(series: pd.Series, period: int) -> np.ndarray:
        """Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean().fillna(0).values
    
    @staticmethod
    def RSI(series: pd.Series, period: int = 14) -> np.ndarray:
        """Relative Strength Index"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50).values
    
    @staticmethod
    def MACD(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """MACD indicator"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line.fillna(0).values,
            'signal': signal_line.fillna(0).values,
            'histogram': histogram.fillna(0).values
        }
    
    @staticmethod
    def BollingerBands(series: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, np.ndarray]:
        """Bollinger Bands"""
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return {
            'upper': upper.fillna(series.iloc[0]).values,
            'middle': middle.fillna(series.iloc[0]).values,
            'lower': lower.fillna(series.iloc[0]).values
        }