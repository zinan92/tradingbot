from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for all domain events
    
    Provides common fields for event sourcing and correlation:
    - event_id: Unique identifier for this event
    - correlation_id: ID to correlate related events across boundaries
    - timestamp: When the event occurred
    - aggregate_id: The aggregate that generated this event
    - version: Event schema version for compatibility
    """
    
    def __post_init__(self):
        """Ensure fields are properly initialized"""
        # Generate defaults if not set
        if not hasattr(self, 'event_id'):
            object.__setattr__(self, "event_id", uuid4())
        if not hasattr(self, 'correlation_id'):
            object.__setattr__(self, "correlation_id", uuid4())
        if not hasattr(self, 'timestamp'):
            object.__setattr__(self, "timestamp", datetime.utcnow())
        if not hasattr(self, 'version'):
            object.__setattr__(self, "version", "1.0")
        
        # If aggregate_id not set, try to use order_id if available
        if not hasattr(self, 'aggregate_id') or getattr(self, 'aggregate_id', None) == UUID(int=0):
            if hasattr(self, 'order_id'):
                object.__setattr__(self, "aggregate_id", self.order_id)
            else:
                object.__setattr__(self, "aggregate_id", UUID(int=0))
    
    @property
    def event_name(self) -> str:
        """Return the event name for routing/handling"""
        return f"{self.__class__.__module__}.{self.__class__.__name__}"
    
    def to_dict(self) -> dict:
        """Base dictionary representation"""
        return {
            "event_id": str(getattr(self, 'event_id', uuid4())),
            "correlation_id": str(getattr(self, 'correlation_id', uuid4())),
            "timestamp": getattr(self, 'timestamp', datetime.utcnow()).isoformat(),
            "aggregate_id": str(getattr(self, 'aggregate_id', UUID(int=0))),
            "version": getattr(self, 'version', "1.0"),
            "event_name": self.event_name,
        }


@dataclass(frozen=True)
class OrderPlaced(DomainEvent):
    """
    Event raised when a new order is placed
    
    Contains all relevant information about the order placement
    for downstream systems and event handlers.
    """
    order_id: UUID
    portfolio_id: UUID
    symbol: str
    quantity: int
    order_type: str
    placed_by: Optional[UUID] = None  # User who placed the order
    price: Optional[Decimal] = None
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID = field(default=UUID(int=0))
    version: str = field(default="1.0")
    
    @property
    def event_name(self) -> str:
        return "order.placed"
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": str(self.order_id),
            "portfolio_id": str(self.portfolio_id),
            "symbol": self.symbol,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "placed_by": str(self.placed_by) if self.placed_by else None,
            "price": str(self.price) if self.price else None,
        })
        return base_dict


@dataclass(frozen=True)
class OrderCancelled(DomainEvent):
    """
    Event raised when an order is cancelled
    
    Includes comprehensive information about the cancellation
    for audit trail and downstream processing.
    """
    order_id: UUID
    reason: str
    cancelled_at: datetime
    cancelled_by: UUID  # User ID who cancelled the order
    original_quantity: int
    symbol: str
    order_type: Optional[str] = None
    unfilled_quantity: Optional[int] = None  # How much was not filled
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID = field(default=UUID(int=0))
    version: str = field(default="1.0")
    
    @property
    def event_name(self) -> str:
        return "order.cancelled"
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": str(self.order_id),
            "reason": self.reason,
            "cancelled_at": self.cancelled_at.isoformat(),
            "cancelled_by": str(self.cancelled_by),
            "original_quantity": self.original_quantity,
            "symbol": self.symbol,
            "order_type": self.order_type,
            "unfilled_quantity": self.unfilled_quantity,
        })
        return base_dict


@dataclass(frozen=True)
class OrderFilled(DomainEvent):
    """
    Event raised when an order is filled by the broker
    """
    order_id: UUID
    symbol: str
    quantity: int
    fill_price: Decimal
    filled_at: datetime = field(default_factory=datetime.utcnow)
    broker_order_id: Optional[str] = None
    filled_by: Optional[UUID] = None  # System/broker that filled the order
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID = field(default=UUID(int=0))
    version: str = field(default="1.0")
    
    @property
    def event_name(self) -> str:
        return "order.filled"
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": str(self.order_id),
            "symbol": self.symbol,
            "quantity": self.quantity,
            "fill_price": str(self.fill_price),
            "filled_at": self.filled_at.isoformat(),
            "broker_order_id": self.broker_order_id,
            "filled_by": str(self.filled_by) if self.filled_by else None,
        })
        return base_dict


@dataclass(frozen=True)
class OrderRejected(DomainEvent):
    """
    Event raised when an order is rejected by the broker
    """
    order_id: UUID
    reason: str
    symbol: str
    quantity: int
    rejected_at: datetime = field(default_factory=datetime.utcnow)
    rejected_by: Optional[str] = None  # Broker/system that rejected
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID = field(default=UUID(int=0))
    version: str = field(default="1.0")
    
    @property
    def event_name(self) -> str:
        return "order.rejected"
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": str(self.order_id),
            "reason": self.reason,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "rejected_at": self.rejected_at.isoformat(),
            "rejected_by": self.rejected_by,
        })
        return base_dict


@dataclass(frozen=True)
class OrderFullyCancelled(DomainEvent):
    """
    Event raised when broker confirms order cancellation
    
    This represents the final confirmation that an order has been
    successfully cancelled on the broker's side.
    """
    order_id: UUID
    symbol: str
    quantity: int
    confirmed_at: datetime
    broker_order_id: Optional[str] = None
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID = field(default=UUID(int=0))
    version: str = field(default="1.0")
    
    @property
    def event_name(self) -> str:
        return "order.fully_cancelled"
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": str(self.order_id),
            "symbol": self.symbol,
            "quantity": self.quantity,
            "confirmed_at": self.confirmed_at.isoformat(),
            "broker_order_id": self.broker_order_id,
        })
        return base_dict


@dataclass(frozen=True)
class OrderCancelledByBroker(DomainEvent):
    """
    Event raised when broker confirms order cancellation
    
    This is an async notification from the broker that the
    cancellation has been completed on their side.
    """
    order_id: UUID
    broker_order_id: str
    cancelled_at: datetime
    reason: Optional[str] = "Cancelled by broker"
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID = field(default=UUID(int=0))
    version: str = field(default="1.0")
    
    @property
    def event_name(self) -> str:
        return "order.cancelled_by_broker"
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": str(self.order_id),
            "broker_order_id": self.broker_order_id,
            "cancelled_at": self.cancelled_at.isoformat(),
            "reason": self.reason,
        })
        return base_dict


@dataclass(frozen=True)
class OrderPartiallyFilled(DomainEvent):
    """
    Event raised when an order is partially filled
    """
    order_id: UUID
    symbol: str
    filled_quantity: int
    remaining_quantity: int
    fill_price: Decimal
    total_filled: int  # Total quantity filled so far
    broker_order_id: Optional[str] = None
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    aggregate_id: UUID = field(default=UUID(int=0))
    version: str = field(default="1.0")
    
    @property
    def event_name(self) -> str:
        return "order.partially_filled"
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": str(self.order_id),
            "symbol": self.symbol,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "fill_price": str(self.fill_price),
            "total_filled": self.total_filled,
            "broker_order_id": self.broker_order_id,
        })
        return base_dict