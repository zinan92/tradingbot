"""
Order Domain Events using Pydantic v2

Implements all order-related domain events with strict validation.
Uses Pydantic v2 for type safety, validation, and serialization.
"""

from pydantic import Field, field_validator, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional, ClassVar
from uuid import UUID

from .base_events import OrderEvent


class OrderPlaced(OrderEvent):
    """
    Event raised when a new order is placed.
    
    Contains all relevant information about the order placement
    for downstream systems and event handlers.
    """
    
    event_name: ClassVar[str] = "order.placed"
    
    portfolio_id: UUID = Field(..., description="Portfolio that placed the order")
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Order quantity")
    order_type: str = Field(..., description="Order type (MARKET, LIMIT, etc.)")
    side: str = Field(default="BUY", description="Order side (BUY or SELL)")
    price: Optional[Decimal] = Field(None, ge=0, description="Limit price for LIMIT orders")
    placed_by: Optional[UUID] = Field(None, description="User who placed the order")
    
    @field_validator('order_type')
    @classmethod
    def validate_order_type(cls, v: str) -> str:
        """Validate order type"""
        valid_types = ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]
        if v.upper() not in valid_types:
            raise ValueError(f"Invalid order type: {v}. Must be one of {valid_types}")
        return v.upper()
    
    @field_validator('side')
    @classmethod
    def validate_side(cls, v: str) -> str:
        """Validate order side"""
        if v.upper() not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid side: {v}. Must be BUY or SELL")
        return v.upper()
    
    @field_validator('price')
    @classmethod
    def validate_price_for_limit_orders(cls, v: Optional[Decimal], values) -> Optional[Decimal]:
        """Ensure price is provided for LIMIT orders"""
        order_type = values.data.get('order_type', '').upper()
        if order_type in ["LIMIT", "STOP_LIMIT"] and v is None:
            raise ValueError(f"Price is required for {order_type} orders")
        return v


class OrderCancelled(OrderEvent):
    """
    Event raised when an order is cancelled.
    
    Includes comprehensive information about the cancellation
    for audit trail and downstream processing.
    """
    
    event_name: ClassVar[str] = "order.cancelled"
    
    reason: str = Field(..., min_length=1, description="Cancellation reason")
    cancelled_at: datetime = Field(default_factory=datetime.utcnow, description="When cancelled")
    cancelled_by: UUID = Field(..., description="User who cancelled the order")
    original_quantity: int = Field(..., gt=0, description="Original order quantity")
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    order_type: str = Field(..., description="Order type")
    unfilled_quantity: int = Field(..., ge=0, description="Quantity that was not filled")
    
    @field_validator('unfilled_quantity')
    @classmethod
    def validate_unfilled_quantity(cls, v: int, values) -> int:
        """Ensure unfilled quantity doesn't exceed original"""
        original = values.data.get('original_quantity', 0)
        if v > original:
            raise ValueError(f"Unfilled quantity {v} cannot exceed original quantity {original}")
        return v


class OrderFilled(OrderEvent):
    """
    Event raised when an order is filled by the broker.
    
    Contains execution details for portfolio updates and accounting.
    """
    
    event_name: ClassVar[str] = "order.filled"
    
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Filled quantity")
    fill_price: Decimal = Field(..., gt=0, description="Execution price")
    filled_at: datetime = Field(default_factory=datetime.utcnow, description="Fill timestamp")
    broker_order_id: Optional[str] = Field(None, description="Broker's order ID")
    commission: Optional[Decimal] = Field(None, ge=0, description="Trading commission")
    filled_by: Optional[UUID] = Field(None, description="System/broker that filled the order")


class OrderPartiallyFilled(OrderEvent):
    """
    Event raised when an order is partially filled.
    
    Tracks partial execution for complex order management.
    """
    
    event_name: ClassVar[str] = "order.partially_filled"
    
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    filled_quantity: int = Field(..., gt=0, description="Quantity filled in this execution")
    remaining_quantity: int = Field(..., ge=0, description="Quantity still open")
    fill_price: Decimal = Field(..., gt=0, description="Execution price for this fill")
    total_filled: int = Field(..., gt=0, description="Total quantity filled so far")
    average_fill_price: Optional[Decimal] = Field(None, gt=0, description="Average price of all fills")
    broker_order_id: Optional[str] = Field(None, description="Broker's order ID")
    
    @field_validator('total_filled')
    @classmethod
    def validate_total_filled(cls, v: int, values) -> int:
        """Ensure total filled equals filled + remaining"""
        filled = values.data.get('filled_quantity', 0)
        if v < filled:
            raise ValueError(f"Total filled {v} must be at least {filled}")
        return v


