"""
Grid Strategy Aggregate

Domain aggregate for ATR-based grid trading strategy.
Encapsulates grid calculation, level management, and trading decisions.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

from src.domain.trading.value_objects.symbol import Symbol
from src.domain.trading.value_objects.price import Price
from src.domain.trading.value_objects.quantity import Quantity
from src.domain.trading.value_objects.side import Side
from src.domain.strategy.regime.regime_models import MarketRegime, GridMode


@dataclass(frozen=True)
class GridLevel:
    """Value object representing a single grid level"""
    price: float
    side: str  # 'BUY' or 'SELL'
    level_index: int
    is_active: bool = True
    
    def __post_init__(self):
        if self.side not in ['BUY', 'SELL']:
            raise ValueError(f"Invalid side: {self.side}")
        if self.price <= 0:
            raise ValueError(f"Invalid price: {self.price}")


@dataclass(frozen=True)
class GridConfiguration:
    """Value object for grid configuration parameters"""
    atr_multiplier: float = 0.75
    grid_levels: int = 5
    max_position_size: float = 0.1
    stop_loss_atr_multiplier: float = 2.0
    recalculation_threshold: float = 0.5  # Recalc if price moves > 0.5 ATR
    
    def __post_init__(self):
        if self.atr_multiplier <= 0:
            raise ValueError("ATR multiplier must be positive")
        if self.grid_levels <= 0:
            raise ValueError("Grid levels must be positive")
        if not 0 < self.max_position_size <= 1:
            raise ValueError("Max position size must be between 0 and 1")


class GridState(Enum):
    """Grid strategy state"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    SUSPENDED = "suspended"  # Temporarily suspended due to risk
    RECALCULATING = "recalculating"


