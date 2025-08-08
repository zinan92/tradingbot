"""
Optimal Grid Strategy with Midpoint-Based Trading Rules

This strategy implements a grid trading system where:
- Daily range is defined by 1-day ATR(14)
- Default regime is NEUTRAL (bidirectional)
- Buys only occur below midpoint
- Sells only occur above midpoint
- 5 grid levels on each side of midpoint
"""

import pandas as pd
import numpy as np
from backtesting import Strategy
from backtesting.lib import crossover


class OptimalGridStrategy(Strategy):
    """
    Optimal Grid Trading Strategy with Midpoint Rules
    
    In NEUTRAL mode (default for backtesting):
    - Buy when price < midpoint (5 levels down)
    - Sell when price > midpoint (5 levels up)
    """
    
    # Parameters
    atr_period = 14          # ATR calculation period (14 days)
    grid_levels = 5          # Number of grid levels per side
    atr_range_multiplier = 1.0  # Range = multiplier × daily ATR
    
    # Position management
    take_profit_pct = 0.02   # Take profit at 2% move
    stop_loss_pct = 0.05     # Stop loss at 5% move
    
    def init(self):
        """Initialize indicators and state"""
        # Calculate daily ATR from hourly data
        self.daily_atr = self.I(self._calculate_daily_atr, self.data.df, self.atr_period)
        
        # State tracking
        self.range_upper = None
        self.range_lower = None
        self.midpoint = None
        self.buy_levels = []
        self.sell_levels = []
        self.last_update_day = None
        self.entry_price = None
        
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
        
        # Map daily ATR back to hourly timeframe
        result = np.zeros(len(df))
        daily_atr_dict = {date.date(): atr_value for date, atr_value in daily_atr.items()}
        
        for i, timestamp in enumerate(df.index):
            date_key = timestamp.date()
            if date_key in daily_atr_dict:
                result[i] = daily_atr_dict[date_key]
            else:
                # Use previous day's ATR if available
                prev_date = date_key - pd.Timedelta(days=1)
                if prev_date in daily_atr_dict:
                    result[i] = daily_atr_dict[prev_date]
        
        return result
    
    def _update_daily_range(self, current_price: float, current_atr: float):
        """Update daily range and grid levels"""
        # Calculate range based on ATR
        half_range = (current_atr * self.atr_range_multiplier) / 2
        
        # Set range bounds with current price as midpoint
        self.midpoint = current_price
        self.range_upper = current_price + half_range
        self.range_lower = current_price - half_range
        
        # Clear previous grid levels
        self.buy_levels = []
        self.sell_levels = []
        
        # Calculate grid spacing
        buy_spacing = (self.midpoint - self.range_lower) / self.grid_levels
        sell_spacing = (self.range_upper - self.midpoint) / self.grid_levels
        
        # Create buy levels (below midpoint)
        for i in range(1, self.grid_levels + 1):
            buy_price = self.midpoint - (buy_spacing * i)
            self.buy_levels.append(buy_price)
        
        # Create sell levels (above midpoint)
        for i in range(1, self.grid_levels + 1):
            sell_price = self.midpoint + (sell_spacing * i)
            self.sell_levels.append(sell_price)
    
    def next(self):
        """Execute strategy logic on each bar"""
        current_price = self.data.Close[-1]
        current_atr = self.daily_atr[-1] if len(self.daily_atr) > 0 else 0
        
        # Skip if no ATR
        if current_atr == 0 or pd.isna(current_atr):
            return
        
        # Get current date
        current_day = self.data.index[-1].date()
        
        # Update range at start of each day
        if self.last_update_day != current_day:
            self._update_daily_range(current_price, current_atr)
            self.last_update_day = current_day
        
        # Skip if range not initialized
        if self.midpoint is None:
            return
        
        # Trading logic
        if not self.position:
            self._check_entry_signals(current_price)
        else:
            self._manage_position(current_price)
    
    def _check_entry_signals(self, current_price: float):
        """Check for grid entry signals (NEUTRAL regime)"""
        
        # NEUTRAL REGIME: Can both buy and sell based on midpoint
        
        # Check BUY signals (only below midpoint)
        if current_price < self.midpoint:
            # Find the appropriate buy level
            for buy_level in self.buy_levels:
                if current_price <= buy_level:
                    # Buy at this grid level
                    self.buy()
                    self.entry_price = current_price
                    return
        
        # Check SELL signals (only above midpoint)
        elif current_price > self.midpoint:
            # Find the appropriate sell level
            for sell_level in self.sell_levels:
                if current_price >= sell_level:
                    # Sell (short) at this grid level
                    self.sell()
                    self.entry_price = current_price
                    return
    
    def _manage_position(self, current_price: float):
        """Manage existing position"""
        if not self.entry_price:
            self.entry_price = self.position.open_price
        
        if self.position.is_long:
            # Long position management
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            
            # Take profit
            if pnl_pct >= self.take_profit_pct:
                self.position.close()
                self.entry_price = None
                return
            
            # Stop loss
            if pnl_pct <= -self.stop_loss_pct:
                self.position.close()
                self.entry_price = None
                return
            
            # Grid exit - close if price crosses above midpoint significantly
            if current_price > self.midpoint * 1.01:  # 1% above midpoint
                self.position.close()
                self.entry_price = None
                return
        
        else:  # Short position
            # Short position management
            pnl_pct = (self.entry_price - current_price) / self.entry_price
            
            # Take profit
            if pnl_pct >= self.take_profit_pct:
                self.position.close()
                self.entry_price = None
                return
            
            # Stop loss
            if pnl_pct <= -self.stop_loss_pct:
                self.position.close()
                self.entry_price = None
                return
            
            # Grid exit - close if price crosses below midpoint significantly
            if current_price < self.midpoint * 0.99:  # 1% below midpoint
                self.position.close()
                self.entry_price = None
                return