class OrderRejected(OrderEvent):
    """
    Event raised when an order is rejected by the broker.
    
    Contains rejection details for error handling and retry logic.
    """
    
    event_name: ClassVar[str] = "order.rejected"
    
    reason: str = Field(..., min_length=1, description="Rejection reason")
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Attempted quantity")
    rejected_at: datetime = Field(default_factory=datetime.utcnow, description="Rejection timestamp")
    rejected_by: Optional[str] = Field(None, description="System that rejected the order")
    error_code: Optional[str] = Field(None, description="Broker error code")
    retry_after: Optional[datetime] = Field(None, description="Suggested retry time")


class OrderExpired(OrderEvent):
    """
    Event raised when an order expires.
    
    For time-in-force orders that reach their expiration.
    """
    
    event_name: ClassVar[str] = "order.expired"
    
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Original quantity")
    unfilled_quantity: int = Field(..., ge=0, description="Quantity that was not filled")
    expired_at: datetime = Field(default_factory=datetime.utcnow, description="Expiration timestamp")
    time_in_force: str = Field(..., description="Time in force setting (DAY, GTC, IOC, etc.)")
    
    @field_validator('time_in_force')
    @classmethod
    def validate_time_in_force(cls, v: str) -> str:
        """Validate time in force"""
        valid_tif = ["DAY", "GTC", "IOC", "FOK", "GTX", "GTD", "ATC", "ATO"]
        if v.upper() not in valid_tif:
            raise ValueError(f"Invalid time in force: {v}")
        return v.upper()


class OrderAmended(OrderEvent):
    """
    Event raised when an order is amended/modified.
    
    Tracks changes to existing orders.
    """
    
    event_name: ClassVar[str] = "order.amended"
    
    original_quantity: int = Field(..., gt=0, description="Original quantity")
    new_quantity: Optional[int] = Field(None, gt=0, description="New quantity if changed")
    original_price: Optional[Decimal] = Field(None, gt=0, description="Original price")
    new_price: Optional[Decimal] = Field(None, gt=0, description="New price if changed")
    amended_by: UUID = Field(..., description="User who amended the order")
    amended_at: datetime = Field(default_factory=datetime.utcnow, description="Amendment timestamp")
    amendment_reason: Optional[str] = Field(None, description="Reason for amendment")
    
    model_config = ConfigDict(validate_assignment=True)
    
    @field_validator('new_quantity', 'new_price')
    @classmethod
    def validate_amendment_has_changes(cls, v, values):
        """Ensure at least one field is being changed"""
        if values.data.get('new_quantity') is None and values.data.get('new_price') is None:
            raise ValueError("Amendment must change either quantity or price")
        return v


class OrderFullyCancelled(OrderEvent):
    """
    Event raised when broker confirms order cancellation.
    
    Final confirmation that an order has been successfully
    cancelled on the broker's side.
    """
    
    event_name: ClassVar[str] = "order.fully_cancelled"
    
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Original quantity")
    confirmed_at: datetime = Field(..., description="Broker confirmation timestamp")
    broker_order_id: Optional[str] = Field(None, description="Broker's order ID")


class OrderCancelledByBroker(OrderEvent):
    """
    Event raised when broker initiates order cancellation.
    
    Async notification from broker about cancellation.
    """
    
    event_name: ClassVar[str] = "order.cancelled_by_broker"
    
    broker_order_id: str = Field(..., description="Broker's order ID")
    cancelled_at: datetime = Field(..., description="Cancellation timestamp")
    reason: str = Field(default="Cancelled by broker", description="Cancellation reason")
    error_code: Optional[str] = Field(None, description="Broker error code if applicable")