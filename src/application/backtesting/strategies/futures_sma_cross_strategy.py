"""
Futures SMA Crossover Strategy

Example strategy implementing Simple Moving Average crossover logic
with support for both LONG and SHORT positions for futures trading.
"""

from backtesting.lib import crossover
import pandas as pd
import numpy as np
from typing import Optional

from src.infrastructure.backtesting.futures_strategy_adapter import (
    FuturesBaseStrategy, 
    IndicatorMixin,
    PositionDirection
)


class FuturesSmaCrossStrategy(FuturesBaseStrategy, IndicatorMixin):
    """
    Futures SMA Crossover Strategy with LONG/SHORT capabilities
    
    - Goes LONG when fast SMA crosses above slow SMA
    - Goes SHORT when fast SMA crosses below slow SMA
    - Uses leverage for position sizing
    - Implements stop-loss and take-profit for both directions
    
    Parameters:
        n1: Fast SMA period (default: 10)
        n2: Slow SMA period (default: 20)
        leverage: Trading leverage (default: 10x)
    """
    
    # Strategy parameters (can be optimized)
    n1 = 10  # Fast SMA period
    n2 = 20  # Slow SMA period
    
    # Risk management parameters
    stop_loss_pct = 0.02  # 2% stop loss
    take_profit_pct = 0.05  # 5% take profit
    position_size = 0.95  # Use 95% of capital per trade
    
    # Futures-specific parameters
    leverage = 10  # 10x leverage
    market_commission = 0.0004  # 0.04% for market orders
    limit_commission = 0.0002  # 0.02% for limit orders
    allow_shorts = True  # Enable short positions
    use_trailing_stop = False  # Disable trailing stop for basic strategy
    
    def initialize_indicators(self):
        """Initialize SMA indicators"""
        # Calculate SMAs using the I() method for proper backtesting.py integration
        self.sma1 = self.I(self.SMA, self.data.Close, self.n1)
        self.sma2 = self.I(self.SMA, self.data.Close, self.n2)
        
        # Store for analysis
        self.crossover_points = []
        self.trend_direction = None
    
    def should_go_long(self) -> bool:
        """
        Determine if a LONG entry signal is present.
        
        Buy when:
        - Fast SMA crosses above slow SMA (golden cross)
        - Optional: Add trend confirmation
        """
        # Check for golden cross (fast SMA crosses above slow SMA)
        if crossover(self.sma1, self.sma2):
            # Optional: Add trend filter
            if len(self.sma1) > 1 and len(self.sma2) > 1:
                # Confirm uptrend
                sma1_trending_up = self.sma1[-1] > self.sma1[-2]
                
                self.crossover_points.append({
                    'time': self.data.index[-1],
                    'type': 'golden_cross',
                    'price': self.data.Close[-1]
                })
                
                self.trend_direction = 'UP'
                return True
        
        return False
    
    def should_go_short(self) -> bool:
        """
        Determine if a SHORT entry signal is present.
        
        Sell when:
        - Fast SMA crosses below slow SMA (death cross)
        - Optional: Add trend confirmation
        """
        # Check for death cross (fast SMA crosses below slow SMA)
        if crossover(self.sma2, self.sma1):
            # Optional: Add trend filter
            if len(self.sma1) > 1 and len(self.sma2) > 1:
                # Confirm downtrend
                sma1_trending_down = self.sma1[-1] < self.sma1[-2]
                
                self.crossover_points.append({
                    'time': self.data.index[-1],
                    'type': 'death_cross',
                    'price': self.data.Close[-1]
                })
                
                self.trend_direction = 'DOWN'
                return True
        
        return False
    
    def should_close_long(self) -> bool:
        """
        Determine if a LONG exit signal is present.
        
        Close long when:
        - Fast SMA crosses below slow SMA (trend reversal)
        - Or stop-loss/take-profit hit (handled by base class)
        """
        # Exit on opposite signal
        if crossover(self.sma2, self.sma1):
            return True
        
        # Additional exit conditions can be added here
        # For example: RSI overbought, volume divergence, etc.
        
        return False
    
    def should_close_short(self) -> bool:
        """
        Determine if a SHORT exit signal is present.
        
        Close short when:
        - Fast SMA crosses above slow SMA (trend reversal)
        - Or stop-loss/take-profit hit (handled by base class)
        """
        # Exit on opposite signal
        if crossover(self.sma1, self.sma2):
            return True
        
        # Additional exit conditions can be added here
        
        return False


