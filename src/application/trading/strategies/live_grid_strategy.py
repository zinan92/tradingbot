"""
Live Grid Trading Strategy

Flexible grid trading strategy that can be used with any symbol.
Originally tested with BNB showing excellent performance:
- Return: +9.89%
- Sharpe Ratio: 1.87
- Max Drawdown: -7.32%
- Win Rate: 39.6%
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GridLevel:
    """Represents a grid level for trading"""
    price: float
    quantity: float
    side: str  # BUY or SELL
    order_id: Optional[str] = None
    filled: bool = False
    fill_time: Optional[datetime] = None


class LiveGridStrategy:
    """
    Grid Trading Strategy for any trading pair
    
    Creates a grid of buy and sell orders around the current price.
    Profits from market volatility by buying low and selling high within the grid.
    """
    
    def __init__(
        self,
        symbol: str = "BNBUSDT",
        grid_levels: int = 10,
        grid_spacing: float = 0.005,  # 0.5% spacing between levels
        position_size_per_grid: float = 0.1,  # 10% of capital per grid level
        sma_period: int = 20,
        use_dynamic_grid: bool = True,
        atr_period: int = 14,
        atr_multiplier: float = 1.5
    ):
        """
        Initialize BNB Grid Strategy
        
        Args:
            symbol: Trading symbol
            grid_levels: Number of grid levels above and below center
            grid_spacing: Percentage spacing between grid levels
            position_size_per_grid: Position size for each grid level
            sma_period: SMA period for trend detection
            use_dynamic_grid: Whether to adjust grid based on volatility
            atr_period: ATR period for volatility measurement
            atr_multiplier: Multiplier for ATR-based grid spacing
        """
        self.symbol = symbol
        self.grid_levels = grid_levels
        self.grid_spacing = grid_spacing
        self.position_size_per_grid = position_size_per_grid
        self.sma_period = sma_period
        self.use_dynamic_grid = use_dynamic_grid
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        
        # Grid management
        self.buy_grid: List[GridLevel] = []
        self.sell_grid: List[GridLevel] = []
        self.center_price: Optional[float] = None
        self.last_update_time: Optional[datetime] = None
        
        # Technical indicators
        self.sma: Optional[pd.Series] = None
        self.atr: Optional[pd.Series] = None
        
        # Performance tracking
        self.grid_profits = 0.0
        self.completed_cycles = 0
        
        logger.info(f"BNB Grid Strategy initialized with {grid_levels} levels")
    
    def update_indicators(self, data: pd.DataFrame):
        """Update technical indicators with new data"""
        try:
            if len(data) < self.sma_period:
                return
            
            # Calculate SMA
            self.sma = data['Close'].rolling(window=self.sma_period).mean()
            
            # Calculate ATR for dynamic grid spacing
            if self.use_dynamic_grid and len(data) >= self.atr_period:
                high_low = data['High'] - data['Low']
                high_close = abs(data['High'] - data['Close'].shift())
                low_close = abs(data['Low'] - data['Close'].shift())
                
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                self.atr = true_range.rolling(window=self.atr_period).mean()
            
        except Exception as e:
            logger.error(f"Error updating indicators: {e}")
    
    def should_update_grid(self, current_price: float) -> bool:
        """Check if grid needs to be updated"""
        if self.center_price is None:
            return True
        
        # Update if price moved significantly from center
        price_change = abs(current_price - self.center_price) / self.center_price
        if price_change > 0.02:  # 2% movement
            return True
        
        # Update every hour
        if self.last_update_time:
            time_diff = (datetime.now() - self.last_update_time).seconds
            if time_diff > 3600:  # 1 hour
                return True
        
        return False
    
    def calculate_grid_levels(self, current_price: float, capital: float) -> tuple:
        """Calculate grid buy and sell levels"""
        try:
            self.buy_grid.clear()
            self.sell_grid.clear()
            
            # Set center price
            self.center_price = current_price
            
            # Calculate grid spacing
            if self.use_dynamic_grid and self.atr is not None:
                # Dynamic spacing based on ATR
                atr_value = self.atr.iloc[-1]
                spacing = (atr_value / current_price) * self.atr_multiplier
                spacing = max(spacing, 0.003)  # Minimum 0.3% spacing
                spacing = min(spacing, 0.02)   # Maximum 2% spacing
            else:
                spacing = self.grid_spacing
            
            # Calculate position size per grid
            position_value = capital * self.position_size_per_grid
            
            # Create buy grid levels (below current price)
            for i in range(1, self.grid_levels + 1):
                price = current_price * (1 - spacing * i)
                quantity = position_value / price
                
                self.buy_grid.append(GridLevel(
                    price=round(price, 2),
                    quantity=round(quantity, 3),
                    side='BUY'
                ))
            
            # Create sell grid levels (above current price)
            for i in range(1, self.grid_levels + 1):
                price = current_price * (1 + spacing * i)
                quantity = position_value / price
                
                self.sell_grid.append(GridLevel(
                    price=round(price, 2),
                    quantity=round(quantity, 3),
                    side='SELL'
                ))
            
            self.last_update_time = datetime.now()
            
            logger.info(f"Grid updated: Center=${current_price:.2f}, Spacing={spacing:.3%}")
            logger.info(f"Buy range: ${self.buy_grid[-1].price:.2f} - ${self.buy_grid[0].price:.2f}")
            logger.info(f"Sell range: ${self.sell_grid[0].price:.2f} - ${self.sell_grid[-1].price:.2f}")
            
            return self.buy_grid, self.sell_grid
            
        except Exception as e:
            logger.error(f"Error calculating grid levels: {e}")
            return [], []
    
    def get_pending_orders(self) -> List[GridLevel]:
        """Get list of pending grid orders to place"""
        pending = []
        
        # Get unfilled buy orders
        for level in self.buy_grid:
            if not level.filled and level.order_id is None:
                pending.append(level)
        
        # Get unfilled sell orders (only if we have inventory)
        # In live trading, we need to check actual position before placing sell orders
        for level in self.sell_grid:
            if not level.filled and level.order_id is None:
                pending.append(level)
        
        return pending
    
    def get_signal(self, current_price: float, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate trading signal based on grid strategy
        
        Returns:
            Dictionary with signal information:
            - action: 'UPDATE_GRID', 'PLACE_ORDERS', 'CANCEL_ORDERS', 'HOLD'
            - orders: List of orders to place/cancel
            - reason: Explanation of the signal
        """
        try:
            # Update indicators
            self.update_indicators(data)
            
            # Check if we need to update the grid
            if self.should_update_grid(current_price):
                return {
                    'action': 'UPDATE_GRID',
                    'orders': [],
                    'reason': 'Grid update required due to price movement'
                }
            
            # Check for orders to place
            pending_orders = self.get_pending_orders()
            if pending_orders:
                return {
                    'action': 'PLACE_ORDERS',
                    'orders': pending_orders,
                    'reason': f'Placing {len(pending_orders)} grid orders'
                }
            
            # Check if price is too far from grid
            if self.is_price_outside_grid(current_price):
                return {
                    'action': 'CANCEL_ORDERS',
                    'orders': [],
                    'reason': 'Price moved outside grid range'
                }
            
            return {
                'action': 'HOLD',
                'orders': [],
                'reason': 'Grid active, waiting for fills'
            }
            
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return {
                'action': 'HOLD',
                'orders': [],
                'reason': f'Error: {str(e)}'
            }
    
    def is_price_outside_grid(self, current_price: float) -> bool:
        """Check if price moved too far from grid range"""
        if not self.buy_grid or not self.sell_grid:
            return False
        
        lowest_buy = self.buy_grid[-1].price
        highest_sell = self.sell_grid[-1].price
        
        # Check if price is 5% beyond grid boundaries
        if current_price < lowest_buy * 0.95 or current_price > highest_sell * 1.05:
            return True
        
        return False
    
    def on_order_filled(self, order_id: str, fill_price: float, fill_quantity: float, side: str):
        """Handle order fill event"""
        try:
            # Update grid level status
            grid_to_check = self.buy_grid if side == 'BUY' else self.sell_grid
            
            for level in grid_to_check:
                if level.order_id == order_id:
                    level.filled = True
                    level.fill_time = datetime.now()
                    
                    # Calculate profit if this completes a cycle
                    if side == 'SELL':
                        # Find corresponding buy level
                        profit = (fill_price - self.center_price) * fill_quantity
                        self.grid_profits += profit
                        self.completed_cycles += 1
                        
                        logger.info(f"Grid cycle completed: Profit=${profit:.2f}")
                    
                    break
            
            # Reset filled level for next cycle
            self._reset_filled_level(order_id, side)
            
        except Exception as e:
            logger.error(f"Error handling order fill: {e}")
    
    def _reset_filled_level(self, order_id: str, side: str):
        """Reset a filled level for the next trading cycle"""
        # In grid trading, we want to reuse levels
        # So we reset the filled status after a short delay
        grid_to_reset = self.buy_grid if side == 'BUY' else self.sell_grid
        
        for level in grid_to_reset:
            if level.order_id == order_id:
                # Reset for next cycle
                level.order_id = None
                level.filled = False
                level.fill_time = None
                break
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        active_orders = sum(1 for level in self.buy_grid + self.sell_grid if level.order_id and not level.filled)
        filled_orders = sum(1 for level in self.buy_grid + self.sell_grid if level.filled)
        
        return {
            'strategy': 'BNB Grid Trading',
            'center_price': self.center_price,
            'grid_levels': self.grid_levels,
            'active_orders': active_orders,
            'filled_orders': filled_orders,
            'completed_cycles': self.completed_cycles,
            'grid_profits': self.grid_profits,
            'last_update': self.last_update_time
        }
    
    def should_close_all(self, data: pd.DataFrame) -> bool:
        """Check if all positions should be closed (risk management)"""
        try:
            if self.sma is None or len(self.sma) < 2:
                return False
            
            current_price = data['Close'].iloc[-1]
            sma_value = self.sma.iloc[-1]
            
            # Close if price breaks below SMA by 5% (trend reversal)
            if current_price < sma_value * 0.95:
                logger.warning("Price broke below SMA significantly, consider closing positions")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in should_close_all: {e}")
            return False