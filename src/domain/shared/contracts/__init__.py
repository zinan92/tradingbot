"""
Domain Contracts

Pydantic models for data transfer objects used across domain boundaries.
"""
from .order_contracts import (
    OrderSide,
    OrderType,
    OrderStatus,
    OrderRequest,
    OrderResponse,
    OrderModification
)
from .position_contracts import (
    PositionSide,
    Position,
    PositionUpdate,
    PortfolioState
)
from .backtest_contracts import (
    BacktestInput,
    BacktestMetrics,
    BacktestTrade,
    BacktestReport
)
from .strategy_contracts import (
    SignalType,
    SignalStrength,
    StrategyConfig,
    TradingSignal,
    StrategyPerformance,
    StrategyState
)
from .core_events import (
    OrderPlaced,
    OrderFilled,
    PositionUpdated,
    SignalGenerated,
    StrategyDeployed,
    DomainEvent
)

__all__ = [
    # Order contracts
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'OrderRequest',
    'OrderResponse',
    'OrderModification',
    
    # Position contracts
    'PositionSide',
    'Position',
    'PositionUpdate',
    'PortfolioState',
    
    # Backtest contracts
    'BacktestInput',
    'BacktestMetrics',
    'BacktestTrade',
    'BacktestReport',
    
    # Strategy contracts
    'SignalType',
    'SignalStrength',
    'StrategyConfig',
    'TradingSignal',
    'StrategyPerformance',
    'StrategyState',
    
    # Core events
    'OrderPlaced',
    'OrderFilled',
    'PositionUpdated',
    'SignalGenerated',
    'StrategyDeployed',
    'DomainEvent'
]