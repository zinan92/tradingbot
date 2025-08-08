"""
RSI Mean Reversion Strategy

Relative Strength Index based mean reversion strategy.
Buys when RSI indicates oversold conditions, sells when overbought.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from src.infrastructure.backtesting.strategy_adapter import BaseStrategy, IndicatorMixin


class RSIStrategy(BaseStrategy, IndicatorMixin):
    """
    RSI Mean Reversion Strategy
    
    Generates buy signals when RSI is oversold (< 30).
    Generates sell signals when RSI is overbought (> 70).
    
    Parameters:
        rsi_period: RSI calculation period (default: 14)
        oversold_level: RSI level considered oversold (default: 30)
        overbought_level: RSI level considered overbought (default: 70)
        use_divergence: Look for RSI divergence (default: False)
    """
    
    # Strategy parameters
    rsi_period = 14
    oversold_level = 30
    overbought_level = 70
    
    # Divergence detection
    use_divergence = False
    divergence_lookback = 20  # Bars to look back for divergence
    
    # Confirmation parameters
    use_volume_confirmation = False
    use_trend_filter = False
    trend_period = 200  # SMA period for trend filter
    
    # Risk management
    stop_loss_pct = 0.03  # 3% stop loss
    take_profit_pct = 0.06  # 6% take profit
    position_size = 0.95  # Use 95% of capital
    
    # Exit parameters
    exit_on_neutral = True  # Exit when RSI returns to neutral (50)
    neutral_level = 50
    
    def initialize_indicators(self):
        """Initialize RSI and supporting indicators"""
        # Calculate RSI
        self.rsi = self.I(self.RSI, self.data.Close, self.rsi_period)
        
        # Trend filter (optional)
        if self.use_trend_filter:
            self.trend_sma = self.I(self.SMA, self.data.Close, self.trend_period)
        
        # Volume moving average for confirmation
        if self.use_volume_confirmation:
            self.volume_ma = self.I(self.SMA, self.data.Volume, 20)
        
        # Store analysis data
        self.rsi_signals = []
        self.divergences = []
    
    def RSI(self, series, period: int):
        """Calculate Relative Strength Index"""
        # Convert to pandas Series if needed
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
        
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def detect_divergence(self) -> Optional[str]:
        """
        Detect bullish or bearish RSI divergence
        
        Returns:
            'bullish' for bullish divergence
            'bearish' for bearish divergence
            None if no divergence detected
        """
        if not self.use_divergence or len(self.data) < self.divergence_lookback:
            return None
        
        # Get recent price and RSI data
        recent_prices = self.data.Close[-self.divergence_lookback:]
        recent_rsi = self.rsi[-self.divergence_lookback:]
        
        # Find local minima and maxima
        price_min_idx = recent_prices.argmin()
        price_max_idx = recent_prices.argmax()
        rsi_min_idx = recent_rsi.argmin()
        rsi_max_idx = recent_rsi.argmax()
        
        # Bullish divergence: price makes lower low, RSI makes higher low
        if price_min_idx > self.divergence_lookback // 2:  # Recent low
            earlier_low_idx = recent_prices[:price_min_idx].argmin()
            if (recent_prices[price_min_idx] < recent_prices[earlier_low_idx] and
                recent_rsi[price_min_idx] > recent_rsi[earlier_low_idx]):
                self.divergences.append({
                    'time': self.data.index[-1],
                    'type': 'bullish',
                    'price': self.data.Close[-1],
                    'rsi': self.rsi[-1]
                })
                return 'bullish'
        
        # Bearish divergence: price makes higher high, RSI makes lower high
        if price_max_idx > self.divergence_lookback // 2:  # Recent high
            earlier_high_idx = recent_prices[:price_max_idx].argmax()
            if (recent_prices[price_max_idx] > recent_prices[earlier_high_idx] and
                recent_rsi[price_max_idx] < recent_rsi[earlier_high_idx]):
                self.divergences.append({
                    'time': self.data.index[-1],
                    'type': 'bearish',
                    'price': self.data.Close[-1],
                    'rsi': self.rsi[-1]
                })
                return 'bearish'
        
        return None
    
    def should_buy(self) -> bool:
        """
        Determine if a buy signal is present.
        
        Buy when:
        - RSI is oversold (< 30)
        - Optional: Bullish divergence detected
        - Optional: Price above trend SMA (trend filter)
        - Optional: Volume confirmation
        """
        current_rsi = self.rsi[-1]
        
        # Basic oversold condition
        is_oversold = current_rsi < self.oversold_level
        
        if not is_oversold:
            # Check for bullish divergence as alternative signal
            if self.use_divergence:
                divergence = self.detect_divergence()
                if divergence != 'bullish':
                    return False
            else:
                return False
        
        # Trend filter
        if self.use_trend_filter:
            if self.data.Close[-1] < self.trend_sma[-1]:
                return False  # Don't buy in downtrend
        
        # Volume confirmation
        if self.use_volume_confirmation:
            if self.data.Volume[-1] < self.volume_ma[-1]:
                return False  # Need above-average volume
        
        # Check if RSI is starting to turn up (momentum shift)
        if len(self.rsi) > 2:
            rsi_turning_up = self.rsi[-1] > self.rsi[-2]
            if not rsi_turning_up and not self.use_divergence:
                return False
        
        self.rsi_signals.append({
            'time': self.data.index[-1],
            'type': 'buy',
            'rsi': current_rsi,
            'price': self.data.Close[-1]
        })
        
        return True
    
    def should_sell(self) -> bool:
        """
        Determine if a sell signal is present.
        
        Sell when:
        - RSI is overbought (> 70)
        - RSI returns to neutral (if exit_on_neutral is True)
        - Optional: Bearish divergence detected
        """
        current_rsi = self.rsi[-1]
        
        # Basic overbought condition
        is_overbought = current_rsi > self.overbought_level
        
        # Exit on neutral RSI
        if self.exit_on_neutral and self.position:
            # If we bought on oversold, exit when RSI returns to neutral
            if hasattr(self, '_entry_rsi') and self._entry_rsi < self.oversold_level:
                if current_rsi >= self.neutral_level:
                    self.rsi_signals.append({
                        'time': self.data.index[-1],
                        'type': 'sell_neutral',
                        'rsi': current_rsi,
                        'price': self.data.Close[-1]
                    })
                    return True
        
        if is_overbought:
            self.rsi_signals.append({
                'time': self.data.index[-1],
                'type': 'sell_overbought',
                'rsi': current_rsi,
                'price': self.data.Close[-1]
            })
            return True
        
        # Check for bearish divergence
        if self.use_divergence:
            divergence = self.detect_divergence()
            if divergence == 'bearish':
                self.rsi_signals.append({
                    'time': self.data.index[-1],
                    'type': 'sell_divergence',
                    'rsi': current_rsi,
                    'price': self.data.Close[-1]
                })
                return True
        
        return False
    
    def next(self):
        """Execute strategy logic for each bar"""
        # Skip if not enough data
        if len(self.data) < max(self.rsi_period, self.trend_period if self.use_trend_filter else 0):
            return
        
        # Check if we have an open position
        if self.position:
            # Check for exit signals
            if self.should_sell():
                self.position.close()
        else:
            # No position, check for entry signals
            if self.should_buy():
                # Store entry RSI for exit logic
                self._entry_rsi = self.rsi[-1]
                
                # Calculate position size
                size = self.position_size
                
                # Calculate stop loss and take profit
                stop_loss = self.data.Close[-1] * (1 - self.stop_loss_pct)
                take_profit = self.data.Close[-1] * (1 + self.take_profit_pct)
                
                # Open position
                self.buy(size=size, sl=stop_loss, tp=take_profit)
    
    def get_analysis(self) -> Dict[str, Any]:
        """Return strategy analysis data"""
        return {
            'rsi_signals': self.rsi_signals,
            'total_signals': len(self.rsi_signals),
            'buy_signals': len([s for s in self.rsi_signals if s['type'] == 'buy']),
            'sell_signals': len([s for s in self.rsi_signals if 'sell' in s['type']]),
            'divergences': self.divergences,
            'total_divergences': len(self.divergences),
            'parameters': {
                'rsi_period': self.rsi_period,
                'oversold_level': self.oversold_level,
                'overbought_level': self.overbought_level,
                'use_divergence': self.use_divergence,
                'exit_on_neutral': self.exit_on_neutral
            }
        }