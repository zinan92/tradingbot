"""
SMA Crossover Strategy

Example strategy implementing Simple Moving Average crossover logic.
This matches the strategy shown in the screenshot (SmaCross(n1=10, n2=20)).
"""

from backtesting.lib import crossover
import pandas as pd
import numpy as np
from typing import Optional

from src.infrastructure.backtesting.strategy_adapter import BaseStrategy, IndicatorMixin


class SmaCrossStrategy(BaseStrategy, IndicatorMixin):
    """
    Simple Moving Average Crossover Strategy
    
    Generates buy signals when fast SMA crosses above slow SMA.
    Generates sell signals when fast SMA crosses below slow SMA.
    
    Parameters:
        n1: Fast SMA period (default: 10)
        n2: Slow SMA period (default: 20)
    """
    
    # Strategy parameters (can be optimized)
    n1 = 10  # Fast SMA period
    n2 = 20  # Slow SMA period
    
    # Risk management parameters
    stop_loss_pct = 0.02  # 2% stop loss
    take_profit_pct = 0.05  # 5% take profit
    position_size = 0.95  # Use 95% of capital per trade
    
    def initialize_indicators(self):
        """Initialize SMA indicators"""
        # Calculate SMAs using the I() method for proper backtesting.py integration
        self.sma1 = self.I(self.SMA, self.data.Close, self.n1)
        self.sma2 = self.I(self.SMA, self.data.Close, self.n2)
        
        # Store for analysis
        self.crossover_points = []
    
    def should_buy(self) -> bool:
        """
        Determine if a buy signal is present.
        
        Buy when:
        - Fast SMA crosses above slow SMA
        - Both SMAs are trending up (optional filter)
        """
        # Check for golden cross (fast SMA crosses above slow SMA)
        if crossover(self.sma1, self.sma2):
            # Optional: Add trend filter
            # Check if both SMAs are trending up
            if len(self.sma1) > 1 and len(self.sma2) > 1:
                sma1_trending_up = self.sma1[-1] > self.sma1[-2]
                sma2_trending_up = self.sma2[-1] > self.sma2[-2]
                
                # Only buy if trend is favorable
                # Comment out for pure crossover strategy
                # if not (sma1_trending_up and sma2_trending_up):
                #     return False
            
            self.crossover_points.append({
                'time': self.data.index[-1],
                'type': 'golden_cross',
                'price': self.data.Close[-1]
            })
            return True
        
        return False
    
    def should_sell(self) -> bool:
        """
        Determine if a sell signal is present.
        
        Sell when:
        - Fast SMA crosses below slow SMA (death cross)
        """
        # Check for death cross (fast SMA crosses below slow SMA)
        if crossover(self.sma2, self.sma1):
            self.crossover_points.append({
                'time': self.data.index[-1],
                'type': 'death_cross',
                'price': self.data.Close[-1]
            })
            return True
        
        return False


class EnhancedSmaCrossStrategy(SmaCrossStrategy):
    """
    Enhanced SMA Crossover Strategy with additional filters
    
    Adds volume and volatility filters to reduce false signals.
    """
    
    # Additional parameters
    volume_factor = 1.5  # Volume must be 1.5x average
    volatility_threshold = 0.02  # Minimum volatility for entry
    
    def initialize_indicators(self):
        """Initialize enhanced indicators"""
        # Call parent initialization
        super().initialize_indicators()
        
        # Add volume moving average
        self.volume_sma = self.I(self.SMA, self.data.Volume, 20)
        
        # Add volatility indicator (using ATR proxy)
        self.volatility = self.I(self._calculate_volatility, self.data, 14)
    
    def _calculate_volatility(self, data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calculate volatility using High-Low range"""
        hl_range = data.High - data.Low
        volatility = hl_range.rolling(window=period).mean() / data.Close.rolling(window=period).mean()
        return volatility.fillna(0).values
    
    def should_buy(self) -> bool:
        """Enhanced buy signal with volume confirmation"""
        # First check basic SMA crossover
        if not super().should_buy():
            return False
        
        # Check volume confirmation
        if self.data.Volume[-1] < self.volume_sma[-1] * self.volume_factor:
            return False
        
        # Check volatility threshold
        if self.volatility[-1] < self.volatility_threshold:
            return False
        
        return True


class AdaptiveSmaCrossStrategy(SmaCrossStrategy):
    """
    Adaptive SMA Crossover Strategy
    
    Adjusts SMA periods based on market volatility.
    Uses shorter periods in high volatility, longer in low volatility.
    """
    
    # Base parameters
    n1_base = 10
    n2_base = 20
    adapt_factor = 2  # How much to adjust periods
    
    def initialize_indicators(self):
        """Initialize adaptive indicators"""
        # Calculate market volatility
        volatility = self.data.Close.pct_change().rolling(20).std()
        median_vol = volatility.median()
        
        # Adjust SMA periods based on volatility
        # Higher volatility = shorter periods (more responsive)
        # Lower volatility = longer periods (less noise)
        for i in range(len(self.data)):
            if i < 20:
                continue
                
            current_vol = volatility.iloc[i]
            if current_vol > median_vol * 1.5:
                # High volatility - use shorter periods
                self.n1 = max(5, self.n1_base - self.adapt_factor)
                self.n2 = max(10, self.n2_base - self.adapt_factor * 2)
            elif current_vol < median_vol * 0.5:
                # Low volatility - use longer periods
                self.n1 = self.n1_base + self.adapt_factor
                self.n2 = self.n2_base + self.adapt_factor * 2
            else:
                # Normal volatility - use base periods
                self.n1 = self.n1_base
                self.n2 = self.n2_base
        
        # Initialize SMAs with final periods
        super().initialize_indicators()