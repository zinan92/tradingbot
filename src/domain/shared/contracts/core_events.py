# src/domain/shared/contracts/core_events.py
# SHARE THIS WITH ALL 5 CLAUDE CODE INSTANCES

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

@dataclass
class DomainEvent:
    event_id: str
    occurred_at: datetime
    correlation_id: str
    source_context: str

# Trading Events
@dataclass
class OrderPlaced(DomainEvent):
    order_id: str
    portfolio_id: str
    symbol: str
    quantity: int
    order_type: str

@dataclass
class OrderFilled(DomainEvent):
    order_id: str
    executed_price: Decimal
    executed_quantity: int

@dataclass
class PositionUpdated(DomainEvent):
    portfolio_id: str
    symbol: str
    quantity: int
    average_price: Decimal

# Strategy Events
@dataclass
class SignalGenerated(DomainEvent):
    strategy_id: str
    symbol: str
    action: str  # BUY/SELL
    quantity: int
    confidence: float

@dataclass
class StrategyDeployed(DomainEvent):
    strategy_id: str
    name: str
    capital_allocated: Decimal

# Risk Events
@dataclass
class RiskCheckRequested(DomainEvent):
    order_id: str
    portfolio_id: str
    exposure: Decimal

@dataclass
class RiskCheckCompleted(DomainEvent):
    order_id: str
    approved: bool
    reason: Optional[str]

# Market Data Events
@dataclass
class MarketDataReceived(DomainEvent):
    symbol: str
    price: Decimal
    volume: int
    timestamp: datetime

@dataclass
class IndicatorCalculated(DomainEvent):
    symbol: str
    indicator_name: str
    value: Decimal
    timestamp: datetime

# Backtesting Events
@dataclass
class BacktestRequested(DomainEvent):
    strategy_id: str
    start_date: datetime
    end_date: datetime

@dataclass
class BacktestCompleted(DomainEvent):
    strategy_id: str
    total_return: Decimal
    sharpe_ratio: float
    max_drawdown: float