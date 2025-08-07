from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID


@dataclass(frozen=True)
class PortfolioEvent:
    """Base class for all portfolio domain events"""
    portfolio_id: UUID
    occurred_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            "event_type": self.__class__.__name__,
            "portfolio_id": str(self.portfolio_id),
            "occurred_at": self.occurred_at.isoformat(),
            **self._get_event_data()
        }
    
    def _get_event_data(self) -> Dict[str, Any]:
        """Override in subclasses to provide event-specific data"""
        return {}


@dataclass(frozen=True)
class PortfolioCreated(PortfolioEvent):
    """Event raised when a new portfolio is created"""
    name: str
    initial_cash: Decimal
    currency: str
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "initial_cash": str(self.initial_cash),
            "currency": self.currency
        }


@dataclass(frozen=True)
class FundsReserved(PortfolioEvent):
    """Event raised when funds are reserved for an order"""
    amount: Decimal
    order_id: UUID
    reason: str
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "amount": str(self.amount),
            "order_id": str(self.order_id),
            "reason": self.reason
        }


@dataclass(frozen=True)
class FundsReleased(PortfolioEvent):
    """Event raised when reserved funds are released"""
    amount: Decimal
    order_id: Optional[UUID]
    reason: str
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "amount": str(self.amount),
            "order_id": str(self.order_id) if self.order_id else None,
            "reason": self.reason
        }


@dataclass(frozen=True)
class PositionOpened(PortfolioEvent):
    """Event raised when a new position is opened"""
    symbol: str
    quantity: int
    entry_price: Decimal
    order_id: UUID
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": str(self.entry_price),
            "order_id": str(self.order_id)
        }


@dataclass(frozen=True)
class PositionClosed(PortfolioEvent):
    """Event raised when a position is fully closed"""
    symbol: str
    quantity: int
    exit_price: Decimal
    realized_pnl: Decimal
    order_id: UUID
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "exit_price": str(self.exit_price),
            "realized_pnl": str(self.realized_pnl),
            "order_id": str(self.order_id)
        }


@dataclass(frozen=True)
class PositionUpdated(PortfolioEvent):
    """Event raised when a position is partially filled or adjusted"""
    symbol: str
    old_quantity: int
    new_quantity: int
    price: Decimal
    order_id: UUID
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "old_quantity": self.old_quantity,
            "new_quantity": self.new_quantity,
            "price": str(self.price),
            "order_id": str(self.order_id)
        }


@dataclass(frozen=True)
class OrderPlacedFromPortfolio(PortfolioEvent):
    """Event raised when an order is placed from this portfolio"""
    order_id: UUID
    symbol: str
    quantity: int
    order_type: str
    reserved_funds: Decimal
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "order_id": str(self.order_id),
            "symbol": self.symbol,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "reserved_funds": str(self.reserved_funds)
        }


@dataclass(frozen=True)
class OrderFilledInPortfolio(PortfolioEvent):
    """Event raised when an order from this portfolio is filled"""
    order_id: UUID
    symbol: str
    quantity: int
    fill_price: Decimal
    actual_cost: Decimal
    commission: Decimal
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "order_id": str(self.order_id),
            "symbol": self.symbol,
            "quantity": self.quantity,
            "fill_price": str(self.fill_price),
            "actual_cost": str(self.actual_cost),
            "commission": str(self.commission)
        }


@dataclass(frozen=True)
class PortfolioRebalanceRequested(PortfolioEvent):
    """Event raised when portfolio rebalancing is requested"""
    target_allocations: Dict[str, Decimal]
    reason: str
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "target_allocations": {k: str(v) for k, v in self.target_allocations.items()},
            "reason": self.reason
        }


@dataclass(frozen=True)
class RiskLimitExceeded(PortfolioEvent):
    """Event raised when a risk limit is exceeded"""
    limit_type: str
    current_value: Decimal
    limit_value: Decimal
    action_required: str
    
    def _get_event_data(self) -> Dict[str, Any]:
        return {
            "limit_type": self.limit_type,
            "current_value": str(self.current_value),
            "limit_value": str(self.limit_value),
            "action_required": self.action_required
        }