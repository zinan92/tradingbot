"""
Order Contracts

Pydantic models for order-related data transfer objects.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class OrderSide(str, Enum):
    """Order side enumeration"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    """Order status enumeration"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderRequest(BaseModel):
    """Order submission request"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side (buy/sell)")
    order_type: OrderType = Field(..., description="Order type")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    price: Optional[Decimal] = Field(None, gt=0, description="Limit price for limit orders")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="Stop price for stop orders")
    time_in_force: str = Field("GTC", description="Time in force (GTC, IOC, FOK)")
    reduce_only: bool = Field(False, description="Reduce-only order flag")
    post_only: bool = Field(False, description="Post-only order flag")
    client_order_id: Optional[str] = Field(None, description="Client-assigned order ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class OrderResponse(BaseModel):
    """Order response from execution"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    order_id: str = Field(..., description="Exchange-assigned order ID")
    client_order_id: Optional[str] = Field(None, description="Client-assigned order ID")
    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side")
    order_type: OrderType = Field(..., description="Order type")
    status: OrderStatus = Field(..., description="Current order status")
    quantity: Decimal = Field(..., description="Original order quantity")
    filled_quantity: Decimal = Field(Decimal("0"), description="Filled quantity")
    remaining_quantity: Decimal = Field(..., description="Remaining quantity")
    price: Optional[Decimal] = Field(None, description="Order price")
    average_fill_price: Optional[Decimal] = Field(None, description="Average fill price")
    stop_price: Optional[Decimal] = Field(None, description="Stop trigger price")
    created_at: datetime = Field(..., description="Order creation time")
    updated_at: datetime = Field(..., description="Last update time")
    filled_at: Optional[datetime] = Field(None, description="Fill completion time")
    commission: Decimal = Field(Decimal("0"), description="Commission paid")
    commission_asset: Optional[str] = Field(None, description="Commission asset")


class OrderModification(BaseModel):
    """Order modification request"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    order_id: str = Field(..., description="Order ID to modify")
    quantity: Optional[Decimal] = Field(None, gt=0, description="New quantity")
    price: Optional[Decimal] = Field(None, gt=0, description="New limit price")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="New stop price")