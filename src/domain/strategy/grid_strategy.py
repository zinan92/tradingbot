"""
Grid Trading Strategy Implementation

Implements ATR-based grid trading strategy as defined in PRD Stories 3.1-3.4:
- ATR-based grid spacing
- Multiple grid levels around reference price
- Risk management (max position size, stop-loss)
- Human regime input integration (Story 2.1)
"""

import pandas as pd
from typing import Dict, Any
from backtesting import Strategy

from src.config.config_loader import get_config
from src.data.core.indicators import IndicatorCalculator
from src.strategy.regime import RegimeManager, MarketRegime, GridMode


class GridTradingStrategy(Strategy):
    """
    ATR-based grid trading strategy for crypto markets.
    
    This strategy implements:
    - Dynamic grid spacing based on ATR
    - Multiple buy/sell levels around current price
    - Risk management with position sizing
    - Market regime awareness (bull/bear/range)
    """
    
    # Strategy parameters (can be optimized)
    atr_multiplier = 0.75      # Grid spacing = ATR * multiplier (Story 3.1)
    grid_levels = 5            # Number of levels each side (Story 3.2)
    max_position_size = 0.1    # Max 10% of capital per position (Story 3.4)
    
    def init(self):
        """
        Initialize strategy indicators and grid parameters.
        """
        # Get configuration
        self.config = get_config()
        
        # Initialize regime manager (Story 2.1)
        self.regime_manager = RegimeManager()
        
        # Initialize indicator calculator
        self.indicator_calc = IndicatorCalculator()
        
        # Calculate ATR for grid spacing
        # Convert backtesting.py format (uppercase) to our format (lowercase)
        df_for_atr = self.data.df.copy()
        df_for_atr.columns = df_for_atr.columns.str.lower()
        
        df_with_atr = self.indicator_calc.calculate_atr(
            df_for_atr, 
            period=14, 
            method='rma'
        )
        self.atr = self.I(lambda: df_with_atr['ATR_14'].values)
        
        # Grid tracking
        self.grid_levels_buy = []
        self.grid_levels_sell = []
        self.last_grid_price = None
        self.position_count = 0
        
        # Risk management
        self.max_total_position = self.max_position_size * len(self.data)
        
    def calculate_grid_levels(self, reference_price: float, atr_value: float) -> tuple:
        """
        Calculate buy and sell grid levels around reference price.
        
        Args:
            reference_price: Current or reference price for grid center
            atr_value: Current ATR value for spacing calculation
            
        Returns:
            Tuple of (buy_levels, sell_levels) as lists of prices
        """
        # Calculate grid spacing (Story 3.1)
        grid_spacing = atr_value * self.atr_multiplier
        
        buy_levels = []
        sell_levels = []
        
        # Generate grid levels (Story 3.2)
        for i in range(1, self.grid_levels + 1):
            # Buy levels below current price
            buy_price = reference_price - (grid_spacing * i)
            buy_levels.append(buy_price)
            
            # Sell levels above current price
            sell_price = reference_price + (grid_spacing * i) 
            sell_levels.append(sell_price)
        
        return buy_levels, sell_levels
    
    def should_activate_grid(self, atr_value: float) -> bool:
        """
        Determine if grid should be activated based on regime and volatility.
        
        Args:
            atr_value: Current ATR value
            
        Returns:
            Boolean indicating if grid should be active
        """
        # Get current regime from manager (Story 2.1)
        current_regime = self.regime_manager.get_current_regime()
        grid_mode = self.regime_manager.get_current_grid_mode()
        
        # Skip if grid is disabled (none regime)
        if grid_mode == GridMode.DISABLED:
            return False
            
        # Skip if volatility is too extreme (Story 1.4 concept)
        # This is a simple implementation - can be enhanced
        recent_atr = pd.Series(self.atr[-20:] if len(self.atr) >= 20 else self.atr)
        atr_percentile_75 = recent_atr.quantile(0.75)
        atr_percentile_25 = recent_atr.quantile(0.25)
        
        # Skip if volatility is too high or too low
        if atr_value > atr_percentile_75 * 1.5 or atr_value < atr_percentile_25 * 0.5:
            return False
            
        return True
    
    def get_position_size(self) -> float:
        """
        Calculate position size based on risk management rules.
        
        Returns:
            Position size as fraction of equity
        """
        # Simple equal-weight position sizing
        # Can be enhanced with volatility-based sizing
        base_size = self.max_position_size / self.grid_levels
        
        # Reduce size if we have multiple positions
        size_adjustment = max(0.5, 1.0 - (self.position_count * 0.1))
        
        return base_size * size_adjustment
    
    def next(self):
        """
        Main strategy logic executed on each bar.
        """
        # Get current values
        current_price = self.data.Close[-1]
        current_atr = self.atr[-1] if len(self.atr) > 0 else 0
        
        # Skip if ATR not available yet
        if current_atr == 0 or pd.isna(current_atr):
            return
            
        # Check if we should activate grid
        if not self.should_activate_grid(current_atr):
            return
            
        # Update grid levels if price has moved significantly or first time
        if (self.last_grid_price is None or 
            abs(current_price - self.last_grid_price) > current_atr * 0.5):
            
            self.grid_levels_buy, self.grid_levels_sell = self.calculate_grid_levels(
                current_price, current_atr
            )
            self.last_grid_price = current_price
        
        # Grid trading logic based on regime (Story 2.1)
        grid_mode = self.regime_manager.get_current_grid_mode()
        
        # Execute buy grid for long-only and bidirectional modes
        if grid_mode in [GridMode.LONG_ONLY, GridMode.BIDIRECTIONAL]:
            self._execute_buy_grid(current_price)
            
        # Execute sell grid for short-only and bidirectional modes  
        if grid_mode in [GridMode.SHORT_ONLY, GridMode.BIDIRECTIONAL]:
            self._execute_sell_grid(current_price)
            
        # Risk management - close positions if needed
        self._manage_risk(current_price, current_atr)
    
    def _execute_buy_grid(self, current_price: float):
        """Execute buy orders at grid levels."""
        if self.position.size >= 0:  # Only buy if not short
            for buy_level in self.grid_levels_buy:
                if current_price <= buy_level and not self.position.is_long:
                    size = self.get_position_size()
                    if size > 0:
                        self.buy(size=size)
                        self.position_count += 1
                        break
    
    def _execute_sell_grid(self, current_price: float):
        """Execute sell orders at grid levels."""
        if self.position.size <= 0:  # Only sell if not long
            for sell_level in self.grid_levels_sell:
                if current_price >= sell_level and not self.position.is_short:
                    size = self.get_position_size()
                    if size > 0:
                        self.sell(size=size)
                        self.position_count += 1
                        break
    
    def _manage_risk(self, current_price: float, current_atr: float):
        """
        Risk management logic including stop-loss and position limits.
        """
        # Simple stop-loss based on ATR
        stop_loss_distance = current_atr * 2.0
        
        if self.position.is_long:
            stop_price = current_price - stop_loss_distance
            if current_price <= stop_price:
                self.position.close()
                self.position_count = max(0, self.position_count - 1)
                
        elif self.position.is_short:
            stop_price = current_price + stop_loss_distance
            if current_price >= stop_price:
                self.position.close()
                self.position_count = max(0, self.position_count - 1)
        
        # Position size limit (Story 3.4)
        if abs(self.position.size) > self.max_total_position:
            self.position.close()
            self.position_count = 0