class FuturesMeanReversionStrategy(FuturesBaseStrategy, IndicatorMixin):
    """
    Mean Reversion Strategy for Futures
    
    - Goes SHORT when price is above upper Bollinger Band
    - Goes LONG when price is below lower Bollinger Band
    - Closes positions when price returns to middle band
    
    Parameters:
        bb_period: Bollinger Band period (default: 20)
        bb_std: Standard deviations (default: 2)
        rsi_period: RSI period for confirmation (default: 14)
    """
    
    # Strategy parameters
    bb_period = 20
    bb_std = 2
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought = 70
    
    # Risk management
    stop_loss_pct = 0.03  # 3% stop loss (wider for mean reversion)
    take_profit_pct = 0.04  # 4% take profit
    position_size = 0.8  # Use 80% of capital
    
    # Futures parameters
    leverage = 5  # Lower leverage for mean reversion
    allow_shorts = True
    use_trailing_stop = True
    trailing_stop_pct = 0.025
    
    def initialize_indicators(self):
        """Initialize Bollinger Bands and RSI indicators"""
        # Calculate Bollinger Bands components separately
        close_series = pd.Series(self.data.Close)
        sma = close_series.rolling(window=self.bb_period).mean()
        std = close_series.rolling(window=self.bb_period).std()
        
        # Calculate bands
        self.bb_upper = self.I(lambda: (sma + (std * self.bb_std)).fillna(close_series.iloc[0]).values)
        self.bb_middle = self.I(lambda: sma.fillna(close_series.iloc[0]).values)
        self.bb_lower = self.I(lambda: (sma - (std * self.bb_std)).fillna(close_series.iloc[0]).values)
        
        # Calculate RSI for confirmation
        self.rsi = self.I(self.RSI, self.data.Close, self.rsi_period)
        
        # Track extremes
        self.extreme_points = []
    
    def should_go_long(self) -> bool:
        """
        Go LONG when oversold (price below lower BB + RSI confirmation)
        """
        if len(self.data) < 2:
            return False
        
        price = self.data.Close[-1]
        
        # Check if price is below lower Bollinger Band
        if price < self.bb_lower[-1]:
            # Confirm with RSI
            if self.rsi[-1] < self.rsi_oversold:
                self.extreme_points.append({
                    'time': self.data.index[-1],
                    'type': 'oversold',
                    'price': price
                })
                return True
        
        return False
    
    def should_go_short(self) -> bool:
        """
        Go SHORT when overbought (price above upper BB + RSI confirmation)
        """
        if len(self.data) < 2:
            return False
        
        price = self.data.Close[-1]
        
        # Check if price is above upper Bollinger Band
        if price > self.bb_upper[-1]:
            # Confirm with RSI
            if self.rsi[-1] > self.rsi_overbought:
                self.extreme_points.append({
                    'time': self.data.index[-1],
                    'type': 'overbought',
                    'price': price
                })
                return True
        
        return False
    
    def should_close_long(self) -> bool:
        """
        Close LONG when price returns to middle band or above
        """
        if len(self.data) < 2:
            return False
        
        price = self.data.Close[-1]
        
        # Close when price reaches middle band (mean reversion complete)
        if price >= self.bb_middle[-1]:
            return True
        
        # Also close if RSI becomes overbought (trend reversal)
        if self.rsi[-1] > self.rsi_overbought:
            return True
        
        return False
    
    def should_close_short(self) -> bool:
        """
        Close SHORT when price returns to middle band or below
        """
        if len(self.data) < 2:
            return False
        
        price = self.data.Close[-1]
        
        # Close when price reaches middle band (mean reversion complete)
        if price <= self.bb_middle[-1]:
            return True
        
        # Also close if RSI becomes oversold (trend reversal)
        if self.rsi[-1] < self.rsi_oversold:
            return True
        
        return False


