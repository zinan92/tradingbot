"""
MACD Divergence Strategy

Moving Average Convergence Divergence strategy with histogram analysis.
Trades based on MACD signal line crossovers and histogram momentum.
"""

from backtesting.lib import crossover
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple

from src.infrastructure.backtesting.strategy_adapter import BaseStrategy, IndicatorMixin


class MACDStrategy(BaseStrategy, IndicatorMixin):
    """
    MACD Divergence Strategy
    
    Generates signals based on:
    - MACD line crossing signal line
    - Histogram momentum changes
    - Optional: Price/MACD divergence detection
    
    Parameters:
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)
        use_histogram: Trade based on histogram momentum (default: True)
        use_divergence: Detect price/MACD divergence (default: False)
    """
    
    # MACD parameters
    fast_period = 12
    slow_period = 26
    signal_period = 9
    
    # Strategy options
    use_histogram = True  # Consider histogram momentum
    use_divergence = False  # Look for divergence patterns
    histogram_threshold = 0.0  # Minimum histogram value for entry
    
    # Divergence detection
    divergence_lookback = 30  # Bars to look back for divergence
    min_divergence_strength = 0.02  # Minimum % difference for divergence
    
    # Risk management
    stop_loss_pct = 0.025  # 2.5% stop loss
    take_profit_pct = 0.05  # 5% take profit
    position_size = 0.95
    
    # Exit options
    exit_on_signal_cross = True  # Exit when MACD crosses signal line
    exit_on_histogram_flip = False  # Exit when histogram changes sign
    
    def initialize_indicators(self):
        """Initialize MACD indicators"""
        # Calculate MACD components
        close_prices = self.data.Close
        
        # Calculate MACD line, signal line, and histogram
        macd_data = self.I(self.MACD, close_prices, 
                          self.fast_period, self.slow_period, self.signal_period)
        
        # Unpack MACD components
        self.macd_line = macd_data[0]
        self.signal_line = macd_data[1]
        self.histogram = macd_data[2]
        
        # Store signals for analysis
        self.macd_signals = []
        self.divergences = []
        self.histogram_peaks = []
    
    def MACD(self, series, fast: int, slow: int, signal: int) -> Tuple:
        """
        Calculate MACD components
        
        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        # Convert to pandas Series if needed
        if not isinstance(series, pd.Series):
            series = pd.Series(series)
            
        # Calculate EMAs
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        
        # MACD line
        macd = ema_fast - ema_slow
        
        # Signal line
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        
        # Histogram
        histogram = macd - signal_line
        
        return macd, signal_line, histogram
    
    def detect_histogram_momentum(self) -> Optional[str]:
        """
        Detect histogram momentum changes
        
        Returns:
            'bullish' for increasing histogram
            'bearish' for decreasing histogram
            None if no clear momentum
        """
        if len(self.histogram) < 3:
            return None
        
        # Check histogram trend over last 3 bars
        hist_1 = self.histogram[-1]
        hist_2 = self.histogram[-2]
        hist_3 = self.histogram[-3]
        
        # Bullish momentum: histogram increasing
        if hist_1 > hist_2 > hist_3:
            # Additional check: histogram crossing above zero
            if hist_2 <= 0 < hist_1:
                return 'bullish_strong'
            return 'bullish'
        
        # Bearish momentum: histogram decreasing
        if hist_1 < hist_2 < hist_3:
            # Additional check: histogram crossing below zero
            if hist_2 >= 0 > hist_1:
                return 'bearish_strong'
            return 'bearish'
        
        return None
    
    def detect_divergence(self) -> Optional[str]:
        """
        Detect MACD/price divergence
        
        Returns:
            'bullish' for bullish divergence
            'bearish' for bearish divergence
            None if no divergence
        """
        if not self.use_divergence or len(self.data) < self.divergence_lookback:
            return None
        
        # Get recent data
        recent_prices = self.data.Close[-self.divergence_lookback:]
        recent_macd = self.macd_line[-self.divergence_lookback:]
        
        # Find local extrema
        price_peaks = []
        price_troughs = []
        macd_peaks = []
        macd_troughs = []
        
        for i in range(1, len(recent_prices) - 1):
            # Price peaks and troughs
            if recent_prices[i] > recent_prices[i-1] and recent_prices[i] > recent_prices[i+1]:
                price_peaks.append((i, recent_prices[i]))
            if recent_prices[i] < recent_prices[i-1] and recent_prices[i] < recent_prices[i+1]:
                price_troughs.append((i, recent_prices[i]))
            
            # MACD peaks and troughs
            if recent_macd[i] > recent_macd[i-1] and recent_macd[i] > recent_macd[i+1]:
                macd_peaks.append((i, recent_macd[i]))
            if recent_macd[i] < recent_macd[i-1] and recent_macd[i] < recent_macd[i+1]:
                macd_troughs.append((i, recent_macd[i]))
        
        # Check for bullish divergence (price lower low, MACD higher low)
        if len(price_troughs) >= 2 and len(macd_troughs) >= 2:
            if (price_troughs[-1][1] < price_troughs[-2][1] and
                macd_troughs[-1][1] > macd_troughs[-2][1]):
                
                # Check divergence strength
                price_diff = abs(price_troughs[-1][1] - price_troughs[-2][1]) / price_troughs[-2][1]
                if price_diff >= self.min_divergence_strength:
                    self.divergences.append({
                        'time': self.data.index[-1],
                        'type': 'bullish',
                        'price': self.data.Close[-1],
                        'macd': self.macd_line[-1]
                    })
                    return 'bullish'
        
        # Check for bearish divergence (price higher high, MACD lower high)
        if len(price_peaks) >= 2 and len(macd_peaks) >= 2:
            if (price_peaks[-1][1] > price_peaks[-2][1] and
                macd_peaks[-1][1] < macd_peaks[-2][1]):
                
                # Check divergence strength
                price_diff = abs(price_peaks[-1][1] - price_peaks[-2][1]) / price_peaks[-2][1]
                if price_diff >= self.min_divergence_strength:
                    self.divergences.append({
                        'time': self.data.index[-1],
                        'type': 'bearish',
                        'price': self.data.Close[-1],
                        'macd': self.macd_line[-1]
                    })
                    return 'bearish'
        
        return None
    
    def should_buy(self) -> bool:
        """
        Determine if a buy signal is present.
        
        Buy when:
        - MACD crosses above signal line
        - Histogram is positive or increasing (if use_histogram)
        - Optional: Bullish divergence detected
        """
        # MACD crossover
        macd_cross_up = crossover(self.macd_line, self.signal_line)
        
        if not macd_cross_up:
            # Check for divergence as alternative signal
            if self.use_divergence:
                divergence = self.detect_divergence()
                if divergence != 'bullish':
                    return False
            else:
                return False
        
        # Histogram filter
        if self.use_histogram:
            current_histogram = self.histogram[-1]
            
            # Check histogram threshold
            if current_histogram < self.histogram_threshold:
                return False
            
            # Check histogram momentum
            momentum = self.detect_histogram_momentum()
            if momentum not in ['bullish', 'bullish_strong']:
                return False
        
        self.macd_signals.append({
            'time': self.data.index[-1],
            'type': 'buy',
            'macd': self.macd_line[-1],
            'signal': self.signal_line[-1],
            'histogram': self.histogram[-1],
            'price': self.data.Close[-1]
        })
        
        return True
    
    def should_sell(self) -> bool:
        """
        Determine if a sell signal is present.
        
        Sell when:
        - MACD crosses below signal line (if exit_on_signal_cross)
        - Histogram turns negative (if exit_on_histogram_flip)
        - Optional: Bearish divergence detected
        """
        # MACD crossover
        if self.exit_on_signal_cross:
            macd_cross_down = crossover(self.signal_line, self.macd_line)
            if macd_cross_down:
                self.macd_signals.append({
                    'time': self.data.index[-1],
                    'type': 'sell_cross',
                    'macd': self.macd_line[-1],
                    'signal': self.signal_line[-1],
                    'histogram': self.histogram[-1],
                    'price': self.data.Close[-1]
                })
                return True
        
        # Histogram flip
        if self.exit_on_histogram_flip:
            if len(self.histogram) > 1:
                if self.histogram[-2] > 0 >= self.histogram[-1]:
                    self.macd_signals.append({
                        'time': self.data.index[-1],
                        'type': 'sell_histogram',
                        'macd': self.macd_line[-1],
                        'signal': self.signal_line[-1],
                        'histogram': self.histogram[-1],
                        'price': self.data.Close[-1]
                    })
                    return True
        
        # Divergence
        if self.use_divergence:
            divergence = self.detect_divergence()
            if divergence == 'bearish':
                self.macd_signals.append({
                    'time': self.data.index[-1],
                    'type': 'sell_divergence',
                    'macd': self.macd_line[-1],
                    'signal': self.signal_line[-1],
                    'histogram': self.histogram[-1],
                    'price': self.data.Close[-1]
                })
                return True
        
        return False
    
    def next(self):
        """Execute strategy logic for each bar"""
        # Skip if not enough data
        if len(self.data) < max(self.slow_period, self.divergence_lookback):
            return
        
        # Check if we have an open position
        if self.position:
            # Check for exit signals
            if self.should_sell():
                self.position.close()
        else:
            # No position, check for entry signals
            if self.should_buy():
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
            'macd_signals': self.macd_signals,
            'total_signals': len(self.macd_signals),
            'buy_signals': len([s for s in self.macd_signals if s['type'] == 'buy']),
            'sell_signals': len([s for s in self.macd_signals if 'sell' in s['type']]),
            'divergences': self.divergences,
            'bullish_divergences': len([d for d in self.divergences if d['type'] == 'bullish']),
            'bearish_divergences': len([d for d in self.divergences if d['type'] == 'bearish']),
            'parameters': {
                'fast_period': self.fast_period,
                'slow_period': self.slow_period,
                'signal_period': self.signal_period,
                'use_histogram': self.use_histogram,
                'use_divergence': self.use_divergence
            }
        }