class GridStrategyAggregate:
    """
    Aggregate root for Grid Trading Strategy.
    
    Manages grid levels, tracks positions, and makes trading decisions
    based on ATR and market regime.
    """
    
    def __init__(self, 
                 strategy_id: str,
                 symbol: Symbol,
                 config: GridConfiguration,
                 initial_regime: MarketRegime = MarketRegime.NONE):
        """
        Initialize grid strategy aggregate.
        
        Args:
            strategy_id: Unique identifier for this strategy instance
            symbol: Trading symbol
            config: Grid configuration parameters
            initial_regime: Initial market regime
        """
        self.id = strategy_id
        self.symbol = symbol
        self.config = config
        self.market_regime = initial_regime
        self.grid_mode = self._get_grid_mode_for_regime(initial_regime)
        
        # Grid state
        self.state = GridState.INACTIVE
        self.buy_levels: List[GridLevel] = []
        self.sell_levels: List[GridLevel] = []
        self.reference_price: Optional[float] = None
        self.last_atr: Optional[float] = None
        self.last_recalculation: Optional[datetime] = None
        
        # Position tracking
        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.position_count = 0
        self.total_position_size = 0.0
        
        # Risk metrics
        self.consecutive_losses = 0
        self.max_drawdown = 0.0
        self.total_pnl = 0.0
        
        # Events to be published
        self.events = []
    
    def _get_grid_mode_for_regime(self, regime: MarketRegime) -> GridMode:
        """Map market regime to grid mode"""
        mapping = {
            MarketRegime.BULLISH: GridMode.LONG_ONLY,
            MarketRegime.BEARISH: GridMode.SHORT_ONLY,
            MarketRegime.RANGE: GridMode.BIDIRECTIONAL,
            MarketRegime.NONE: GridMode.DISABLED
        }
        return mapping.get(regime, GridMode.DISABLED)
    
    def update_market_regime(self, new_regime: MarketRegime) -> None:
        """
        Update market regime and adjust grid mode.
        
        Args:
            new_regime: New market regime
        """
        if self.market_regime != new_regime:
            old_regime = self.market_regime
            self.market_regime = new_regime
            self.grid_mode = self._get_grid_mode_for_regime(new_regime)
            
            # Emit regime change event
            self.events.append({
                'type': 'RegimeChanged',
                'strategy_id': self.id,
                'old_regime': old_regime.value,
                'new_regime': new_regime.value,
                'grid_mode': self.grid_mode.value,
                'timestamp': datetime.now()
            })
            
            # Suspend grid if disabled
            if self.grid_mode == GridMode.DISABLED:
                self.state = GridState.SUSPENDED
    
    def calculate_grid_levels(self, 
                            reference_price: float, 
                            atr_value: float) -> Tuple[List[GridLevel], List[GridLevel]]:
        """
        Calculate buy and sell grid levels around reference price.
        
        Args:
            reference_price: Center price for grid
            atr_value: Current ATR value
            
        Returns:
            Tuple of (buy_levels, sell_levels)
        """
        if atr_value <= 0:
            raise ValueError("ATR must be positive")
        if reference_price <= 0:
            raise ValueError("Reference price must be positive")
        
        # Calculate grid spacing
        grid_spacing = atr_value * self.config.atr_multiplier
        
        buy_levels = []
        sell_levels = []
        
        # Generate grid levels based on mode
        if self.grid_mode in [GridMode.LONG_ONLY, GridMode.BIDIRECTIONAL]:
            for i in range(1, self.config.grid_levels + 1):
                buy_price = reference_price - (grid_spacing * i)
                buy_levels.append(GridLevel(
                    price=buy_price,
                    side='BUY',
                    level_index=i,
                    is_active=True
                ))
        
        if self.grid_mode in [GridMode.SHORT_ONLY, GridMode.BIDIRECTIONAL]:
            for i in range(1, self.config.grid_levels + 1):
                sell_price = reference_price + (grid_spacing * i)
                sell_levels.append(GridLevel(
                    price=sell_price,
                    side='SELL',
                    level_index=i,
                    is_active=True
                ))
        
        return buy_levels, sell_levels
    
    def should_recalculate_grid(self, current_price: float, current_atr: float) -> bool:
        """
        Determine if grid should be recalculated.
        
        Args:
            current_price: Current market price
            current_atr: Current ATR value
            
        Returns:
            True if grid should be recalculated
        """
        if self.reference_price is None or self.last_atr is None:
            return True
        
        # Check if price moved significantly
        price_change = abs(current_price - self.reference_price)
        threshold = current_atr * self.config.recalculation_threshold
        
        return price_change > threshold
    
    def update_grid(self, current_price: float, current_atr: float) -> None:
        """
        Update grid levels based on current market conditions.
        
        Args:
            current_price: Current market price
            current_atr: Current ATR value
        """
        if self.grid_mode == GridMode.DISABLED:
            self.state = GridState.SUSPENDED
            return
        
        # Check if recalculation needed
        if self.should_recalculate_grid(current_price, current_atr):
            self.state = GridState.RECALCULATING
            
            # Calculate new levels
            self.buy_levels, self.sell_levels = self.calculate_grid_levels(
                current_price, current_atr
            )
            
            # Update reference values
            self.reference_price = current_price
            self.last_atr = current_atr
            self.last_recalculation = datetime.now()
            
            # Emit grid update event
            self.events.append({
                'type': 'GridUpdated',
                'strategy_id': self.id,
                'reference_price': current_price,
                'atr': current_atr,
                'buy_levels': len(self.buy_levels),
                'sell_levels': len(self.sell_levels),
                'timestamp': datetime.now()
            })
            
            self.state = GridState.ACTIVE
    
    def check_buy_signal(self, current_price: float) -> Optional[GridLevel]:
        """
        Check if current price hits a buy grid level.
        
        Args:
            current_price: Current market price
            
        Returns:
            GridLevel if buy signal triggered, None otherwise
        """
        if self.grid_mode not in [GridMode.LONG_ONLY, GridMode.BIDIRECTIONAL]:
            return None
        
        if self.state != GridState.ACTIVE:
            return None
        
        # Check if price hits any buy level
        for level in self.buy_levels:
            if level.is_active and current_price <= level.price:
                return level
        
        return None
    
    def check_sell_signal(self, current_price: float) -> Optional[GridLevel]:
        """
        Check if current price hits a sell grid level.
        
        Args:
            current_price: Current market price
            
        Returns:
            GridLevel if sell signal triggered, None otherwise
        """
        if self.grid_mode not in [GridMode.SHORT_ONLY, GridMode.BIDIRECTIONAL]:
            return None
        
        if self.state != GridState.ACTIVE:
            return None
        
        # Check if price hits any sell level
        for level in self.sell_levels:
            if level.is_active and current_price >= level.price:
                return level
        
        return None
    
    def calculate_position_size(self) -> float:
        """
        Calculate position size based on risk management rules.
        
        Returns:
            Position size as fraction of equity
        """
        # Base size divided by number of levels
        base_size = self.config.max_position_size / self.config.grid_levels
        
        # Reduce size if we have multiple positions
        size_adjustment = max(0.5, 1.0 - (self.position_count * 0.1))
        
        return min(base_size * size_adjustment, 
                  self.config.max_position_size - self.total_position_size)
    
    def should_activate_grid(self, atr_value: float, 
                           atr_history: List[float]) -> bool:
        """
        Determine if grid should be activated.
        
        Args:
            atr_value: Current ATR value
            atr_history: Recent ATR values (not used after removing filter)
            
        Returns:
            True if grid should be active
        """
        if self.grid_mode == GridMode.DISABLED:
            return False
        
        # Always activate grid if not disabled
        return True
    
    def check_stop_loss(self, current_price: float, 
                       position_entry: float, 
                       position_side: str) -> bool:
        """
        Check if stop loss is triggered for a position.
        
        Args:
            current_price: Current market price
            position_entry: Entry price of position
            position_side: 'LONG' or 'SHORT'
            
        Returns:
            True if stop loss triggered
        """
        if self.last_atr is None:
            return False
        
        stop_distance = self.last_atr * self.config.stop_loss_atr_multiplier
        
        if position_side == 'LONG':
            stop_price = position_entry - stop_distance
            return current_price <= stop_price
        elif position_side == 'SHORT':
            stop_price = position_entry + stop_distance
            return current_price >= stop_price
        
        return False
    
    def record_position_opened(self, position_id: str, 
                              grid_level: GridLevel,
                              size: float) -> None:
        """
        Record that a position was opened at a grid level.
        
        Args:
            position_id: Unique position identifier
            grid_level: Grid level that triggered the position
            size: Position size
        """
        self.active_positions[position_id] = {
            'level': grid_level,
            'size': size,
            'entry_time': datetime.now(),
            'side': 'LONG' if grid_level.side == 'BUY' else 'SHORT'
        }
        
        self.position_count += 1
        self.total_position_size += size
        
        # Deactivate the level
        for level in (self.buy_levels if grid_level.side == 'BUY' else self.sell_levels):
            if level.level_index == grid_level.level_index:
                # Create new level with is_active=False (immutable)
                new_levels = []
                for l in (self.buy_levels if grid_level.side == 'BUY' else self.sell_levels):
                    if l.level_index == grid_level.level_index:
                        new_levels.append(GridLevel(
                            price=l.price,
                            side=l.side,
                            level_index=l.level_index,
                            is_active=False
                        ))
                    else:
                        new_levels.append(l)
                
                if grid_level.side == 'BUY':
                    self.buy_levels = new_levels
                else:
                    self.sell_levels = new_levels
                break
        
        # Emit position opened event
        self.events.append({
            'type': 'GridPositionOpened',
            'strategy_id': self.id,
            'position_id': position_id,
            'level_price': grid_level.price,
            'side': grid_level.side,
            'size': size,
            'timestamp': datetime.now()
        })
    
    def record_position_closed(self, position_id: str, 
                             exit_price: float,
                             pnl: float) -> None:
        """
        Record that a position was closed.
        
        Args:
            position_id: Position identifier
            exit_price: Exit price
            pnl: Profit/loss amount
        """
        if position_id in self.active_positions:
            position = self.active_positions[position_id]
            
            # Reactivate the grid level
            level_to_reactivate = position['level']
            new_levels = []
            
            levels_list = self.buy_levels if level_to_reactivate.side == 'BUY' else self.sell_levels
            for level in levels_list:
                if level.level_index == level_to_reactivate.level_index:
                    new_levels.append(GridLevel(
                        price=level.price,
                        side=level.side,
                        level_index=level.level_index,
                        is_active=True
                    ))
                else:
                    new_levels.append(level)
            
            if level_to_reactivate.side == 'BUY':
                self.buy_levels = new_levels
            else:
                self.sell_levels = new_levels
            
            # Update tracking
            del self.active_positions[position_id]
            self.position_count = max(0, self.position_count - 1)
            self.total_position_size = max(0, self.total_position_size - position['size'])
            self.total_pnl += pnl
            
            # Track consecutive losses
            if pnl < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0
            
            # Emit position closed event
            self.events.append({
                'type': 'GridPositionClosed',
                'strategy_id': self.id,
                'position_id': position_id,
                'exit_price': exit_price,
                'pnl': pnl,
                'timestamp': datetime.now()
            })
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics for the strategy"""
        return {
            'active_positions': self.position_count,
            'total_position_size': self.total_position_size,
            'consecutive_losses': self.consecutive_losses,
            'max_drawdown': self.max_drawdown,
            'total_pnl': self.total_pnl,
            'grid_state': self.state.value,
            'market_regime': self.market_regime.value,
            'grid_mode': self.grid_mode.value
        }
    
    def clear_events(self) -> List[Dict[str, Any]]:
        """Clear and return accumulated events"""
        events = self.events.copy()
        self.events = []
        return events