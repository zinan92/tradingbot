from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID, uuid4
import logging

from .order import Order
from ..events.portfolio_events import (
    PortfolioCreated,
    FundsReserved,
    FundsReleased,
    PositionOpened,
    PositionClosed,
    PositionUpdated,
    OrderPlacedFromPortfolio,
    OrderFilledInPortfolio
)

logger = logging.getLogger(__name__)


@dataclass
class Portfolio:
    """
    Portfolio Aggregate Root
    
    Manages trading portfolio with cash balance and positions.
    Enforces business rules around fund availability and order placement.
    """
    id: UUID
    name: str
    available_cash: Decimal  # TODO: Replace with Money value object
    reserved_cash: Decimal = field(default_factory=lambda: Decimal("0"))
    currency: str = "USD"
    positions: Dict[str, int] = field(default_factory=dict)  # symbol -> quantity
    
    # Event sourcing support
    _events: List = field(default_factory=list, init=False)
    
    @classmethod
    def create(cls, name: str, initial_cash: Decimal, currency: str = "USD"):
        """Factory method to create a new portfolio"""
        portfolio_id = uuid4()
        
        if initial_cash < 0:
            raise InvalidInitialCashError("Initial cash cannot be negative")
        
        portfolio = cls(
            id=portfolio_id,
            name=name,
            available_cash=initial_cash,
            currency=currency
        )
        
        # Record domain event
        event = PortfolioCreated(
            portfolio_id=portfolio_id,
            name=name,
            initial_cash=initial_cash,
            currency=currency,
            occurred_at=datetime.utcnow()
        )
        portfolio._add_event(event)
        
        return portfolio
    
    def check_sufficient_funds(self, amount: Decimal) -> bool:
        """
        Check if portfolio has sufficient available funds
        
        Returns True if funds are available, False otherwise
        """
        # TODO: When using Money value object, check currency matches
        return self.available_cash >= amount
    
    def reserve_funds(self, amount: Decimal) -> None:
        """
        Reserve funds for a pending order
        
        Business Rule: Cannot reserve more than available cash
        """
        if amount <= 0:
            raise InvalidAmountError("Reserve amount must be positive")
        
        if not self.check_sufficient_funds(amount):
            raise InsufficientFundsError(
                f"Cannot reserve {amount} {self.currency}. "
                f"Available: {self.available_cash} {self.currency}"
            )
        
        self.available_cash -= amount
        self.reserved_cash += amount
        
        # Record domain event
        event = FundsReserved(
            portfolio_id=self.id,
            amount=amount,
            order_id=UUID(int=0),  # Will be updated when order is created
            reason="Order placement",
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
    
    def release_reserved_funds(self, amount: Decimal) -> None:
        """
        Release previously reserved funds (e.g., when order is cancelled)
        """
        if amount <= 0:
            raise InvalidAmountError("Release amount must be positive")
        
        if amount > self.reserved_cash:
            raise InvalidAmountError(
                f"Cannot release {amount} {self.currency}. "
                f"Reserved: {self.reserved_cash} {self.currency}"
            )
        
        self.reserved_cash -= amount
        self.available_cash += amount
        
        # Record domain event
        event = FundsReleased(
            portfolio_id=self.id,
            amount=amount,
            order_id=None,
            reason="Order cancelled or funds released",
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
    
    def place_order(self, 
                   symbol: str,           # TODO: Symbol
                   quantity: int,         # TODO: Quantity
                   order_type: str,       # TODO: OrderType
                   price: Optional[float] = None) -> Order:  # TODO: Optional[Money]
        """
        Place a new order from this portfolio
        
        Business Rules:
        - Must have sufficient funds for the order
        - Reserves funds for pending orders
        """
        # Calculate required funds
        # TODO: Use proper value objects and calculations
        if order_type == "MARKET":
            # For market orders, estimate with a buffer (e.g., 5% above current price)
            # In real implementation, would fetch current market price
            estimated_price = 100.0  # Placeholder
            required_funds = Decimal(str(estimated_price * quantity * 1.05))
        else:  # LIMIT order
            if not price:
                raise InvalidOrderError("Limit orders require a price")
            required_funds = Decimal(str(price * quantity))
        
        # Check and reserve funds
        if not self.check_sufficient_funds(required_funds):
            raise InsufficientFundsError(
                f"Insufficient funds for order. Required: {required_funds} {self.currency}, "
                f"Available: {self.available_cash} {self.currency}"
            )
        
        # Reserve the funds
        self.reserve_funds(required_funds)
        
        # Create the order
        order = Order.create(
            symbol=symbol,
            quantity=quantity,
            order_type=order_type,
            price=price
        )
        
        # Record domain event
        event = OrderPlacedFromPortfolio(
            portfolio_id=self.id,
            order_id=order.id,
            symbol=symbol,
            quantity=quantity,
            order_type=order_type,
            reserved_funds=required_funds,
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
        
        return order
    
    def add_position(self, symbol: str, quantity: int) -> None:
        """Add or update a position when an order is filled"""
        if quantity <= 0:
            raise InvalidAmountError("Position quantity must be positive")
        
        if symbol in self.positions:
            self.positions[symbol] += quantity
        else:
            self.positions[symbol] = quantity
        
        # Record domain event
        old_quantity = self.positions.get(symbol, 0)
        event = PositionUpdated(
            portfolio_id=self.id,
            symbol=symbol,
            old_quantity=old_quantity,
            new_quantity=old_quantity + quantity,
            price=Decimal("0"),  # Will be set by caller with actual price
            order_id=UUID(int=0),  # Will be set by caller
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
    
    def get_position(self, symbol: str) -> int:
        """Get current position for a symbol"""
        return self.positions.get(symbol, 0)
    
    def complete_order_fill(self, 
                           symbol: str,
                           quantity: int,
                           fill_price: Decimal,
                           order_id) -> None:
        """
        Complete an order fill by adjusting reserved/spent funds
        
        When an order is filled:
        1. The actual cost is calculated from fill_price
        2. Reserved funds are converted to spent funds
        3. Any excess reserved funds are released back to available
        
        Args:
            symbol: The symbol that was filled
            quantity: Number of shares filled
            fill_price: Actual execution price
            order_id: The order that was filled
        """
        actual_cost = fill_price * Decimal(str(quantity))
        
        # We had reserved funds for this order
        # Now we need to adjust for the actual fill price
        # Assuming we reserved the maximum expected cost
        
        # For simplicity, we'll assume all reserved funds were for this order
        # In production, we'd track reserved funds per order
        if self.reserved_cash > 0:
            # Release all reserved funds first
            released = self.reserved_cash
            self.reserved_cash = Decimal("0")
            self.available_cash += released
            
            # Now deduct the actual cost
            if self.available_cash < actual_cost:
                raise InsufficientFundsError(
                    f"Insufficient funds for fill. Cost: {actual_cost}, Available: {self.available_cash}"
                )
            
            self.available_cash -= actual_cost
            
            # Record event
            event = OrderFilledInPortfolio(
                portfolio_id=self.id,
                order_id=order_id,
                symbol=symbol,
                quantity=quantity,
                fill_price=fill_price,
                actual_cost=actual_cost,
                commission=Decimal("0"),  # TODO: Add commission tracking
                occurred_at=datetime.utcnow()
            )
            self._add_event(event)
            
            logger.info(
                f"Portfolio {self.id}: Order filled for {quantity} {symbol} @ {fill_price}. "
                f"Cost: {actual_cost}, Available cash: {self.available_cash}"
            )
    
    def get_total_value(self) -> Decimal:
        """
        Calculate total portfolio value
        TODO: Implement with market prices
        """
        # This would need market prices to calculate properly
        # For now, return cash only
        return self.available_cash + self.reserved_cash
    
    def pull_events(self) -> List:
        """Return and clear domain events"""
        events = self._events.copy()
        self._events.clear()
        return events
    
    def _add_event(self, event) -> None:
        """Add a domain event to be published"""
        self._events.append(event)


# Domain Exceptions
class PortfolioDomainError(Exception):
    """Base exception for Portfolio domain errors"""
    pass


class InsufficientFundsError(PortfolioDomainError):
    """Raised when portfolio has insufficient funds for an operation"""
    pass


class InvalidAmountError(PortfolioDomainError):
    """Raised when an invalid amount is provided"""
    pass


class InvalidInitialCashError(PortfolioDomainError):
    """Raised when initial cash is invalid"""
    pass


class InvalidOrderError(PortfolioDomainError):
    """Raised when order parameters are invalid"""
    pass