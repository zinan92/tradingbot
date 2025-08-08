"""
Start Grid Strategy Command

Command to start a grid trading strategy for live trading.
"""

from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from src.domain.strategy.aggregates.grid_strategy_aggregate import GridConfiguration


@dataclass
class StartGridStrategyCommand:
    """
    Command to start a new grid trading strategy.
    
    Attributes:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        atr_multiplier: ATR multiplier for grid spacing
        grid_levels: Number of grid levels on each side
        max_position_size: Maximum position size as fraction of capital
        stop_loss_atr_multiplier: Stop loss distance in ATR multiples
        recalculation_threshold: Threshold for grid recalculation
    """
    symbol: str
    atr_multiplier: float = 0.75
    grid_levels: int = 5
    max_position_size: float = 0.1
    stop_loss_atr_multiplier: float = 2.0
    recalculation_threshold: float = 0.5


class StartGridStrategyCommandHandler:
    """Handler for starting grid strategy."""
    
    def __init__(self, grid_strategy_service):
        """
        Initialize command handler.
        
        Args:
            grid_strategy_service: Grid strategy application service
        """
        self.grid_strategy_service = grid_strategy_service
    
    async def handle(self, command: StartGridStrategyCommand) -> dict:
        """
        Handle start grid strategy command.
        
        Args:
            command: Start grid strategy command
            
        Returns:
            Result dictionary with strategy_id or error
        """
        try:
            # Create grid configuration
            config = GridConfiguration(
                atr_multiplier=command.atr_multiplier,
                grid_levels=command.grid_levels,
                max_position_size=command.max_position_size,
                stop_loss_atr_multiplier=command.stop_loss_atr_multiplier,
                recalculation_threshold=command.recalculation_threshold
            )
            
            # Start strategy
            strategy_id = self.grid_strategy_service.create_strategy(
                symbol=command.symbol,
                config=config
            )
            
            return {
                'success': True,
                'strategy_id': strategy_id,
                'message': f'Grid strategy started for {command.symbol}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


@dataclass
class StopGridStrategyCommand:
    """Command to stop a grid strategy."""
    strategy_id: str


class StopGridStrategyCommandHandler:
    """Handler for stopping grid strategy."""
    
    def __init__(self, grid_strategy_service):
        """
        Initialize command handler.
        
        Args:
            grid_strategy_service: Grid strategy application service
        """
        self.grid_strategy_service = grid_strategy_service
    
    async def handle(self, command: StopGridStrategyCommand) -> dict:
        """
        Handle stop grid strategy command.
        
        Args:
            command: Stop grid strategy command
            
        Returns:
            Result dictionary
        """
        try:
            success = self.grid_strategy_service.stop_strategy(command.strategy_id)
            
            if success:
                return {
                    'success': True,
                    'message': f'Strategy {command.strategy_id} stopped'
                }
            else:
                return {
                    'success': False,
                    'error': 'Strategy not found'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


@dataclass
class UpdateGridRegimeCommand:
    """Command to update market regime for grid strategies."""
    new_regime: str  # 'bullish', 'bearish', 'range', 'none'


class UpdateGridRegimeCommandHandler:
    """Handler for updating grid regime."""
    
    def __init__(self, grid_strategy_service):
        """
        Initialize command handler.
        
        Args:
            grid_strategy_service: Grid strategy application service
        """
        self.grid_strategy_service = grid_strategy_service
    
    async def handle(self, command: UpdateGridRegimeCommand) -> dict:
        """
        Handle update regime command.
        
        Args:
            command: Update regime command
            
        Returns:
            Result dictionary
        """
        try:
            self.grid_strategy_service.update_regime(command.new_regime)
            
            return {
                'success': True,
                'message': f'Regime updated to {command.new_regime}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }