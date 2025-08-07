from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

# TODO: Import value objects when created
# from ..value_objects import OrderId, Symbol, Quantity, OrderType, Money

from ..events import OrderPlaced, OrderCancelled, OrderFilled


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED" 
    CANCELLED = "CANCELLED"
    CANCELLED_CONFIRMED = "CANCELLED_CONFIRMED"  # Broker has confirmed cancellation


@dataclass
class Order:
    """
    Order Aggregate Root
    
    Represents a trading order with its complete lifecycle.
    Enforces business rules around order state transitions.
    """
    id: UUID
    symbol: str          # TODO: Replace with Symbol value object
    quantity: int        # TODO: Replace with Quantity value object
    order_type: str      # TODO: Replace with OrderType value object
    price: Optional[float] = None  # TODO: Replace with Money value object
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None  # Track reason for cancellation
    broker_order_id: Optional[str] = None
    broker_confirmed_at: Optional[datetime] = None  # When broker confirmed cancellation
    
    # Event sourcing support
    _events: List = field(default_factory=list, init=False)
    
    @classmethod
    def create(cls, 
              symbol: str,          # TODO: Symbol
              quantity: int,        # TODO: Quantity  
              order_type: str,      # TODO: OrderType
              price: Optional[float] = None,  # TODO: Optional[Money]
              portfolio_id: Optional[UUID] = None):  # Portfolio that placed the order
        """Factory method to create a new order"""
        from decimal import Decimal
        
        order_id = uuid4()
        
        # Create new order
        order = cls(
            id=order_id,
            symbol=symbol,
            quantity=quantity, 
            order_type=order_type,
            price=price,
            status=OrderStatus.PENDING
        )
        
        # Create and record domain event
        event = OrderPlaced(
            order_id=order_id,
            portfolio_id=portfolio_id or UUID(int=0),  # Use null UUID if not provided
            symbol=symbol,
            quantity=quantity,
            order_type=order_type,
            price=Decimal(str(price)) if price else None
        )
        order._add_event(event)
        
        return order
    
    def cancel(self, reason: Optional[str] = None, cancelled_by: Optional[UUID] = None) -> OrderCancelled:
        """
        Cancel the order if business rules allow
        
        Args:
            reason: Optional reason for cancellation
            cancelled_by: Optional UUID of user who cancelled the order
            
        Returns:
            OrderCancelled event
            
        Business Rules:
            - Cannot cancel an order that is already filled
            - Cannot cancel an order that is already cancelled
        """
        # Check if order can be cancelled
        if self.status == OrderStatus.FILLED:
            raise CannotCancelFilledOrderError(
                f"Order {self.id} is already filled and cannot be cancelled"
            )
        
        if self.status == OrderStatus.CANCELLED:
            raise OrderAlreadyCancelledError(
                f"Order {self.id} is already cancelled"
            )
        
        # Update order state
        self.status = OrderStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancellation_reason = reason or "No reason provided"
        
        # Create and record domain event with all required fields
        event = OrderCancelled(
            order_id=self.id,
            reason=reason or "No reason provided",
            cancelled_at=self.cancelled_at,
            cancelled_by=cancelled_by or UUID(int=0),  # Use null UUID if not provided
            original_quantity=self.quantity,
            symbol=self.symbol,
            order_type=self.order_type,
            unfilled_quantity=self.quantity  # Assuming no partial fills for now
        )
        self._add_event(event)
        
        return event
    
    def fill(self, filled_at: Optional[datetime] = None, fill_price: Optional[float] = None) -> OrderFilled:
        """
        Mark the order as filled
        
        Args:
            filled_at: Optional timestamp of fill
            fill_price: Optional actual fill price
            
        Returns:
            OrderFilled event
            
        Business Rules:
            - Can only fill pending orders
            - Cannot fill cancelled orders
        """
        from decimal import Decimal
        
        if self.status == OrderStatus.FILLED:
            raise OrderAlreadyFilledError(f"Order {self.id} is already filled")
        
        if self.status == OrderStatus.CANCELLED:
            raise CannotFillCancelledOrderError(f"Order {self.id} is cancelled and cannot be filled")
        
        # Update order state
        self.status = OrderStatus.FILLED
        self.filled_at = filled_at or datetime.utcnow()
        
        # Create and record domain event
        event = OrderFilled(
            order_id=self.id,
            symbol=self.symbol,
            quantity=self.quantity,
            fill_price=Decimal(str(fill_price or self.price or 0)),
            broker_order_id=self.broker_order_id
        )
        self._add_event(event)
        
        return event
    
    def set_broker_order_id(self, broker_order_id: str) -> None:
        """Set the broker's order ID after submission"""
        self.broker_order_id = broker_order_id
    
    def is_pending(self) -> bool:
        """Check if order is still pending"""
        return self.status == OrderStatus.PENDING
    
    def is_filled(self) -> bool:
        """Check if order has been filled"""
        return self.status == OrderStatus.FILLED
    
    def is_cancelled(self) -> bool:
        """Check if order has been cancelled"""
        return self.status in [OrderStatus.CANCELLED, OrderStatus.CANCELLED_CONFIRMED]
    
    def confirm_cancellation(self, confirmation_time: Optional[datetime] = None) -> None:
        """
        Confirm that broker has cancelled the order
        
        This is called when we receive async confirmation from the broker
        that the cancellation has been completed on their side.
        
        Args:
            confirmation_time: When the broker confirmed cancellation
            
        Raises:
            OrderDomainError: If order is not in CANCELLED state
        """
        if self.status != OrderStatus.CANCELLED:
            raise OrderDomainError(
                f"Cannot confirm cancellation for order in {self.status} state"
            )
        
        self.status = OrderStatus.CANCELLED_CONFIRMED
        self.broker_confirmed_at = confirmation_time or datetime.utcnow()
        
        # Emit OrderFullyCancelled event
        from ..events import OrderFullyCancelled
        event = OrderFullyCancelled(
            order_id=self.id,
            symbol=self.symbol,
            quantity=self.quantity,
            confirmed_at=self.broker_confirmed_at,
            broker_order_id=self.broker_order_id
        )
        self._add_event(event)
    
    def pull_events(self) -> List:
        """Return and clear domain events (for event sourcing)"""
        events = self._events.copy()
        self._events.clear()
        return events
    
    def _add_event(self, event) -> None:
        """Add a domain event to be published"""
        self._events.append(event)


# Domain Exceptions (Business Rule Violations)
class OrderDomainError(Exception):
    """Base exception for Order domain errors"""
    pass


class CannotCancelFilledOrderError(OrderDomainError):
    """Raised when trying to cancel an already filled order"""
    pass


class OrderAlreadyCancelledError(OrderDomainError):
    """Raised when trying to cancel an already cancelled order"""
    pass


class OrderAlreadyFilledError(OrderDomainError):
    """Raised when trying to fill an already filled order"""
    pass


class CannotFillCancelledOrderError(OrderDomainError):
    """Raised when trying to fill a cancelled order"""
    pass