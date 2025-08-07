"""
Order Type Value Object

Encapsulates order type with business rules and validation.
"""
from enum import Enum
from typing import Union, Optional

from pydantic import BaseModel, Field, ConfigDict


class OrderTypeEnum(str, Enum):
    """Enumeration of valid order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    
    @classmethod
    def has_value(cls, value: str) -> bool:
        """Check if a value is a valid order type"""
        return value in cls._value2member_map_


class OrderType(BaseModel):
    """
    Order Type Value Object
    
    Immutable representation of an order type with business rules.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutable
        str_strip_whitespace=True,
        use_enum_values=False
    )
    
    value: OrderTypeEnum = Field(
        ...,
        description="The order type enumeration"
    )
    
    def __init__(self, value: Union[str, OrderTypeEnum]):
        """
        Initialize OrderType with validation
        
        Args:
            value: Order type as string or enum
            
        Raises:
            ValueError: If order type is invalid
        """
        if isinstance(value, str):
            value = value.upper().strip()
            if not OrderTypeEnum.has_value(value):
                raise ValueError(
                    f"Invalid order type: {value}. "
                    f"Valid types: {', '.join([e.value for e in OrderTypeEnum])}"
                )
            value = OrderTypeEnum(value)
        elif not isinstance(value, OrderTypeEnum):
            raise ValueError(f"Invalid order type: {type(value)}")
        
        super().__init__(value=value)
    
    @classmethod
    def from_string(cls, value: str) -> "OrderType":
        """
        Factory method to create from string
        
        Args:
            value: Order type as string
            
        Returns:
            OrderType instance
        """
        return cls(value)
    
    @classmethod
    def market(cls) -> "OrderType":
        """Factory method for market order"""
        return cls(OrderTypeEnum.MARKET)
    
    @classmethod
    def limit(cls) -> "OrderType":
        """Factory method for limit order"""
        return cls(OrderTypeEnum.LIMIT)
    
    @classmethod
    def stop(cls) -> "OrderType":
        """Factory method for stop order"""
        return cls(OrderTypeEnum.STOP)
    
    @classmethod
    def stop_limit(cls) -> "OrderType":
        """Factory method for stop-limit order"""
        return cls(OrderTypeEnum.STOP_LIMIT)
    
    def is_market(self) -> bool:
        """Check if this is a market order"""
        return self.value == OrderTypeEnum.MARKET
    
    def is_limit(self) -> bool:
        """Check if this is a limit order"""
        return self.value == OrderTypeEnum.LIMIT
    
    def is_stop(self) -> bool:
        """Check if this is any type of stop order"""
        return self.value in [OrderTypeEnum.STOP, OrderTypeEnum.STOP_LIMIT, OrderTypeEnum.TRAILING_STOP]
    
    def requires_price(self) -> bool:
        """Check if this order type requires a price"""
        return self.value in [OrderTypeEnum.LIMIT, OrderTypeEnum.STOP, OrderTypeEnum.STOP_LIMIT]
    
    def requires_stop_price(self) -> bool:
        """Check if this order type requires a stop price"""
        return self.value in [OrderTypeEnum.STOP, OrderTypeEnum.STOP_LIMIT, OrderTypeEnum.TRAILING_STOP]
    
    def is_immediate(self) -> bool:
        """Check if this order executes immediately at market"""
        return self.value == OrderTypeEnum.MARKET
    
    def allows_partial_fill(self) -> bool:
        """Check if this order type allows partial fills"""
        # Most order types allow partial fills except special instructions
        return True
    
    def to_broker_format(self, broker: str) -> str:
        """
        Convert to broker-specific format
        
        Args:
            broker: Broker name (e.g., "BINANCE", "ALPACA")
            
        Returns:
            Broker-specific order type string
        """
        # Map to broker-specific formats
        broker_mappings = {
            "BINANCE": {
                OrderTypeEnum.MARKET: "MARKET",
                OrderTypeEnum.LIMIT: "LIMIT",
                OrderTypeEnum.STOP: "STOP_LOSS",
                OrderTypeEnum.STOP_LIMIT: "STOP_LOSS_LIMIT",
            },
            "ALPACA": {
                OrderTypeEnum.MARKET: "market",
                OrderTypeEnum.LIMIT: "limit",
                OrderTypeEnum.STOP: "stop",
                OrderTypeEnum.STOP_LIMIT: "stop_limit",
                OrderTypeEnum.TRAILING_STOP: "trailing_stop",
            }
        }
        
        broker_upper = broker.upper()
        if broker_upper in broker_mappings:
            return broker_mappings[broker_upper].get(self.value, self.value.value)
        
        return self.value.value
    
    def validate_with_price(self, price: Optional["Price"]) -> None:
        """
        Validate order type with price
        
        Args:
            price: Optional price value object
            
        Raises:
            InvalidOrderError: If validation fails
        """
        if self.requires_price() and price is None:
            raise InvalidOrderError(f"{self.value.value} orders require a price")
        
        if self.is_market() and price is not None:
            raise InvalidOrderError("Market orders should not have a price")
    
    def __str__(self) -> str:
        """String representation"""
        return self.value.value
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"OrderType(value={self.value.value})"
    
    def __eq__(self, other) -> bool:
        """Equality comparison"""
        if isinstance(other, OrderType):
            return self.value == other.value
        if isinstance(other, str):
            return self.value.value == other.upper()
        if isinstance(other, OrderTypeEnum):
            return self.value == other
        return False
    
    def __hash__(self) -> int:
        """Make hashable for use in sets/dicts"""
        return hash(self.value)


# Exceptions
class OrderTypeError(Exception):
    """Base exception for order type errors"""
    pass


class InvalidOrderError(OrderTypeError):
    """Raised when order configuration is invalid"""
    pass


class UnsupportedOrderTypeError(OrderTypeError):
    """Raised when order type is not supported"""
    pass