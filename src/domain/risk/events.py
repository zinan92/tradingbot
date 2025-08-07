"""
Domain events for Risk bounded context
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class RiskEvent:
    """Base class for risk domain events"""
    occurred_at: datetime
    
    def to_dict(self):
        return {
            "event_type": self.__class__.__name__,
            "occurred_at": self.occurred_at.isoformat(),
            **self._get_event_data()
        }
    
    def _get_event_data(self):
        return {}


@dataclass(frozen=True)
class RiskLimitBreached(RiskEvent):
    """Risk limit has been breached"""
    portfolio_id: UUID
    order_id: Optional[UUID]
    limit_type: str
    current_value: Decimal
    limit_value: Decimal
    action_taken: str
    
    def _get_event_data(self):
        return {
            "portfolio_id": str(self.portfolio_id),
            "order_id": str(self.order_id) if self.order_id else None,
            "limit_type": self.limit_type,
            "current_value": str(self.current_value),
            "limit_value": str(self.limit_value),
            "action_taken": self.action_taken
        }


@dataclass(frozen=True)
class OrderRejectedByRisk(RiskEvent):
    """Order rejected due to risk limits"""
    order_id: UUID
    reason: str
    
    def _get_event_data(self):
        return {
            "order_id": str(self.order_id),
            "reason": self.reason
        }


@dataclass(frozen=True)
class SignalRejected(RiskEvent):
    """Trading signal rejected by risk checks"""
    signal_id: UUID
    reason: str
    
    def _get_event_data(self):
        return {
            "signal_id": str(self.signal_id),
            "reason": self.reason
        }


@dataclass(frozen=True)
class StopLossTriggered(RiskEvent):
    """Stop-loss has been triggered"""
    portfolio_id: UUID
    position_id: UUID
    symbol: str
    stop_price: Decimal
    quantity: int
    
    def _get_event_data(self):
        return {
            "portfolio_id": str(self.portfolio_id),
            "position_id": str(self.position_id),
            "symbol": self.symbol,
            "stop_price": str(self.stop_price),
            "quantity": self.quantity
        }


@dataclass(frozen=True)
class TakeProfitTriggered(RiskEvent):
    """Take-profit has been triggered"""
    portfolio_id: UUID
    position_id: UUID
    symbol: str
    target_price: Decimal
    quantity: int
    
    def _get_event_data(self):
        return {
            "portfolio_id": str(self.portfolio_id),
            "position_id": str(self.position_id),
            "symbol": self.symbol,
            "target_price": str(self.target_price),
            "quantity": self.quantity
        }


@dataclass(frozen=True)
class TrailingStopAdjusted(RiskEvent):
    """Trailing stop has been adjusted"""
    position_id: UUID
    symbol: str
    old_stop: Decimal
    new_stop: Decimal
    
    def _get_event_data(self):
        return {
            "position_id": str(self.position_id),
            "symbol": self.symbol,
            "old_stop": str(self.old_stop),
            "new_stop": str(self.new_stop)
        }


@dataclass(frozen=True)
class RiskMetricsCalculated(RiskEvent):
    """Risk metrics have been calculated"""
    portfolio_id: UUID
    var_95: Decimal
    var_99: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    beta: Decimal
    calculated_at: datetime
    
    def _get_event_data(self):
        return {
            "portfolio_id": str(self.portfolio_id),
            "var_95": str(self.var_95),
            "var_99": str(self.var_99),
            "sharpe_ratio": str(self.sharpe_ratio),
            "max_drawdown": str(self.max_drawdown),
            "beta": str(self.beta),
            "calculated_at": self.calculated_at.isoformat()
        }


@dataclass(frozen=True)
class CircuitBreakerActivated(RiskEvent):
    """Trading circuit breaker has been activated"""
    reason: str
    activated_at: datetime
    
    def _get_event_data(self):
        return {
            "reason": self.reason,
            "activated_at": self.activated_at.isoformat()
        }


@dataclass(frozen=True)
class EmergencyLiquidation(RiskEvent):
    """Emergency liquidation has been triggered"""
    portfolio_id: UUID
    reason: str
    positions_liquidated: int
    
    def _get_event_data(self):
        return {
            "portfolio_id": str(self.portfolio_id),
            "reason": self.reason,
            "positions_liquidated": self.positions_liquidated
        }