class FuturesMomentumStrategy(FuturesBaseStrategy, IndicatorMixin):
    """
    Momentum Strategy for Futures
    
    - Uses MACD for trend direction
    - Goes LONG when MACD crosses above signal line in uptrend
    - Goes SHORT when MACD crosses below signal line in downtrend
    - Uses RSI to filter overbought/oversold conditions
    
    Parameters:
        macd_fast: Fast EMA period (default: 12)
        macd_slow: Slow EMA period (default: 26)
        macd_signal: Signal line period (default: 9)
    """
    
    # Strategy parameters
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9
    rsi_period = 14
    trend_sma = 50  # SMA for trend determination
    
    # Risk management
    stop_loss_pct = 0.025  # 2.5% stop loss
    take_profit_pct = 0.06  # 6% take profit
    position_size = 0.9  # Use 90% of capital
    
    # Futures parameters
    leverage = 8  # 8x leverage for momentum
    allow_shorts = True
    use_trailing_stop = True
    trailing_stop_pct = 0.03
    
    def initialize_indicators(self):
        """Initialize MACD, RSI, and trend indicators"""
        # Calculate MACD components separately
        close_series = pd.Series(self.data.Close)
        ema_fast = close_series.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close_series.ewm(span=self.macd_slow, adjust=False).mean()
        
        macd_line_values = ema_fast - ema_slow
        signal_line_values = macd_line_values.ewm(span=self.macd_signal, adjust=False).mean()
        histogram_values = macd_line_values - signal_line_values
        
        self.macd_line = self.I(lambda: macd_line_values.fillna(0).values)
        self.signal_line = self.I(lambda: signal_line_values.fillna(0).values)
        self.macd_histogram = self.I(lambda: histogram_values.fillna(0).values)
        
        # Calculate RSI
        self.rsi = self.I(self.RSI, self.data.Close, self.rsi_period)
        
        # Calculate trend SMA
        self.trend_sma = self.I(self.SMA, self.data.Close, self.trend_sma)
        
        # Track signals
        self.momentum_signals = []
    
    def should_go_long(self) -> bool:
        """
        Go LONG on bullish momentum
        """
        if len(self.data) < 2:
            return False
        
        price = self.data.Close[-1]
        
        # Check uptrend (price above trend SMA)
        if price > self.trend_sma[-1]:
            # Check MACD bullish crossover
            if crossover(self.macd_line, self.signal_line):
                # Confirm RSI not overbought
                if self.rsi[-1] < 70:
                    self.momentum_signals.append({
                        'time': self.data.index[-1],
                        'type': 'bullish_momentum',
                        'price': price
                    })
                    return True
        
        return False
    
    def should_go_short(self) -> bool:
        """
        Go SHORT on bearish momentum
        """
        if len(self.data) < 2:
            return False
        
        price = self.data.Close[-1]
        
        # Check downtrend (price below trend SMA)
        if price < self.trend_sma[-1]:
            # Check MACD bearish crossover
            if crossover(self.signal_line, self.macd_line):
                # Confirm RSI not oversold
                if self.rsi[-1] > 30:
                    self.momentum_signals.append({
                        'time': self.data.index[-1],
                        'type': 'bearish_momentum',
                        'price': price
                    })
                    return True
        
        return False
    
    def should_close_long(self) -> bool:
        """
        Close LONG on momentum loss
        """
        if len(self.data) < 2:
            return False
        
        # Close on MACD bearish crossover
        if crossover(self.signal_line, self.macd_line):
            return True
        
        # Close if RSI becomes extremely overbought
        if self.rsi[-1] > 80:
            return True
        
        # Close if price falls below trend SMA (trend change)
        if self.data.Close[-1] < self.trend_sma[-1]:
            return True
        
        return False
    
    def should_close_short(self) -> bool:
        """
        Close SHORT on momentum loss
        """
        if len(self.data) < 2:
            return False
        
        # Close on MACD bullish crossover
        if crossover(self.macd_line, self.signal_line):
            return True
        
        # Close if RSI becomes extremely oversold
        if self.rsi[-1] < 20:
            return True
        
        # Close if price rises above trend SMA (trend change)
        if self.data.Close[-1] > self.trend_sma[-1]:
            return True
        
        return False