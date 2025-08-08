"""
Order Side Value Object

Represents the side of a trading order (BUY or SELL).
Uses Pydantic v2 for validation and type safety.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import ClassVar


class OrderSideEnum(str, Enum):
    """Enumeration for order sides"""
    BUY = "BUY"
    SELL = "SELL"


class Side(BaseModel):
    """
    Order Side Value Object
    
    Immutable representation of order side (BUY/SELL).
    Enforces business rules around order direction.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Make immutable
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    value: OrderSideEnum = Field(..., description="Order side (BUY or SELL)")
    
    def __init__(self, value: str):
        """
        Initialize Side with validation
        
        Args:
            value: The side value ("BUY" or "SELL")
            
        Raises:
            ValueError: If side is invalid
        """
        # Convert string to enum
        try:
            if isinstance(value, OrderSideEnum):
                enum_value = value
            else:
                enum_value = OrderSideEnum(value.upper())
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid side: {value}. Must be BUY or SELL")
        
        super().__init__(value=enum_value)
    
    @field_validator('value')
    @classmethod
    def validate_side(cls, v: OrderSideEnum) -> OrderSideEnum:
        """Validate side value"""
        if v not in OrderSideEnum:
            raise ValueError(f"Invalid side: {v}")
        return v
    
    def is_buy(self) -> bool:
        """Check if this is a buy order"""
        return self.value == OrderSideEnum.BUY
    
    def is_sell(self) -> bool:
        """Check if this is a sell order"""
        return self.value == OrderSideEnum.SELL
    
    def opposite(self) -> "Side":
        """Get the opposite side"""
        if self.value == OrderSideEnum.BUY:
            return Side("SELL")
        else:
            return Side("BUY")
    
    def to_position_action(self) -> str:
        """
        Convert to position action description
        
        Returns:
            "LONG" for BUY, "SHORT" for SELL
        """
        if self.value == OrderSideEnum.BUY:
            return "LONG"
        else:
            return "SHORT"
    
    def calculate_cost(self, price: float, quantity: float) -> float:
        """
        Calculate the cost/proceeds of the order
        
        Args:
            price: Execution price
            quantity: Order quantity
            
        Returns:
            Negative for BUY (cash outflow), positive for SELL (cash inflow)
        """
        cost = price * quantity
        if self.value == OrderSideEnum.BUY:
            return -cost  # Negative for purchases
        else:
            return cost  # Positive for sales
    
    def __str__(self) -> str:
        """String representation"""
        return self.value.value
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"Side('{self.value.value}')"
    
    def __eq__(self, other) -> bool:
        """Equality comparison"""
        if not isinstance(other, Side):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Make Side hashable for use in sets/dicts"""
        return hash(self.value)
    
    @classmethod
    def from_string(cls, value: str) -> "Side":
        """Factory method to create Side from string"""
        return cls(value)
    
    @classmethod
    def buy(cls) -> "Side":
        """Factory method for BUY side"""
        return cls("BUY")
    
    @classmethod
    def sell(cls) -> "Side":
        """Factory method for SELL side"""
        return cls("SELL")


# Re-export for backward compatibility with futures position code
class PositionSide(Enum):
    """
    Position side for futures trading.
    
    Represents the direction of a futures position.
    """
    LONG = "LONG"    # Betting on price increase
    SHORT = "SHORT"  # Betting on price decrease
    BOTH = "BOTH"    # For hedge mode (Binance specific)
    
    def opposite(self) -> "PositionSide":
        """Get the opposite position side."""
        if self == PositionSide.LONG:
            return PositionSide.SHORT
        elif self == PositionSide.SHORT:
            return PositionSide.LONG
        else:
            raise ValueError("Cannot get opposite of BOTH position side")
    
    def to_order_side(self) -> str:
        """
        Convert position side to order side for opening positions.
        
        Returns:
            "BUY" for LONG positions, "SELL" for SHORT positions
        """
        if self == PositionSide.LONG:
            return "BUY"
        elif self == PositionSide.SHORT:
            return "SELL"
        else:
            raise ValueError("Cannot convert BOTH to order side")
    
    def closing_order_side(self) -> str:
        """
        Get the order side needed to close this position.
        
        Returns:
            "SELL" to close LONG positions, "BUY" to close SHORT positions
        """
        if self == PositionSide.LONG:
            return "SELL"
        elif self == PositionSide.SHORT:
            return "BUY"
        else:
            raise ValueError("Cannot get closing order side for BOTH")
    
    def is_profitable_move(self, entry_price: float, current_price: float) -> bool:
        """
        Check if price movement is profitable for this position.
        
        Args:
            entry_price: Price at which position was opened
            current_price: Current market price
            
        Returns:
            True if the price movement is profitable
        """
        if self == PositionSide.LONG:
            return current_price > entry_price
        elif self == PositionSide.SHORT:
            return current_price < entry_price
        else:
            return False
    
    def calculate_pnl_multiplier(self) -> int:
        """
        Get PnL calculation multiplier.
        
        Returns:
            1 for LONG (profit when price increases)
            -1 for SHORT (profit when price decreases)
        """
        if self == PositionSide.LONG:
            return 1
        elif self == PositionSide.SHORT:
            return -1
        else:
            raise ValueError("Cannot calculate PnL multiplier for BOTH")
    
    @classmethod
    def from_order_side(cls, order_side: str, reduce_only: bool = False) -> "PositionSide":
        """
        Infer position side from order side.
        
        Args:
            order_side: "BUY" or "SELL"
            reduce_only: If True, infer the position being closed
            
        Returns:
            PositionSide enum value
        """
        order_side = order_side.upper()
        
        if reduce_only:
            # Reduce-only orders close opposite positions
            if order_side == "BUY":
                return PositionSide.SHORT  # Buying to close short
            elif order_side == "SELL":
                return PositionSide.LONG   # Selling to close long
        else:
            # Regular orders open positions
            if order_side == "BUY":
                return PositionSide.LONG   # Buying to open long
            elif order_side == "SELL":
                return PositionSide.SHORT  # Selling to open short
        
        raise ValueError(f"Invalid order side: {order_side}")


@dataclass(frozen=True)
class FuturesPosition:
    """
    Futures Position Value Object
    
    Immutable representation of a futures position with PnL calculation.
    """
    symbol: str
    side: PositionSide
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    leverage: int = 1
    
    def calculate_pnl(self) -> Decimal:
        """
        Calculate unrealized PnL for the position.
        
        Returns:
            PnL amount (positive for profit, negative for loss)
        """
        price_diff = self.current_price - self.entry_price
        
        if self.side == PositionSide.LONG:
            # Long position: profit when price increases
            pnl = price_diff * Decimal(str(self.quantity))
        elif self.side == PositionSide.SHORT:
            # Short position: profit when price decreases
            pnl = -price_diff * Decimal(str(self.quantity))
        else:
            pnl = Decimal("0")
        
        return pnl
    
    def calculate_pnl_percentage(self) -> Decimal:
        """
        Calculate PnL as percentage of entry value.
        
        Returns:
            PnL percentage (e.g., 0.05 = 5% profit)
        """
        if self.entry_price == 0:
            return Decimal("0")
        
        pnl = self.calculate_pnl()
        entry_value = self.entry_price * Decimal(str(self.quantity))
        
        if entry_value == 0:
            return Decimal("0")
        
        return pnl / entry_value
    
    def calculate_roi(self) -> Decimal:
        """
        Calculate return on investment considering leverage.
        
        Returns:
            ROI percentage based on margin used
        """
        pnl_percentage = self.calculate_pnl_percentage()
        return pnl_percentage * Decimal(str(self.leverage))
    
    def get_position_value(self) -> Decimal:
        """Get current position value."""
        return self.current_price * Decimal(str(self.quantity))
    
    def get_initial_margin(self) -> Decimal:
        """Calculate initial margin required."""
        entry_value = self.entry_price * Decimal(str(self.quantity))
        return entry_value / Decimal(str(self.leverage))