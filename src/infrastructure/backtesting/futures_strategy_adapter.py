"""
Futures Strategy Adapter for Backtesting

Enhanced strategy base class that supports futures trading features:
- LONG and SHORT positions
- Leverage/margin trading
- Separate commission rates for market/limit orders
- Position direction tracking
"""

from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Literal
from abc import abstractmethod
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PositionDirection(Enum):
    """Position direction for futures trading"""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class OrderType(Enum):
    """Order types with different commission rates"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class FuturesBaseStrategy(Strategy):
    """
    Enhanced base strategy class for futures trading.
    
    Supports:
    - Both LONG and SHORT positions
    - Leverage trading
    - Different commission rates for order types
    - Advanced position management
    """
    
    # Default parameters (can be overridden in subclasses)
    stop_loss_pct = 0.02  # 2% stop loss
    take_profit_pct = 0.05  # 5% take profit
    position_size = 0.95  # Use 95% of available capital per trade
    
    # Futures-specific parameters
    leverage = 10  # Default 10x leverage
    market_commission = 0.0004  # 0.04% for market orders
    limit_commission = 0.0002  # 0.02% for limit orders
    allow_shorts = True  # Enable short positions
    
    # Risk management
    max_position_size = 1.0  # Maximum position as fraction of equity
    use_trailing_stop = False  # Use trailing stop-loss
    trailing_stop_pct = 0.03  # 3% trailing stop
    
    def init(self):
        """
        Initialize strategy indicators and variables.
        
        This method is called once at the beginning of the backtest.
        Subclasses should override this to add their own indicators.
        """
        # Track trade statistics
        self.trade_count = 0
        self.long_trades = 0
        self.short_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        # Position tracking
        self.position_direction = PositionDirection.NEUTRAL
        self.entry_price = None
        self.highest_price = None  # For trailing stop on longs
        self.lowest_price = None   # For trailing stop on shorts
        
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
    def should_go_long(self) -> bool:
        """
        Determine if a LONG entry signal is present.
        
        Must be implemented by subclasses.
        
        Returns:
            True if should enter long position, False otherwise
        """
        pass
    
    @abstractmethod
    def should_go_short(self) -> bool:
        """
        Determine if a SHORT entry signal is present.
        
        Must be implemented by subclasses.
        
        Returns:
            True if should enter short position, False otherwise
        """
        pass
    
    @abstractmethod
    def should_close_long(self) -> bool:
        """
        Determine if a LONG exit signal is present.
        
        Must be implemented by subclasses.
        
        Returns:
            True if should close long position, False otherwise
        """
        pass
    
    @abstractmethod
    def should_close_short(self) -> bool:
        """
        Determine if a SHORT exit signal is present.
        
        Must be implemented by subclasses.
        
        Returns:
            True if should close short position, False otherwise
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
        
        # Update trailing stop prices
        if self.position:
            self._update_trailing_stops()
        
        # Check for exit conditions first
        if self.position:
            if self.position_direction == PositionDirection.LONG:
                # Check long exit conditions
                if self._should_exit_long():
                    self.position.close()
                    self._on_trade_close()
                    return
            
            elif self.position_direction == PositionDirection.SHORT:
                # Check short exit conditions
                if self._should_exit_short():
                    self.position.close()
                    self._on_trade_close()
                    return
        
        # Check for entry conditions
        if not self.position:
            # Check for LONG entry
            if self.should_go_long():
                size = self._calculate_position_size_with_leverage()
                if size > 0:
                    self.buy(size=size)
                    self._on_trade_open(PositionDirection.LONG)
                    return
            
            # Check for SHORT entry (if enabled)
            if self.allow_shorts and self.should_go_short():
                size = self._calculate_position_size_with_leverage()
                if size > 0:
                    self.sell(size=size)  # Sell to open short position
                    self._on_trade_open(PositionDirection.SHORT)
                    return
    
    def _should_exit_long(self) -> bool:
        """
        Check if should exit LONG position.
        
        Returns:
            True if should exit
        """
        # Check stop loss
        if self._check_long_stop_loss():
            return True
        
        # Check take profit
        if self._check_long_take_profit():
            return True
        
        # Check trailing stop
        if self.use_trailing_stop and self._check_long_trailing_stop():
            return True
        
        # Check strategy-specific exit signal
        if self.should_close_long():
            return True
        
        return False
    
    def _should_exit_short(self) -> bool:
        """
        Check if should exit SHORT position.
        
        Returns:
            True if should exit
        """
        # Check stop loss
        if self._check_short_stop_loss():
            return True
        
        # Check take profit
        if self._check_short_take_profit():
            return True
        
        # Check trailing stop
        if self.use_trailing_stop and self._check_short_trailing_stop():
            return True
        
        # Check strategy-specific exit signal
        if self.should_close_short():
            return True
        
        return False
    
    def _check_long_stop_loss(self) -> bool:
        """Check if long position hit stop loss"""
        if not self.position or self.stop_loss_pct <= 0:
            return False
        
        current_price = self.data.Close[-1]
        loss_pct = (current_price - self.entry_price) / self.entry_price
        return loss_pct <= -self.stop_loss_pct
    
    def _check_long_take_profit(self) -> bool:
        """Check if long position hit take profit"""
        if not self.position or self.take_profit_pct <= 0:
            return False
        
        current_price = self.data.Close[-1]
        profit_pct = (current_price - self.entry_price) / self.entry_price
        return profit_pct >= self.take_profit_pct
    
    def _check_short_stop_loss(self) -> bool:
        """Check if short position hit stop loss"""
        if not self.position or self.stop_loss_pct <= 0:
            return False
        
        current_price = self.data.Close[-1]
        loss_pct = (self.entry_price - current_price) / self.entry_price
        return loss_pct <= -self.stop_loss_pct
    
    def _check_short_take_profit(self) -> bool:
        """Check if short position hit take profit"""
        if not self.position or self.take_profit_pct <= 0:
            return False
        
        current_price = self.data.Close[-1]
        profit_pct = (self.entry_price - current_price) / self.entry_price
        return profit_pct >= self.take_profit_pct
    
    def _check_long_trailing_stop(self) -> bool:
        """Check if long position hit trailing stop"""
        if not self.highest_price:
            return False
        
        current_price = self.data.Close[-1]
        drawdown_pct = (current_price - self.highest_price) / self.highest_price
        return drawdown_pct <= -self.trailing_stop_pct
    
    def _check_short_trailing_stop(self) -> bool:
        """Check if short position hit trailing stop"""
        if not self.lowest_price:
            return False
        
        current_price = self.data.Close[-1]
        drawdown_pct = (self.lowest_price - current_price) / self.lowest_price
        return drawdown_pct <= -self.trailing_stop_pct
    
    def _update_trailing_stops(self):
        """Update trailing stop prices"""
        current_price = self.data.Close[-1]
        
        if self.position_direction == PositionDirection.LONG:
            if not self.highest_price or current_price > self.highest_price:
                self.highest_price = current_price
        
        elif self.position_direction == PositionDirection.SHORT:
            if not self.lowest_price or current_price < self.lowest_price:
                self.lowest_price = current_price
    
    def _calculate_position_size_with_leverage(self) -> float:
        """
        Calculate position size considering leverage.
        
        Returns:
            Position size as a fraction of equity
        """
        # Base position size
        base_size = self.position_size
        
        # Apply leverage (increases buying power)
        leveraged_size = base_size * self.leverage
        
        # Cap at maximum position size
        final_size = min(leveraged_size, self.max_position_size)
        
        return final_size
    
    def _on_trade_open(self, direction: PositionDirection):
        """
        Called when a new trade is opened.
        
        Args:
            direction: Position direction (LONG or SHORT)
        """
        self.trade_count += 1
        self.position_direction = direction
        self.entry_price = self.data.Close[-1]
        
        # Reset trailing stop prices
        self.highest_price = self.entry_price if direction == PositionDirection.LONG else None
        self.lowest_price = self.entry_price if direction == PositionDirection.SHORT else None
        
        if direction == PositionDirection.LONG:
            self.long_trades += 1
            logger.debug(f"LONG trade #{self.trade_count} opened at {self.entry_price}")
        else:
            self.short_trades += 1
            logger.debug(f"SHORT trade #{self.trade_count} opened at {self.entry_price}")
    
    def _on_trade_close(self):
        """
        Called when a trade is closed.
        """
        if not self.position:
            return
        
        exit_price = self.data.Close[-1]
        
        # Calculate P&L based on position direction
        if self.position_direction == PositionDirection.LONG:
            pnl_pct = (exit_price - self.entry_price) / self.entry_price
        else:  # SHORT
            pnl_pct = (self.entry_price - exit_price) / self.entry_price
        
        # Apply leverage to P&L
        leveraged_pnl = pnl_pct * self.leverage
        
        # Track win/loss
        if leveraged_pnl > 0:
            self.winning_trades += 1
            result = "WIN"
        else:
            self.losing_trades += 1
            result = "LOSS"
        
        logger.debug(
            f"{self.position_direction.value} trade #{self.trade_count} closed. "
            f"Entry: {self.entry_price:.2f}, Exit: {exit_price:.2f}, "
            f"P&L: {leveraged_pnl:.2%} ({result})"
        )
        
        # Reset position tracking
        self.position_direction = PositionDirection.NEUTRAL
        self.entry_price = None
        self.highest_price = None
        self.lowest_price = None
    
    def get_trade_stats(self) -> Dict[str, Any]:
        """
        Get detailed trade statistics for the strategy.
        
        Returns:
            Dictionary of trade statistics
        """
        win_rate = (self.winning_trades / self.trade_count * 100) if self.trade_count > 0 else 0
        long_ratio = (self.long_trades / self.trade_count * 100) if self.trade_count > 0 else 0
        short_ratio = (self.short_trades / self.trade_count * 100) if self.trade_count > 0 else 0
        
        return {
            'total_trades': self.trade_count,
            'long_trades': self.long_trades,
            'short_trades': self.short_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'long_ratio': long_ratio,
            'short_ratio': short_ratio,
            'leverage_used': self.leverage
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
    def EMA(series, period: int) -> np.ndarray:
        """Exponential Moving Average"""
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
        return series.ewm(span=period, adjust=False).mean().fillna(0).values
    
    @staticmethod
    def RSI(series, period: int = 14) -> np.ndarray:
        """Relative Strength Index"""
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50).values
    
    @staticmethod
    def MACD(series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """MACD indicator"""
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
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
    def BollingerBands(series, period: int = 20, std_dev: int = 2) -> Dict[str, np.ndarray]:
        """Bollinger Bands"""
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        
        return {
            'upper': upper.fillna(series.iloc[0] if len(series) > 0 else 0).values,
            'middle': middle.fillna(series.iloc[0] if len(series) > 0 else 0).values,
            'lower': lower.fillna(series.iloc[0] if len(series) > 0 else 0).values
        }