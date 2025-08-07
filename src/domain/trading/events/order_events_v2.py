"""
Domain Events for Trading Context with Pydantic v2

All domain events use Pydantic v2 for strict validation and immutability.
Events are the primary mechanism for communication between bounded contexts.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict


class DomainEvent(BaseModel):
    """
    Base class for all domain events with Pydantic v2
    
    Immutable events that capture state changes in the domain.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Events are immutable
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
            UUID: lambda v: str(v)
        }
    )
    
    event_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this event instance"
    )
    
    aggregate_id: UUID = Field(
        ...,
        description="ID of the aggregate that raised this event"
    )
    
    occurred_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the event occurred"
    )
    
    version: int = Field(
        default=1,
        description="Event schema version for compatibility"
    )
    
    correlation_id: Optional[UUID] = Field(
        None,
        description="ID to correlate related events across boundaries"
    )
    
    causation_id: Optional[UUID] = Field(
        None,
        description="ID of the command/event that caused this event"
    )
    
    metadata: dict = Field(
        default_factory=dict,
        description="Additional context or debugging information"
    )
    
    @property
    def event_type(self) -> str:
        """Get the event type name"""
        return self.__class__.__name__
    
    def to_dict(self) -> dict:
        """Convert event to dictionary for serialization"""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: dict) -> "DomainEvent":
        """Create event from dictionary"""
        return cls.model_validate(data)


# Order Events

