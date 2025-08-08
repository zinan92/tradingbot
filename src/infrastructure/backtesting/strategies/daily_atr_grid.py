"""
Daily ATR Grid Strategy for Backtesting

Uses 1-day ATR for wider grid spacing to avoid rapid position accumulation
in trending markets. All other specifications remain the same.
"""

import pandas as pd
import numpy as np
from backtesting import Strategy
from backtesting.lib import crossover


class DailyATRGridStrategy(Strategy):
    """
    Daily ATR-based Grid Trading Strategy
    
    Uses 1-day ATR for dynamic grid spacing to create wider grids
    that don't trigger all levels in minor price movements.
    """
    
    # Parameters (keeping same as original except ATR source)
    atr_multiplier = 0.5      # Grid spacing as ATR multiple  
    grid_levels = 5           # Number of grid levels
    atr_period = 14          # ATR calculation period (14 days)
    take_profit_atr = 1.0    # Take profit at X ATR
    stop_loss_atr = 2.0      # Stop loss at X ATR
    
    def init(self):
        """Initialize indicators and state"""
        # Calculate daily ATR from hourly data
        # We'll resample to daily and calculate ATR
        self.daily_atr = self.I(self._calculate_daily_atr, self.data.df, self.atr_period)
        
        # State tracking
        self.grid_initialized = False
        self.buy_levels = []
        self.sell_levels = []
        self.entry_price = None
        self.grid_center = None
        self.current_atr = None
        
    def _calculate_daily_atr(self, df: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calculate Average True Range using daily timeframe"""
        # Create a copy with datetime index
        df_copy = df.copy()
        
        # Resample to daily timeframe
        daily_df = df_copy.resample('1D').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        
        if len(daily_df) < 2:
            # Not enough data for daily ATR, return zeros
            return np.zeros(len(df))
        
        # Calculate True Range on daily data
        high = daily_df['High']
        low = daily_df['Low']
        close = daily_df['Close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        daily_atr = tr.ewm(alpha=1/period, adjust=False).mean()
        
        # Fill first value if NaN
        daily_atr = daily_atr.fillna(tr.iloc[0] if len(tr) > 0 else 0)
        
        # Now we need to expand daily ATR back to hourly timeframe
        # Create a mapping from date to ATR value
        daily_atr_dict = {}
        for date, atr_value in daily_atr.items():
            daily_atr_dict[date.date()] = atr_value
        
        # Apply daily ATR to each hour
        result = np.zeros(len(df))
        for i, timestamp in enumerate(df.index):
            date_key = timestamp.date()
            if date_key in daily_atr_dict:
                result[i] = daily_atr_dict[date_key]
            else:
                # Use previous day's ATR if available
                prev_date = date_key - pd.Timedelta(days=1)
                while prev_date not in daily_atr_dict and prev_date > (date_key - pd.Timedelta(days=7)):
                    prev_date -= pd.Timedelta(days=1)
                if prev_date in daily_atr_dict:
                    result[i] = daily_atr_dict[prev_date]
        
        return result
    
    def next(self):
        """Execute strategy logic on each bar"""
        current_price = self.data.Close[-1]
        current_atr = self.daily_atr[-1] if len(self.daily_atr) > 0 else 0
        
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
        
        # Recalculate if price moved significantly (2x daily ATR)
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
        for sell_level in self.sell_levels:
            if current_price >= sell_level:
                self.sell()  # Short position
                self.entry_price = current_price
                return
    
    def _manage_position(self, current_price: float):
        """Manage existing position"""
        if not self.entry_price:
            self.entry_price = self.position.open_price
        
        # Calculate P&L distance using daily ATR
        if self.position.is_long:
            pnl_distance = current_price - self.entry_price
            
            # Take profit (1x daily ATR)
            if pnl_distance >= self.current_atr * self.take_profit_atr:
                self.position.close()
                self.entry_price = None
                return
            
            # Stop loss (2x daily ATR)
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