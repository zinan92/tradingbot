"""
Grid Strategy Application Service

Coordinates grid strategy execution, integrating with market data,
order management, and risk management services.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from src.domain.strategy.aggregates.grid_strategy_aggregate import (
    GridStrategyAggregate,
    GridConfiguration,
    GridLevel,
    GridState
)
from src.domain.strategy.regime.regime_manager import RegimeManager
from src.domain.trading.value_objects.symbol import Symbol
from src.domain.trading.value_objects.quantity import Quantity
from src.domain.trading.value_objects.price import Price
from src.domain.trading.value_objects.side import Side
from src.application.trading.commands.place_order_command_v2 import PlaceOrderCommand
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus


logger = logging.getLogger(__name__)


class GridStrategyService:
    """
    Application service for grid trading strategy.
    
    Orchestrates grid strategy execution by coordinating between
    domain logic, market data, and order management.
    """
    
    def __init__(self,
                 event_bus: InMemoryEventBus,
                 regime_manager: RegimeManager,
                 order_service: Any,  # Order management service
                 market_data_service: Any,  # Market data service
                 indicator_service: Any):  # Technical indicator service
        """
        Initialize grid strategy service.
        
        Args:
            event_bus: Event bus for publishing domain events
            regime_manager: Market regime manager
            order_service: Service for placing orders
            market_data_service: Service for market data
            indicator_service: Service for technical indicators
        """
        self.event_bus = event_bus
        self.regime_manager = regime_manager
        self.order_service = order_service
        self.market_data_service = market_data_service
        self.indicator_service = indicator_service
        
        # Active strategies
        self.active_strategies: Dict[str, GridStrategyAggregate] = {}
        
        # Position tracking
        self.position_map: Dict[str, str] = {}  # position_id -> strategy_id
        
        # ATR history for volatility filtering
        self.atr_history: Dict[str, List[float]] = {}
    
    def create_strategy(self,
                       symbol: str,
                       config: Optional[GridConfiguration] = None) -> str:
        """
        Create and activate a new grid strategy.
        
        Args:
            symbol: Trading symbol
            config: Grid configuration (uses defaults if None)
            
        Returns:
            Strategy ID
        """
        strategy_id = str(uuid.uuid4())
        
        # Use default config if not provided
        if config is None:
            config = GridConfiguration()
        
        # Get current market regime
        current_regime = self.regime_manager.get_current_regime()
        
        # Create strategy aggregate
        strategy = GridStrategyAggregate(
            strategy_id=strategy_id,
            symbol=Symbol(symbol),
            config=config,
            initial_regime=current_regime
        )
        
        # Store strategy
        self.active_strategies[strategy_id] = strategy
        self.atr_history[strategy_id] = []
        
        logger.info(f"Created grid strategy {strategy_id} for {symbol}")
        logger.info(f"Config: ATR mult={config.atr_multiplier}, "
                   f"Levels={config.grid_levels}, "
                   f"Regime={current_regime.value}")
        
        # Publish strategy created event
        self.event_bus.publish({
            'type': 'GridStrategyCreated',
            'strategy_id': strategy_id,
            'symbol': symbol,
            'config': {
                'atr_multiplier': config.atr_multiplier,
                'grid_levels': config.grid_levels,
                'max_position_size': config.max_position_size
            },
            'regime': current_regime.value,
            'timestamp': datetime.now()
        })
        
        return strategy_id
    
    async def process_market_data(self, market_data: Dict[str, Any]) -> None:
        """
        Process incoming market data and update strategies.
        
        Args:
            market_data: Market data event with price and volume
        """
        symbol = market_data.get('symbol')
        price = market_data.get('price')
        
        if not symbol or not price:
            return
        
        # Process for each active strategy on this symbol
        for strategy_id, strategy in self.active_strategies.items():
            if strategy.symbol.value == symbol:
                await self._process_strategy_tick(strategy_id, price)
    
    async def _process_strategy_tick(self, strategy_id: str, current_price: float) -> None:
        """
        Process a price tick for a specific strategy.
        
        Args:
            strategy_id: Strategy identifier
            current_price: Current market price
        """
        strategy = self.active_strategies.get(strategy_id)
        if not strategy:
            return
        
        try:
            # Get current ATR
            atr_data = await self._get_current_atr(strategy.symbol.value)
            if not atr_data:
                return
            
            current_atr = atr_data['value']
            
            # Update ATR history
            if strategy_id in self.atr_history:
                self.atr_history[strategy_id].append(current_atr)
                # Keep last 100 values
                if len(self.atr_history[strategy_id]) > 100:
                    self.atr_history[strategy_id] = self.atr_history[strategy_id][-100:]
            
            # Check if grid should be active
            if not strategy.should_activate_grid(current_atr, self.atr_history[strategy_id]):
                if strategy.state == GridState.ACTIVE:
                    strategy.state = GridState.SUSPENDED
                    logger.info(f"Strategy {strategy_id} suspended due to volatility")
                return
            
            # Update grid if needed
            strategy.update_grid(current_price, current_atr)
            
            # Check for buy signals
            buy_level = strategy.check_buy_signal(current_price)
            if buy_level:
                await self._execute_buy_order(strategy, buy_level, current_price)
            
            # Check for sell signals
            sell_level = strategy.check_sell_signal(current_price)
            if sell_level:
                await self._execute_sell_order(strategy, sell_level, current_price)
            
            # Check stop losses for active positions
            await self._check_stop_losses(strategy, current_price)
            
            # Process and publish any domain events
            events = strategy.clear_events()
            for event in events:
                self.event_bus.publish(event)
            
        except Exception as e:
            logger.error(f"Error processing tick for strategy {strategy_id}: {e}")
    
    async def _get_current_atr(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current ATR value for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            ATR data or None
        """
        try:
            # Get ATR from indicator service
            indicators = self.indicator_service.get_latest_indicators(
                symbol=symbol,
                timeframe='5m'  # Use 5m timeframe for grid
            )
            
            atr_data = indicators.get('atr')
            if atr_data:
                return atr_data
            
            # Calculate if not available
            await self.indicator_service.calculate_and_publish(
                symbol=symbol,
                interval='5m'
            )
            
            # Try again
            indicators = self.indicator_service.get_latest_indicators(
                symbol=symbol,
                timeframe='5m'
            )
            
            return indicators.get('atr')
            
        except Exception as e:
            logger.error(f"Error getting ATR for {symbol}: {e}")
            return None
    
    async def _execute_buy_order(self, 
                                strategy: GridStrategyAggregate,
                                grid_level: GridLevel,
                                current_price: float) -> None:
        """
        Execute a buy order at grid level.
        
        Args:
            strategy: Grid strategy aggregate
            grid_level: Grid level that triggered
            current_price: Current market price
        """
        try:
            # Calculate position size
            position_size = strategy.calculate_position_size()
            if position_size <= 0:
                logger.warning(f"Strategy {strategy.id}: Cannot open position, size limit reached")
                return
            
            # Create order command
            order_command = PlaceOrderCommand(
                portfolio_id="default",  # TODO: Get from strategy config
                symbol=strategy.symbol.value,
                quantity=position_size * 10000,  # Convert to base units
                order_type="LIMIT",
                side="BUY",
                price=grid_level.price
            )
            
            # Place order
            result = await self.order_service.place_order(order_command)
            
            if result.get('success'):
                order_id = result.get('order_id')
                position_id = str(uuid.uuid4())
                
                # Record in strategy
                strategy.record_position_opened(
                    position_id=position_id,
                    grid_level=grid_level,
                    size=position_size
                )
                
                # Track position
                self.position_map[position_id] = strategy.id
                
                logger.info(f"Strategy {strategy.id}: Opened BUY position at {grid_level.price}")
                
                # Publish order placed event
                self.event_bus.publish({
                    'type': 'GridOrderPlaced',
                    'strategy_id': strategy.id,
                    'position_id': position_id,
                    'order_id': order_id,
                    'side': 'BUY',
                    'price': grid_level.price,
                    'size': position_size,
                    'timestamp': datetime.now()
                })
            else:
                logger.error(f"Strategy {strategy.id}: Failed to place buy order: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error executing buy order for strategy {strategy.id}: {e}")
    
    async def _execute_sell_order(self,
                                 strategy: GridStrategyAggregate,
                                 grid_level: GridLevel,
                                 current_price: float) -> None:
        """
        Execute a sell order at grid level.
        
        Args:
            strategy: Grid strategy aggregate
            grid_level: Grid level that triggered
            current_price: Current market price
        """
        try:
            # Calculate position size
            position_size = strategy.calculate_position_size()
            if position_size <= 0:
                logger.warning(f"Strategy {strategy.id}: Cannot open position, size limit reached")
                return
            
            # Create order command
            order_command = PlaceOrderCommand(
                portfolio_id="default",
                symbol=strategy.symbol.value,
                quantity=position_size * 10000,
                order_type="LIMIT",
                side="SELL",
                price=grid_level.price
            )
            
            # Place order
            result = await self.order_service.place_order(order_command)
            
            if result.get('success'):
                order_id = result.get('order_id')
                position_id = str(uuid.uuid4())
                
                # Record in strategy
                strategy.record_position_opened(
                    position_id=position_id,
                    grid_level=grid_level,
                    size=position_size
                )
                
                # Track position
                self.position_map[position_id] = strategy.id
                
                logger.info(f"Strategy {strategy.id}: Opened SELL position at {grid_level.price}")
                
                # Publish order placed event
                self.event_bus.publish({
                    'type': 'GridOrderPlaced',
                    'strategy_id': strategy.id,
                    'position_id': position_id,
                    'order_id': order_id,
                    'side': 'SELL',
                    'price': grid_level.price,
                    'size': position_size,
                    'timestamp': datetime.now()
                })
            else:
                logger.error(f"Strategy {strategy.id}: Failed to place sell order: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error executing sell order for strategy {strategy.id}: {e}")
    
    async def _check_stop_losses(self,
                                strategy: GridStrategyAggregate,
                                current_price: float) -> None:
        """
        Check and execute stop losses for active positions.
        
        Args:
            strategy: Grid strategy aggregate
            current_price: Current market price
        """
        positions_to_close = []
        
        for position_id, position_data in strategy.active_positions.items():
            grid_level = position_data['level']
            position_side = position_data['side']
            
            # Check if stop loss triggered
            if strategy.check_stop_loss(current_price, grid_level.price, position_side):
                positions_to_close.append(position_id)
        
        # Close positions that hit stop loss
        for position_id in positions_to_close:
            await self._close_position(strategy, position_id, current_price, is_stop_loss=True)
    
    async def _close_position(self,
                            strategy: GridStrategyAggregate,
                            position_id: str,
                            exit_price: float,
                            is_stop_loss: bool = False) -> None:
        """
        Close a grid position.
        
        Args:
            strategy: Grid strategy aggregate
            position_id: Position identifier
            exit_price: Exit price
            is_stop_loss: Whether this is a stop loss exit
        """
        try:
            position_data = strategy.active_positions.get(position_id)
            if not position_data:
                return
            
            grid_level = position_data['level']
            position_size = position_data['size']
            position_side = position_data['side']
            
            # Calculate PnL
            entry_price = grid_level.price
            if position_side == 'LONG':
                pnl = (exit_price - entry_price) * position_size * 10000
            else:  # SHORT
                pnl = (entry_price - exit_price) * position_size * 10000
            
            # Place closing order
            close_side = 'SELL' if position_side == 'LONG' else 'BUY'
            order_command = PlaceOrderCommand(
                portfolio_id="default",
                symbol=strategy.symbol.value,
                quantity=position_size * 10000,
                order_type="MARKET",
                side=close_side
            )
            
            result = await self.order_service.place_order(order_command)
            
            if result.get('success'):
                # Record position closed
                strategy.record_position_closed(
                    position_id=position_id,
                    exit_price=exit_price,
                    pnl=pnl
                )
                
                # Remove from tracking
                if position_id in self.position_map:
                    del self.position_map[position_id]
                
                logger.info(f"Strategy {strategy.id}: Closed position {position_id} "
                          f"at {exit_price}, PnL: {pnl:.2f}")
                
                # Publish position closed event
                self.event_bus.publish({
                    'type': 'GridPositionClosed',
                    'strategy_id': strategy.id,
                    'position_id': position_id,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'is_stop_loss': is_stop_loss,
                    'timestamp': datetime.now()
                })
            else:
                logger.error(f"Strategy {strategy.id}: Failed to close position: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error closing position {position_id}: {e}")
    
    def update_regime(self, new_regime: str) -> None:
        """
        Update market regime for all active strategies.
        
        Args:
            new_regime: New market regime string
        """
        try:
            # Update regime manager
            from src.domain.strategy.regime.regime_models import MarketRegime
            regime = MarketRegime.from_string(new_regime)
            self.regime_manager.update_regime(regime)
            
            # Update all active strategies
            for strategy_id, strategy in self.active_strategies.items():
                strategy.update_market_regime(regime)
                
                # Process events
                events = strategy.clear_events()
                for event in events:
                    self.event_bus.publish(event)
            
            logger.info(f"Updated all strategies to regime: {new_regime}")
            
        except Exception as e:
            logger.error(f"Error updating regime: {e}")
    
    def get_strategy_status(self, strategy_id: str) -> Dict[str, Any]:
        """
        Get current status of a strategy.
        
        Args:
            strategy_id: Strategy identifier
            
        Returns:
            Strategy status information
        """
        strategy = self.active_strategies.get(strategy_id)
        if not strategy:
            return {'error': 'Strategy not found'}
        
        return {
            'strategy_id': strategy_id,
            'symbol': strategy.symbol.value,
            'state': strategy.state.value,
            'regime': strategy.market_regime.value,
            'grid_mode': strategy.grid_mode.value,
            'reference_price': strategy.reference_price,
            'buy_levels': len(strategy.buy_levels),
            'sell_levels': len(strategy.sell_levels),
            'active_positions': strategy.position_count,
            'total_position_size': strategy.total_position_size,
            'total_pnl': strategy.total_pnl,
            'risk_metrics': strategy.get_risk_metrics()
        }
    
    def get_all_strategies(self) -> List[Dict[str, Any]]:
        """Get status of all active strategies"""
        return [
            self.get_strategy_status(strategy_id)
            for strategy_id in self.active_strategies.keys()
        ]
    
    def stop_strategy(self, strategy_id: str) -> bool:
        """
        Stop and remove a strategy.
        
        Args:
            strategy_id: Strategy identifier
            
        Returns:
            True if successful
        """
        if strategy_id in self.active_strategies:
            strategy = self.active_strategies[strategy_id]
            strategy.state = GridState.INACTIVE
            
            # Close all positions
            # TODO: Implement position closing
            
            del self.active_strategies[strategy_id]
            
            logger.info(f"Stopped strategy {strategy_id}")
            
            # Publish strategy stopped event
            self.event_bus.publish({
                'type': 'GridStrategyStopped',
                'strategy_id': strategy_id,
                'final_pnl': strategy.total_pnl,
                'timestamp': datetime.now()
            })
            
            return True
        
        return False