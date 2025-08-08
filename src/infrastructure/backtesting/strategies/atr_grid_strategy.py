"""
ATR-Based Grid Strategy for Backtesting

Adapter that integrates the domain grid strategy with backtesting.py framework.
Uses your existing grid strategy logic with ATR-based spacing and regime awareness.
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from backtesting import Strategy
from backtesting.lib import crossover

from src.domain.strategy.aggregates.grid_strategy_aggregate import (
    GridStrategyAggregate,
    GridConfiguration,
    GridState
)
from src.domain.strategy.regime.regime_manager import RegimeManager
from src.domain.strategy.regime.regime_models import MarketRegime, GridMode
from src.domain.trading.value_objects.symbol import Symbol


class ATRGridStrategy(Strategy):
    """
    ATR-based Grid Trading Strategy for backtesting.
    
    Adapts the domain grid strategy aggregate for use with backtesting.py.
    Features:
    - Dynamic ATR-based grid spacing
    - Market regime awareness (bull/bear/range)
    - Configurable grid levels and risk management
    - Position tracking and PnL calculation
    """
    
    # Strategy parameters (can be optimized)
    atr_multiplier = 0.75      # Grid spacing = ATR * multiplier
    grid_levels = 5            # Number of levels each side
    max_position_size = 0.1    # Max 10% of capital per position
    stop_loss_atr_mult = 2.0   # Stop loss at 2x ATR
    recalc_threshold = 0.5     # Recalculate grid if price moves > 0.5 ATR
    
    # Regime parameters
    use_regime = True          # Enable regime-based trading
    initial_regime = "range"   # Initial market regime
    
    # ATR parameters
    atr_period = 14           # ATR calculation period
    
    def init(self):
        """Initialize strategy indicators and grid."""
        # Calculate ATR
        self.atr = self.I(self._calculate_atr, self.data.df, self.atr_period)
        
        # Initialize regime manager
        self.regime_manager = RegimeManager()
        
        # Set initial regime
        initial_regime = MarketRegime.from_string(self.initial_regime)
        self.regime_manager.update_regime(initial_regime)
        
        # Create grid configuration
        self.grid_config = GridConfiguration(
            atr_multiplier=self.atr_multiplier,
            grid_levels=self.grid_levels,
            max_position_size=self.max_position_size,
            stop_loss_atr_multiplier=self.stop_loss_atr_mult,
            recalculation_threshold=self.recalc_threshold
        )
        
        # Initialize grid strategy aggregate
        self.grid_strategy = GridStrategyAggregate(
            strategy_id="backtest_grid",
            symbol=Symbol("BTCUSDT"),  # Default symbol
            config=self.grid_config,
            initial_regime=initial_regime
        )
        
        # Track ATR history for volatility filtering
        self.atr_history = []
        
        # Track grid positions for backtesting
        self.grid_positions = {}
        self.next_position_id = 1
        
        # Performance tracking
        self.grid_trades = []
        self.total_grid_pnl = 0
        
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> np.ndarray:
        """
        Calculate Average True Range.
        
        Args:
            df: OHLC DataFrame
            period: ATR period
            
        Returns:
            ATR values as numpy array
        """
        high = df['High']
        low = df['Low']
        close = df['Close'].shift(1)
        
        # Calculate true range
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR using RMA (exponential moving average)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        
        return atr.fillna(tr.iloc[0]).values
    
    def next(self):
        """Execute strategy logic on each bar."""
        # Get current values
        current_price = self.data.Close[-1]
        current_atr = self.atr[-1] if len(self.atr) > 0 else 0
        
        # Skip if ATR not available
        if current_atr == 0 or pd.isna(current_atr):
            return
        
        # Update ATR history
        self.atr_history.append(current_atr)
        if len(self.atr_history) > 100:
            self.atr_history = self.atr_history[-100:]
        
        # Check if grid should be active
        if not self.grid_strategy.should_activate_grid(current_atr, self.atr_history):
            return
        
        # Update grid if needed
        self.grid_strategy.update_grid(current_price, current_atr)
        
        # Execute grid trading logic
        self._execute_grid_trading(current_price, current_atr)
        
        # Check stop losses
        self._check_stop_losses(current_price)
        
        # Process any events (for logging/analysis)
        events = self.grid_strategy.clear_events()
        for event in events:
            self._log_event(event)
    
    def _execute_grid_trading(self, current_price: float, current_atr: float):
        """Execute grid trading logic."""
        # Check for buy signals
        buy_level = self.grid_strategy.check_buy_signal(current_price)
        if buy_level:  # Removed position check - grid trading allows multiple positions
            # Calculate position size
            size = self.grid_strategy.calculate_position_size()
            
            if size > 0:
                # Place buy order in backtesting framework
                self.buy(size=size)
                
                # Track in grid strategy
                position_id = f"pos_{self.next_position_id}"
                self.next_position_id += 1
                
                self.grid_strategy.record_position_opened(
                    position_id=position_id,
                    grid_level=buy_level,
                    size=size
                )
                
                # Track for backtesting
                self.grid_positions[position_id] = {
                    'entry_price': buy_level.price,
                    'size': size,
                    'side': 'LONG',
                    'entry_time': len(self.data)
                }
        
        # Check for sell signals (if short selling is allowed)
        sell_level = self.grid_strategy.check_sell_signal(current_price)
        if sell_level:  # Removed position check for grid trading
            # Calculate position size
            size = self.grid_strategy.calculate_position_size()
            
            if size > 0:
                # Place sell order in backtesting framework
                self.sell(size=size)
                
                # Track in grid strategy
                position_id = f"pos_{self.next_position_id}"
                self.next_position_id += 1
                
                self.grid_strategy.record_position_opened(
                    position_id=position_id,
                    grid_level=sell_level,
                    size=size
                )
                
                # Track for backtesting
                self.grid_positions[position_id] = {
                    'entry_price': sell_level.price,
                    'size': size,
                    'side': 'SHORT',
                    'entry_time': len(self.data)
                }
    
    def _check_stop_losses(self, current_price: float):
        """Check and execute stop losses."""
        if not self.position:
            return
        
        # Check each grid position for stop loss
        positions_to_close = []
        
        for position_id, position_data in self.grid_positions.items():
            entry_price = position_data['entry_price']
            position_side = position_data['side']
            
            # Check if stop loss triggered
            if self.grid_strategy.check_stop_loss(current_price, entry_price, position_side):
                positions_to_close.append(position_id)
        
        # Close positions that hit stop loss
        for position_id in positions_to_close:
            self.position.close()
            
            # Calculate PnL
            position_data = self.grid_positions[position_id]
            entry_price = position_data['entry_price']
            exit_price = current_price
            size = position_data['size']
            
            if position_data['side'] == 'LONG':
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size
            
            # Record in grid strategy
            self.grid_strategy.record_position_closed(
                position_id=position_id,
                exit_price=exit_price,
                pnl=pnl
            )
            
            # Track trade
            self.grid_trades.append({
                'entry_price': entry_price,
                'exit_price': exit_price,
                'side': position_data['side'],
                'pnl': pnl,
                'duration': len(self.data) - position_data['entry_time']
            })
            
            self.total_grid_pnl += pnl
            
            # Remove from tracking
            del self.grid_positions[position_id]
    
    def _log_event(self, event: Dict[str, Any]):
        """Log strategy events for analysis."""
        # This can be extended to save events for post-backtest analysis
        pass
    
    def get_grid_metrics(self) -> Dict[str, Any]:
        """Get grid-specific metrics for analysis."""
        return {
            'total_trades': len(self.grid_trades),
            'total_pnl': self.total_grid_pnl,
            'active_positions': len(self.grid_positions),
            'grid_state': self.grid_strategy.state.value,
            'regime': self.grid_strategy.market_regime.value,
            'grid_mode': self.grid_strategy.grid_mode.value,
            'buy_levels': len(self.grid_strategy.buy_levels),
            'sell_levels': len(self.grid_strategy.sell_levels)
        }


class OptimizedATRGridStrategy(ATRGridStrategy):
    """
    Optimized version with additional features.
    
    Adds:
    - Volume confirmation
    - Trend filtering
    - Dynamic position sizing
    """
    
    # Additional parameters
    use_volume_filter = True
    volume_threshold = 1.5    # Volume must be 1.5x average
    use_trend_filter = True
    trend_period = 50         # SMA period for trend
    
    def init(self):
        """Initialize with additional indicators."""
        super().init()
        
        # Add volume SMA
        if self.use_volume_filter:
            self.volume_sma = self.I(
                lambda: self.data.Volume.rolling(20).mean().values
            )
        
        # Add trend SMA
        if self.use_trend_filter:
            self.trend_sma = self.I(
                lambda: self.data.Close.rolling(self.trend_period).mean().values
            )
    
    def _execute_grid_trading(self, current_price: float, current_atr: float):
        """Execute grid trading with additional filters."""
        # Check volume filter
        if self.use_volume_filter:
            current_volume = self.data.Volume[-1]
            avg_volume = self.volume_sma[-1] if len(self.volume_sma) > 0 else current_volume
            
            if current_volume < avg_volume * self.volume_threshold:
                return  # Skip if volume too low
        
        # Check trend filter
        if self.use_trend_filter and len(self.trend_sma) > 0:
            trend_sma_value = self.trend_sma[-1]
            
            # Adjust grid mode based on trend
            if current_price > trend_sma_value * 1.02:  # Strong uptrend
                # Temporarily switch to LONG_ONLY
                original_mode = self.grid_strategy.grid_mode
                self.grid_strategy.grid_mode = GridMode.LONG_ONLY
                super()._execute_grid_trading(current_price, current_atr)
                self.grid_strategy.grid_mode = original_mode
            elif current_price < trend_sma_value * 0.98:  # Strong downtrend
                # Temporarily switch to SHORT_ONLY
                original_mode = self.grid_strategy.grid_mode
                self.grid_strategy.grid_mode = GridMode.SHORT_ONLY
                super()._execute_grid_trading(current_price, current_atr)
                self.grid_strategy.grid_mode = original_mode
            else:
                # Normal grid execution
                super()._execute_grid_trading(current_price, current_atr)
        else:
            super()._execute_grid_trading(current_price, current_atr)