"""
EMA Crossover Strategy

Exponential Moving Average crossover strategy for trend following.
Generates signals when fast EMA crosses above/below slow EMA.
"""

from backtesting.lib import crossover
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from src.infrastructure.backtesting.strategy_adapter import BaseStrategy, IndicatorMixin


class EMACrossStrategy(BaseStrategy, IndicatorMixin):
    """
    Exponential Moving Average Crossover Strategy
    
    Generates buy signals when fast EMA crosses above slow EMA.
    Generates sell signals when fast EMA crosses below slow EMA.
    
    Parameters:
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        use_volume_filter: Filter signals by volume (default: False)
        volume_threshold: Volume must be above this percentile (default: 50)
    """
    
    # Strategy parameters (can be optimized)
    fast_period = 12  # Fast EMA period
    slow_period = 26  # Slow EMA period
    
    # Volume filter parameters
    use_volume_filter = False
    volume_threshold = 50  # Percentile threshold for volume
    
    # Risk management parameters
    stop_loss_pct = 0.02  # 2% stop loss
    take_profit_pct = 0.05  # 5% take profit
    position_size = 0.95  # Use 95% of capital per trade
    trailing_stop_pct = 0.03  # 3% trailing stop
    
    def initialize_indicators(self):
        """Initialize EMA indicators"""
        # Calculate EMAs using the I() method for proper backtesting.py integration
        self.ema_fast = self.I(self.EMA, self.data.Close, self.fast_period)
        self.ema_slow = self.I(self.EMA, self.data.Close, self.slow_period)
        
        # Calculate volume moving average if volume filter is enabled
        if self.use_volume_filter:
            self.volume_ma = self.I(self.SMA, self.data.Volume, 20)
            self.volume_percentile = np.percentile(self.data.Volume, self.volume_threshold)
        
        # Store for analysis
        self.crossover_points = []
        self.signal_strength = []
    
    def EMA(self, series, period: int):
        """Calculate Exponential Moving Average"""
        # Convert to pandas Series if needed
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
        return series.ewm(span=period, adjust=False).mean()
    
    def should_buy(self) -> bool:
        """
        Determine if a buy signal is present.
        
        Buy when:
        - Fast EMA crosses above slow EMA (golden cross)
        - Optional: Volume is above threshold
        - Optional: Both EMAs are trending up
        """
        # Check for golden cross (fast EMA crosses above slow EMA)
        if crossover(self.ema_fast, self.ema_slow):
            # Volume filter
            if self.use_volume_filter:
                if self.data.Volume[-1] < self.volume_percentile:
                    return False
            
            # Optional: Add trend filter
            # Check if both EMAs are trending up
            if len(self.ema_fast) > 2 and len(self.ema_slow) > 2:
                fast_trending_up = self.ema_fast[-1] > self.ema_fast[-2]
                slow_trending_up = self.ema_slow[-1] > self.ema_slow[-2]
                
                # Calculate signal strength (distance between EMAs)
                ema_distance = abs(self.ema_fast[-1] - self.ema_slow[-1]) / self.data.Close[-1]
                self.signal_strength.append(ema_distance)
            
            self.crossover_points.append({
                'time': self.data.index[-1],
                'type': 'golden_cross',
                'price': self.data.Close[-1],
                'ema_fast': self.ema_fast[-1],
                'ema_slow': self.ema_slow[-1]
            })
            return True
        
        return False
    
    def should_sell(self) -> bool:
        """
        Determine if a sell signal is present.
        
        Sell when:
        - Fast EMA crosses below slow EMA (death cross)
        - Stop loss or take profit hit
        """
        # Check for death cross (fast EMA crosses below slow EMA)
        if crossover(self.ema_slow, self.ema_fast):
            self.crossover_points.append({
                'time': self.data.index[-1],
                'type': 'death_cross',
                'price': self.data.Close[-1],
                'ema_fast': self.ema_fast[-1],
                'ema_slow': self.ema_slow[-1]
            })
            return True
        
        return False
    
    def next(self):
        """Execute strategy logic for each bar"""
        # Skip if not enough data for indicators
        if len(self.data) < max(self.fast_period, self.slow_period):
            return
        
        # Check if we have an open position
        if self.position:
            # Check for exit signals
            if self.should_sell():
                self.position.close()
            else:
                # Update trailing stop if configured
                # Note: backtesting.py doesn't support dynamic stop loss updates
                pass
        else:
            # No position, check for entry signals
            if self.should_buy():
                # Calculate position size
                size = self.position_size
                
                # Calculate stop loss and take profit levels
                stop_loss = self.data.Close[-1] * (1 - self.stop_loss_pct)
                take_profit = self.data.Close[-1] * (1 + self.take_profit_pct)
                
                # Open position
                self.buy(size=size, sl=stop_loss, tp=take_profit)
    
    def get_analysis(self) -> Dict[str, Any]:
        """Return strategy analysis data"""
        return {
            'crossover_points': self.crossover_points,
            'total_crossovers': len(self.crossover_points),
            'golden_crosses': len([c for c in self.crossover_points if c['type'] == 'golden_cross']),
            'death_crosses': len([c for c in self.crossover_points if c['type'] == 'death_cross']),
            'avg_signal_strength': np.mean(self.signal_strength) if self.signal_strength else 0,
            'parameters': {
                'fast_period': self.fast_period,
                'slow_period': self.slow_period,
                'use_volume_filter': self.use_volume_filter,
                'stop_loss_pct': self.stop_loss_pct,
                'take_profit_pct': self.take_profit_pct
            }
        }