class OrderPlaced(DomainEvent):
    """Event raised when an order is placed"""
    
    order_id: UUID = Field(
        ...,
        description="Unique identifier for the order",
        alias="aggregate_id"
    )
    
    portfolio_id: UUID = Field(
        ...,
        description="ID of the portfolio that placed the order"
    )
    
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Trading symbol"
    )
    
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Order quantity"
    )
    
    order_type: str = Field(
        ...,
        description="Type of order (MARKET, LIMIT, etc.)"
    )
    
    price: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Order price for limit orders"
    )
    
    side: str = Field(
        default="BUY",
        description="Order side (BUY or SELL)"
    )
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate and normalize symbol"""
        return v.strip().upper()
    
    @field_validator('order_type')
    @classmethod
    def validate_order_type(cls, v: str) -> str:
        """Validate order type"""
        valid_types = ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]
        v = v.upper()
        if v not in valid_types:
            raise ValueError(f"Invalid order type: {v}")
        return v


class OrderFilled(DomainEvent):
    """Event raised when an order is completely filled"""
    
    order_id: UUID = Field(
        ...,
        description="Order that was filled",
        alias="aggregate_id"
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol"
    )
    
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Filled quantity"
    )
    
    fill_price: Decimal = Field(
        ...,
        gt=0,
        description="Execution price"
    )
    
    broker_order_id: str = Field(
        ...,
        description="Broker's order identifier"
    )
    
    filled_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of fill"
    )
    
    commission: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Trading commission"
    )
    
    @field_validator('quantity', 'fill_price')
    @classmethod
    def validate_positive_decimal(cls, v: Decimal) -> Decimal:
        """Ensure values are positive"""
        if v <= 0:
            raise ValueError(f"Value must be positive: {v}")
        return v


class OrderPartiallyFilled(DomainEvent):
    """Event raised when an order is partially filled"""
    
    order_id: UUID = Field(
        ...,
        description="Order that was partially filled",
        alias="aggregate_id"
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol"
    )
    
    filled_quantity: Decimal = Field(
        ...,
        gt=0,
        description="Quantity filled in this execution"
    )
    
    remaining_quantity: Decimal = Field(
        ...,
        ge=0,
        description="Quantity still remaining"
    )
    
    fill_price: Decimal = Field(
        ...,
        gt=0,
        description="Price of this fill"
    )
    
    total_filled: Decimal = Field(
        ...,
        gt=0,
        description="Total quantity filled so far"
    )
    
    broker_order_id: str = Field(
        ...,
        description="Broker's order identifier"
    )
    
    average_fill_price: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Average price of all fills"
    )


class OrderCancelled(DomainEvent):
    """Event raised when an order is cancelled by user"""
    
    order_id: UUID = Field(
        ...,
        description="Order that was cancelled",
        alias="aggregate_id"
    )
    
    portfolio_id: UUID = Field(
        ...,
        description="Portfolio that owned the order"
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol"
    )
    
    cancelled_quantity: Decimal = Field(
        ...,
        ge=0,
        description="Quantity that was cancelled"
    )
    
    reason: str = Field(
        default="User requested cancellation",
        description="Cancellation reason"
    )
    
    cancelled_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Cancellation timestamp"
    )


class OrderRejected(DomainEvent):
    """Event raised when an order is rejected by broker"""
    
    order_id: UUID = Field(
        ...,
        description="Order that was rejected",
        alias="aggregate_id"
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol"
    )
    
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Attempted order quantity"
    )
    
    reason: str = Field(
        ...,
        description="Rejection reason from broker"
    )
    
    rejected_by: str = Field(
        default="BROKER",
        description="System that rejected the order"
    )
    
    rejected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Rejection timestamp"
    )


class OrderExpired(DomainEvent):
    """Event raised when an order expires"""
    
    order_id: UUID = Field(
        ...,
        description="Order that expired",
        alias="aggregate_id"
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol"
    )
    
    unfilled_quantity: Decimal = Field(
        ...,
        ge=0,
        description="Quantity that was not filled"
    )
    
    expiry_type: str = Field(
        ...,
        description="Type of expiry (TIME, DAY, GTC, etc.)"
    )
    
    expired_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Expiration timestamp"
    )


# Portfolio Events

class PortfolioFundsReserved(DomainEvent):
    """Event raised when funds are reserved for an order"""
    
    portfolio_id: UUID = Field(
        ...,
        description="Portfolio that reserved funds",
        alias="aggregate_id"
    )
    
    order_id: UUID = Field(
        ...,
        description="Order that funds are reserved for"
    )
    
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Amount reserved"
    )
    
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="Currency of reserved funds"
    )
    
    available_balance: Decimal = Field(
        ...,
        ge=0,
        description="Remaining available balance"
    )


class PortfolioFundsReleased(DomainEvent):
    """Event raised when reserved funds are released"""
    
    portfolio_id: UUID = Field(
        ...,
        description="Portfolio that released funds",
        alias="aggregate_id"
    )
    
    order_id: UUID = Field(
        ...,
        description="Order that funds were reserved for"
    )
    
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Amount released"
    )
    
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="Currency of released funds"
    )
    
    reason: str = Field(
        ...,
        description="Reason for release (cancelled, expired, etc.)"
    )


class PositionOpened(DomainEvent):
    """Event raised when a new position is opened"""
    
    portfolio_id: UUID = Field(
        ...,
        description="Portfolio that opened position",
        alias="aggregate_id"
    )
    
    position_id: UUID = Field(
        default_factory=uuid4,
        description="Unique position identifier"
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol"
    )
    
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Position size"
    )
    
    entry_price: Decimal = Field(
        ...,
        gt=0,
        description="Average entry price"
    )
    
    side: str = Field(
        default="LONG",
        description="Position side (LONG or SHORT)"
    )
    
    opened_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Position open timestamp"
    )


class PositionClosed(DomainEvent):
    """Event raised when a position is closed"""
    
    portfolio_id: UUID = Field(
        ...,
        description="Portfolio that closed position",
        alias="aggregate_id"
    )
    
    position_id: UUID = Field(
        ...,
        description="Position that was closed"
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol"
    )
    
    quantity: Decimal = Field(
        ...,
        gt=0,
        description="Position size closed"
    )
    
    entry_price: Decimal = Field(
        ...,
        gt=0,
        description="Average entry price"
    )
    
    exit_price: Decimal = Field(
        ...,
        gt=0,
        description="Average exit price"
    )
    
    realized_pnl: Decimal = Field(
        ...,
        description="Realized profit/loss"
    )
    
    closed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Position close timestamp"
    )


class PositionUpdated(DomainEvent):
    """Event raised when a position is updated (partial fill, etc.)"""
    
    portfolio_id: UUID = Field(
        ...,
        description="Portfolio that owns position",
        alias="aggregate_id"
    )
    
    position_id: UUID = Field(
        ...,
        description="Position that was updated"
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol"
    )
    
    old_quantity: Decimal = Field(
        ...,
        ge=0,
        description="Previous position size"
    )
    
    new_quantity: Decimal = Field(
        ...,
        gt=0,
        description="New position size"
    )
    
    old_average_price: Decimal = Field(
        ...,
        gt=0,
        description="Previous average price"
    )
    
    new_average_price: Decimal = Field(
        ...,
        gt=0,
        description="New average price"
    )
    
    update_reason: str = Field(
        ...,
        description="Reason for update (fill, adjustment, etc.)"
    )


# Event Factory Functions

def create_order_placed(
    order_id: UUID,
    portfolio_id: UUID,
    symbol: str,
    quantity: Decimal,
    order_type: str,
    price: Optional[Decimal] = None,
    **kwargs
) -> OrderPlaced:
    """Factory function to create OrderPlaced event"""
    return OrderPlaced(
        aggregate_id=order_id,
        order_id=order_id,
        portfolio_id=portfolio_id,
        symbol=symbol,
        quantity=quantity,
        order_type=order_type,
        price=price,
        **kwargs
    )


def create_order_filled(
    order_id: UUID,
    symbol: str,
    quantity: Decimal,
    fill_price: Decimal,
    broker_order_id: str,
    **kwargs
) -> OrderFilled:
    """Factory function to create OrderFilled event"""
    return OrderFilled(
        aggregate_id=order_id,
        order_id=order_id,
        symbol=symbol,
        quantity=quantity,
        fill_price=fill_price,
        broker_order_id=broker_order_id,
        **kwargs
    )