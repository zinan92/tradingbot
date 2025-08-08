"""
Simplified ATR Grid Strategy for Backtesting

A working implementation that's compatible with backtesting.py limitations.
"""

import pandas as pd
import numpy as np
from backtesting import Strategy
from backtesting.lib import crossover


class SimpleATRGridStrategy(Strategy):
    """
    Simplified ATR-based Grid Trading Strategy
    
    Uses ATR for dynamic grid spacing and works within
    backtesting.py's single-position limitation.
    """
    
    # Parameters
    atr_multiplier = 0.5      # Grid spacing as ATR multiple  
    grid_levels = 5           # Number of grid levels
    atr_period = 14          # ATR calculation period
    take_profit_atr = 1.0    # Take profit at X ATR
    stop_loss_atr = 2.0      # Stop loss at X ATR
    
    def init(self):
        """Initialize indicators and state"""
        # Calculate ATR
        self.atr = self.I(self._calculate_atr, self.data.df, self.atr_period)
        
        # State tracking
        self.grid_initialized = False
        self.buy_levels = []
        self.sell_levels = []
        self.entry_price = None
        self.grid_center = None
        self.current_atr = None
        
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calculate Average True Range"""
        high = df['High']
        low = df['Low']
        close = df['Close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        
        return atr.fillna(tr.iloc[0]).values
    
    def next(self):
        """Execute strategy logic on each bar"""
        current_price = self.data.Close[-1]
        current_atr = self.atr[-1] if len(self.atr) > 0 else 0
        
        # Skip if no ATR
        if current_atr == 0 or pd.isna(current_atr):
            return
        
        self.current_atr = current_atr
        
        # Initialize or update grid
        if not self.grid_initialized or self._should_recalculate_grid(current_price):
            self._setup_grid(current_price, current_atr)
        
        # Trading logic
        if not self.position:
            # Look for entry
            self._check_grid_entry(current_price)
        else:
            # Manage position
            self._manage_position(current_price)
    
    def _setup_grid(self, center_price: float, atr: float):
        """Setup grid levels around center price"""
        self.grid_center = center_price
        self.buy_levels = []
        self.sell_levels = []
        
        grid_spacing = atr * self.atr_multiplier
        
        # Create grid levels
        for i in range(1, self.grid_levels + 1):
            buy_price = center_price - (grid_spacing * i)
            sell_price = center_price + (grid_spacing * i)
            self.buy_levels.append(buy_price)
            self.sell_levels.append(sell_price)
        
        self.grid_initialized = True
    
    def _should_recalculate_grid(self, current_price: float) -> bool:
        """Check if grid needs recalculation"""
        if not self.grid_center or not self.current_atr:
            return True
        
        # Recalculate if price moved significantly
        price_move = abs(current_price - self.grid_center)
        threshold = self.current_atr * 2
        
        return price_move > threshold
    
    def _check_grid_entry(self, current_price: float):
        """Check for grid entry signals"""
        # Check buy levels
        for buy_level in self.buy_levels:
            if current_price <= buy_level:
                self.buy()
                self.entry_price = current_price
                return
        
        # Check sell levels (for short positions if allowed)
        # Note: backtesting.py needs margin < 1 for shorting
        for sell_level in self.sell_levels:
            if current_price >= sell_level:
                self.sell()  # Short position
                self.entry_price = current_price
                return
    
    def _manage_position(self, current_price: float):
        """Manage existing position"""
        if not self.entry_price:
            self.entry_price = self.position.open_price
        
        # Calculate P&L distance
        if self.position.is_long:
            pnl_distance = current_price - self.entry_price
            
            # Take profit
            if pnl_distance >= self.current_atr * self.take_profit_atr:
                self.position.close()
                self.entry_price = None
                return
            
            # Stop loss
            if pnl_distance <= -self.current_atr * self.stop_loss_atr:
                self.position.close()
                self.entry_price = None
                return
            
            # Grid exit - close at next sell level
            for sell_level in self.sell_levels:
                if current_price >= sell_level:
                    self.position.close()
                    self.entry_price = None
                    return
        
        else:  # Short position
            pnl_distance = self.entry_price - current_price
            
            # Take profit
            if pnl_distance >= self.current_atr * self.take_profit_atr:
                self.position.close()
                self.entry_price = None
                return
            
            # Stop loss
            if pnl_distance <= -self.current_atr * self.stop_loss_atr:
                self.position.close()
                self.entry_price = None
                return
            
            # Grid exit - close at next buy level
            for buy_level in self.buy_levels:
                if current_price <= buy_level:
                    self.position.close()
                    self.entry_price = None
                    return