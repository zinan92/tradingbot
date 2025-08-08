"""
Futures Grid Trading Strategy

Grid trading strategy that places multiple buy and sell orders at predetermined 
price intervals to profit from market volatility in ranging markets.
Optimized for cryptocurrency futures trading with leverage support.
"""

from backtesting.lib import crossover
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

from src.infrastructure.backtesting.futures_strategy_adapter import (
    FuturesBaseStrategy, 
    IndicatorMixin,
    PositionDirection
)


@dataclass
class GridLevel:
    """Represents a single grid level with its properties"""
    price: float
    level_type: str  # 'BUY' or 'SELL'
    position_size: float
    is_filled: bool = False
    position_id: Optional[str] = None
    entry_time: Optional[pd.Timestamp] = None
    
    def __hash__(self):
        return hash((self.price, self.level_type))


class GridMode(Enum):
    """Grid trading modes"""
    NEUTRAL = "neutral"      # Equal buy/sell levels
    LONG_BIAS = "long_bias"   # More buy levels
    SHORT_BIAS = "short_bias" # More sell levels
    ADAPTIVE = "adaptive"     # Adjust based on trend


class FuturesGridStrategy(FuturesBaseStrategy, IndicatorMixin):
    """
    Grid Trading Strategy for Futures Markets
    
    Creates a grid of buy and sell orders at fixed price intervals.
    Profits from price oscillations within a defined range.
    
    Features:
    - Dynamic grid adjustment based on volatility
    - Support for both LONG and SHORT positions
    - Pyramid position sizing option
    - Grid trailing in trending markets
    - Multiple risk management layers
    
    Parameters:
        grid_levels: Number of grid levels on each side
        grid_spacing_pct: Percentage spacing between levels
        upper_bound_pct: Upper boundary as % from center
        lower_bound_pct: Lower boundary as % from center
        grid_mode: Trading bias (neutral/long/short/adaptive)
    """
    
    # Grid Configuration
    grid_levels = 10            # Number of levels each side of center
    grid_spacing_pct = 0.5       # 0.5% spacing between grid levels
    upper_bound_pct = 5.0        # 5% above center price
    lower_bound_pct = 5.0        # 5% below center price
    
    # Position Management
    position_per_grid = 0.05     # 5% of capital per grid level
    max_concurrent_positions = 10 # Maximum positions at once
    pyramid_mode = False         # Use pyramid sizing (larger at extremes)
    pyramid_factor = 1.5         # Multiplier for pyramid sizing
    
    # Grid Mode
    grid_mode = GridMode.NEUTRAL  # Default to neutral grid
    trend_period = 50            # Period for trend detection (adaptive mode)
    
    # Risk Management
    stop_loss_pct = 0.08         # 8% stop beyond grid boundaries  
    take_profit_grids = 2        # Take profit after N grid moves
    max_drawdown_pct = 0.15      # Maximum drawdown before stopping
    
    # Grid Adjustment
    rebalance_threshold = 0.10   # Rebalance if price moves 10% from center
    trailing_grid = False        # Move grid with strong trends
    trailing_threshold = 0.03    # 3% move triggers trailing
    
    # Futures Specific
    leverage = 5                # Conservative leverage for grid trading
    reduce_positions_on_trend = True  # Reduce positions in strong trends
    
    # State Management - will be initialized in init()
    
    def init(self):
        """Initialize strategy state - called by backtesting framework"""
        # Initialize state variables
        self.grid_active = False
        self.grid_center = None
        self.buy_levels = []
        self.sell_levels = []
        self.active_positions = {}
        self.completed_trades = []
        self.last_rebalance_time = None
        self.grid_pnl = 0
        self.consecutive_losses = 0
        self.grid_initialized = False
        
        # Call indicator initialization
        self.initialize_indicators()
        
    def initialize_indicators(self):
        """Initialize technical indicators for grid management"""
        # Volatility for dynamic grid spacing
        self.atr = self.I(self._calculate_atr, self.data, 14)
        
        # Trend indicators for adaptive mode
        self.sma_fast = self.I(self.SMA, self.data.Close, 20)
        self.sma_slow = self.I(self.SMA, self.data.Close, self.trend_period)
        
        # RSI for extreme conditions
        self.rsi = self.I(self.RSI, self.data.Close, 14)
        
        # Volume for liquidity assessment
        self.volume_sma = self.I(self.SMA, self.data.Volume, 20)
        
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calculate Average True Range for volatility-based spacing"""
        high = data.High
        low = data.Low
        close = data.Close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.fillna(tr.iloc[0]).values
    
    def _initialize_grid(self, center_price: float):
        """
        Initialize grid levels around center price
        
        Args:
            center_price: The center price for the grid
        """
        self.grid_center = center_price
        self.buy_levels = []
        self.sell_levels = []
        
        # Adjust spacing based on volatility if available
        if len(self.atr) > 0:
            volatility_factor = self.atr[-1] / center_price
            adjusted_spacing = self.grid_spacing_pct * (1 + volatility_factor)
        else:
            adjusted_spacing = self.grid_spacing_pct
        
        # Determine grid bias based on mode
        buy_levels_count = self.grid_levels
        sell_levels_count = self.grid_levels
        
        if self.grid_mode == GridMode.LONG_BIAS:
            buy_levels_count = int(self.grid_levels * 1.5)
            sell_levels_count = int(self.grid_levels * 0.5)
        elif self.grid_mode == GridMode.SHORT_BIAS:
            buy_levels_count = int(self.grid_levels * 0.5)
            sell_levels_count = int(self.grid_levels * 1.5)
        elif self.grid_mode == GridMode.ADAPTIVE:
            # Adjust based on trend
            if len(self.sma_fast) > 0 and len(self.sma_slow) > 0:
                if self.sma_fast[-1] > self.sma_slow[-1]:
                    buy_levels_count = int(self.grid_levels * 1.3)
                    sell_levels_count = int(self.grid_levels * 0.7)
                else:
                    buy_levels_count = int(self.grid_levels * 0.7)
                    sell_levels_count = int(self.grid_levels * 1.3)
        
        # Create buy levels below center
        for i in range(1, buy_levels_count + 1):
            price = center_price * (1 - (adjusted_spacing * i / 100))
            
            # Apply pyramid sizing if enabled
            if self.pyramid_mode:
                size = self.position_per_grid * (1 + (i - 1) * 0.1 * self.pyramid_factor)
            else:
                size = self.position_per_grid
            
            # Don't create levels beyond boundaries
            if price >= center_price * (1 - self.lower_bound_pct / 100):
                self.buy_levels.append(GridLevel(
                    price=price,
                    level_type='BUY',
                    position_size=size
                ))
        
        # Create sell levels above center
        for i in range(1, sell_levels_count + 1):
            price = center_price * (1 + (adjusted_spacing * i / 100))
            
            # Apply pyramid sizing if enabled
            if self.pyramid_mode:
                size = self.position_per_grid * (1 + (i - 1) * 0.1 * self.pyramid_factor)
            else:
                size = self.position_per_grid
            
            # Don't create levels beyond boundaries
            if price <= center_price * (1 + self.upper_bound_pct / 100):
                self.sell_levels.append(GridLevel(
                    price=price,
                    level_type='SELL',
                    position_size=size
                ))
        
        self.grid_active = True
        self.last_rebalance_time = self.data.index[-1] if len(self.data) > 0 else None
        
    def _should_rebalance_grid(self) -> bool:
        """Check if grid needs rebalancing due to price movement"""
        if not self.grid_active or self.grid_center is None:
            return False
        
        current_price = self.data.Close[-1]
        price_change_pct = abs(current_price - self.grid_center) / self.grid_center
        
        # Rebalance if price moved significantly from center
        if price_change_pct > self.rebalance_threshold:
            return True
        
        # Rebalance if most levels on one side are filled
        filled_buys = sum(1 for level in self.buy_levels if level.is_filled)
        filled_sells = sum(1 for level in self.sell_levels if level.is_filled)
        
        if filled_buys > len(self.buy_levels) * 0.8 or filled_sells > len(self.sell_levels) * 0.8:
            return True
        
        return False
    
    def _should_trail_grid(self) -> bool:
        """Check if grid should be trailed in trending market"""
        if not self.trailing_grid or not self.grid_active:
            return False
        
        current_price = self.data.Close[-1]
        
        # Check for strong uptrend
        if current_price > self.grid_center * (1 + self.trailing_threshold):
            if self.sma_fast[-1] > self.sma_slow[-1]:  # Confirm with trend
                return True
        
        # Check for strong downtrend
        if current_price < self.grid_center * (1 - self.trailing_threshold):
            if self.sma_fast[-1] < self.sma_slow[-1]:  # Confirm with trend
                return True
        
        return False
    
    def _get_nearest_unfilled_level(self, current_price: float, 
                                   level_type: str) -> Optional[GridLevel]:
        """
        Find the nearest unfilled grid level
        
        Args:
            current_price: Current market price
            level_type: 'BUY' or 'SELL'
            
        Returns:
            Nearest unfilled GridLevel or None
        """
        if level_type == 'BUY':
            # Find nearest unfilled buy level below current price
            valid_levels = [
                level for level in self.buy_levels 
                if not level.is_filled and level.price < current_price
            ]
            if valid_levels:
                return max(valid_levels, key=lambda x: x.price)
        else:
            # Find nearest unfilled sell level above current price
            valid_levels = [
                level for level in self.sell_levels
                if not level.is_filled and level.price > current_price
            ]
            if valid_levels:
                return min(valid_levels, key=lambda x: x.price)
        
        return None
    
    def _calculate_grid_metrics(self) -> Dict[str, float]:
        """Calculate grid performance metrics"""
        total_levels = len(self.buy_levels) + len(self.sell_levels)
        filled_levels = sum(1 for level in self.buy_levels + self.sell_levels if level.is_filled)
        
        metrics = {
            'fill_rate': filled_levels / total_levels if total_levels > 0 else 0,
            'active_positions': len(self.active_positions),
            'grid_pnl': self.grid_pnl,
            'completed_trades': len(self.completed_trades),
            'avg_trade_profit': np.mean([t['pnl'] for t in self.completed_trades]) if self.completed_trades else 0
        }
        
        return metrics
    
    def should_go_long(self) -> bool:
        """
        Determine if we should open a LONG position at current price
        
        Grid strategy opens LONG when:
        - Price hits a buy grid level
        - Level hasn't been filled yet
        - Risk conditions are met
        """
        if len(self.data) < 2:
            return False
        
        # Initialize grid if not done
        if not self.grid_initialized:
            self._initialize_grid(self.data.Close[-1])
            self.grid_initialized = True
            return False
        
        # Check if we need to rebalance or trail
        if self._should_rebalance_grid():
            self._initialize_grid(self.data.Close[-1])
        elif self._should_trail_grid():
            new_center = self.data.Close[-1]
            self._initialize_grid(new_center)
        
        current_price = self.data.Close[-1]
        
        # Check if we're at a buy level
        for level in self.buy_levels:
            if not level.is_filled:
                # Check if price crossed this level
                price_tolerance = current_price * 0.001  # 0.1% tolerance
                if abs(current_price - level.price) <= price_tolerance:
                    # Check risk conditions
                    if len(self.active_positions) >= self.max_concurrent_positions:
                        return False
                    
                    # Check if market conditions are suitable
                    if self.rsi[-1] < 20:  # Extremely oversold, good for grid entry
                        level.position_size *= 1.2  # Increase size in extreme conditions
                    
                    # Mark level as filled
                    level.is_filled = True
                    level.entry_time = self.data.index[-1]
                    self.active_positions[level.price] = level
                    
                    # Set position size for the trade
                    self.position_size = level.position_size
                    
                    return True
        
        return False
    
    def should_go_short(self) -> bool:
        """
        Determine if we should open a SHORT position at current price
        
        Grid strategy opens SHORT when:
        - Price hits a sell grid level
        - Level hasn't been filled yet
        - Risk conditions are met
        """
        if len(self.data) < 2:
            return False
        
        # Don't initialize grid here as it's done in should_go_long
        if not self.grid_initialized:
            return False
        
        current_price = self.data.Close[-1]
        
        # Check if we're at a sell level
        for level in self.sell_levels:
            if not level.is_filled:
                # Check if price crossed this level
                price_tolerance = current_price * 0.001  # 0.1% tolerance
                if abs(current_price - level.price) <= price_tolerance:
                    # Check risk conditions
                    if len(self.active_positions) >= self.max_concurrent_positions:
                        return False
                    
                    # Check if market conditions are suitable
                    if self.rsi[-1] > 80:  # Extremely overbought, good for short
                        level.position_size *= 1.2  # Increase size in extreme conditions
                    
                    # Mark level as filled
                    level.is_filled = True
                    level.entry_time = self.data.index[-1]
                    self.active_positions[level.price] = level
                    
                    # Set position size for the trade
                    self.position_size = level.position_size
                    
                    return True
        
        return False
    
    def should_close_long(self) -> bool:
        """
        Determine if we should close a LONG position
        
        Close LONG when:
        - Price reaches N grid levels above entry (take profit)
        - Price breaks below grid boundary (stop loss)
        - Grid is being rebalanced
        """
        if len(self.data) < 2:
            return False
        
        current_price = self.data.Close[-1]
        
        # Check each active long position
        for entry_price, level in list(self.active_positions.items()):
            if level.level_type == 'BUY':
                # Calculate profit in grid levels
                price_change_pct = (current_price - entry_price) / entry_price
                grid_moves = price_change_pct / (self.grid_spacing_pct / 100)
                
                # Take profit after N grid moves
                if grid_moves >= self.take_profit_grids:
                    # Record completed trade
                    self.completed_trades.append({
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'pnl': price_change_pct * level.position_size,
                        'type': 'LONG',
                        'duration': self.data.index[-1] - level.entry_time
                    })
                    
                    # Update grid PnL
                    self.grid_pnl += price_change_pct * level.position_size
                    
                    # Remove from active positions
                    del self.active_positions[entry_price]
                    
                    # Reset the level for potential re-entry
                    level.is_filled = False
                    level.position_id = None
                    
                    return True
                
                # Stop loss if price breaks below grid
                if current_price < self.grid_center * (1 - self.lower_bound_pct / 100 - self.stop_loss_pct / 100):
                    del self.active_positions[entry_price]
                    self.consecutive_losses += 1
                    return True
        
        return False
    
    def should_close_short(self) -> bool:
        """
        Determine if we should close a SHORT position
        
        Close SHORT when:
        - Price reaches N grid levels below entry (take profit)
        - Price breaks above grid boundary (stop loss)
        - Grid is being rebalanced
        """
        if len(self.data) < 2:
            return False
        
        current_price = self.data.Close[-1]
        
        # Check each active short position
        for entry_price, level in list(self.active_positions.items()):
            if level.level_type == 'SELL':
                # Calculate profit in grid levels (inverse for shorts)
                price_change_pct = (entry_price - current_price) / entry_price
                grid_moves = price_change_pct / (self.grid_spacing_pct / 100)
                
                # Take profit after N grid moves
                if grid_moves >= self.take_profit_grids:
                    # Record completed trade
                    self.completed_trades.append({
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'pnl': price_change_pct * level.position_size,
                        'type': 'SHORT',
                        'duration': self.data.index[-1] - level.entry_time
                    })
                    
                    # Update grid PnL
                    self.grid_pnl += price_change_pct * level.position_size
                    
                    # Remove from active positions
                    del self.active_positions[entry_price]
                    
                    # Reset the level for potential re-entry
                    level.is_filled = False
                    level.position_id = None
                    
                    return True
                
                # Stop loss if price breaks above grid
                if current_price > self.grid_center * (1 + self.upper_bound_pct / 100 + self.stop_loss_pct / 100):
                    del self.active_positions[entry_price]
                    self.consecutive_losses += 1
                    return True
        
        return False
    
    def get_strategy_metrics(self) -> Dict[str, any]:
        """Return grid-specific metrics for analysis"""
        metrics = self._calculate_grid_metrics()
        
        # Add additional strategy-specific metrics
        metrics.update({
            'grid_center': self.grid_center,
            'total_buy_levels': len(self.buy_levels),
            'total_sell_levels': len(self.sell_levels),
            'consecutive_losses': self.consecutive_losses,
            'grid_mode': self.grid_mode.value
        })
        
        return metrics