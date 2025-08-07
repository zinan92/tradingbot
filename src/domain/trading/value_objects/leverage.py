from dataclasses import dataclass
from decimal import Decimal
from typing import Union


@dataclass(frozen=True)
class Leverage:
    """
    Leverage Value Object for Futures Trading
    
    Immutable representation of leverage multiplier.
    Enforces business rules around leverage limits and margin requirements.
    """
    value: int
    
    MIN_LEVERAGE = 1
    MAX_LEVERAGE = 125  # Binance Futures max leverage
    
    def __init__(self, value: Union[int, str]):
        """
        Initialize Leverage with validation.
        
        Args:
            value: The leverage multiplier (1x to 125x)
            
        Raises:
            InvalidLeverageError: If leverage is invalid
        """
        try:
            leverage_value = int(value)
        except (ValueError, TypeError) as e:
            raise InvalidLeverageError(f"Cannot create leverage from {value}: {e}")
        
        if leverage_value < self.MIN_LEVERAGE:
            raise InvalidLeverageError(
                f"Leverage cannot be less than {self.MIN_LEVERAGE}x: {leverage_value}x"
            )
        
        if leverage_value > self.MAX_LEVERAGE:
            raise InvalidLeverageError(
                f"Leverage cannot exceed {self.MAX_LEVERAGE}x: {leverage_value}x"
            )
        
        object.__setattr__(self, "value", leverage_value)
    
    def calculate_initial_margin(self, position_value: Decimal) -> Decimal:
        """
        Calculate initial margin required for a position.
        
        Args:
            position_value: Total value of the position
            
        Returns:
            Required initial margin
        """
        if position_value <= 0:
            raise ValueError("Position value must be positive")
        
        return position_value / Decimal(str(self.value))
    
    def calculate_maintenance_margin(self, position_value: Decimal) -> Decimal:
        """
        Calculate maintenance margin for a position.
        
        Binance uses tiered maintenance margin rates based on position value.
        This is a simplified calculation.
        
        Args:
            position_value: Total value of the position
            
        Returns:
            Required maintenance margin
        """
        # Simplified maintenance margin calculation
        # In reality, this would use Binance's tiered system
        maintenance_rate = Decimal("0.005")  # 0.5% for small positions
        
        if position_value > 1000000:
            maintenance_rate = Decimal("0.025")  # 2.5% for large positions
        elif position_value > 250000:
            maintenance_rate = Decimal("0.01")  # 1% for medium positions
        
        return position_value * maintenance_rate
    
    def calculate_liquidation_price(
        self,
        entry_price: Decimal,
        position_side: str,
        wallet_balance: Decimal,
        position_quantity: Decimal
    ) -> Decimal:
        """
        Calculate liquidation price for a leveraged position.
        
        Simplified formula - actual Binance calculation is more complex.
        
        Args:
            entry_price: Entry price of the position
            position_side: "LONG" or "SHORT"
            wallet_balance: Available wallet balance
            position_quantity: Size of the position
            
        Returns:
            Estimated liquidation price
        """
        if position_quantity <= 0:
            raise ValueError("Position quantity must be positive")
        
        # Initial margin used
        position_value = entry_price * position_quantity
        initial_margin = self.calculate_initial_margin(position_value)
        
        # Simplified liquidation calculation
        # In reality, includes fees, funding, and maintenance margin
        if position_side.upper() == "LONG":
            # Long positions are liquidated when price drops
            max_loss = initial_margin * Decimal("0.8")  # 80% of margin
            liquidation_price = entry_price - (max_loss / position_quantity)
        else:  # SHORT
            # Short positions are liquidated when price rises
            max_loss = initial_margin * Decimal("0.8")
            liquidation_price = entry_price + (max_loss / position_quantity)
        
        return max(liquidation_price, Decimal("0"))
    
    def calculate_position_size(self, capital: Decimal, entry_price: Decimal) -> Decimal:
        """
        Calculate maximum position size given capital and leverage.
        
        Args:
            capital: Available capital for margin
            entry_price: Entry price per unit
            
        Returns:
            Maximum position size (quantity)
        """
        if capital <= 0:
            raise ValueError("Capital must be positive")
        if entry_price <= 0:
            raise ValueError("Entry price must be positive")
        
        max_position_value = capital * Decimal(str(self.value))
        return max_position_value / entry_price
    
    def calculate_effective_leverage(
        self,
        position_value: Decimal,
        account_balance: Decimal
    ) -> Decimal:
        """
        Calculate actual leverage being used.
        
        Args:
            position_value: Total value of all positions
            account_balance: Total account balance
            
        Returns:
            Effective leverage ratio
        """
        if account_balance <= 0:
            raise ValueError("Account balance must be positive")
        
        return position_value / account_balance
    
    def is_cross_margin(self) -> bool:
        """Check if this represents cross margin mode (leverage = 0 in some systems)."""
        return False  # In our system, we use explicit leverage values
    
    def increase(self, amount: int = 1) -> "Leverage":
        """
        Increase leverage by specified amount.
        
        Args:
            amount: Amount to increase leverage by
            
        Returns:
            New Leverage object with increased value
        """
        return Leverage(self.value + amount)
    
    def decrease(self, amount: int = 1) -> "Leverage":
        """
        Decrease leverage by specified amount.
        
        Args:
            amount: Amount to decrease leverage by
            
        Returns:
            New Leverage object with decreased value
        """
        return Leverage(self.value - amount)
    
    def to_multiplier_string(self) -> str:
        """Return leverage as multiplier string (e.g., '10x')."""
        return f"{self.value}x"
    
    def __str__(self) -> str:
        """String representation."""
        return self.to_multiplier_string()
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"Leverage(value={self.value})"
    
    def __eq__(self, other) -> bool:
        """Check equality with another Leverage."""
        if not isinstance(other, Leverage):
            return False
        return self.value == other.value
    
    def __lt__(self, other) -> bool:
        """Check if this leverage is less than another."""
        if not isinstance(other, Leverage):
            raise TypeError(f"Cannot compare Leverage with {type(other)}")
        return self.value < other.value
    
    def __le__(self, other) -> bool:
        """Check if this leverage is less than or equal to another."""
        if not isinstance(other, Leverage):
            raise TypeError(f"Cannot compare Leverage with {type(other)}")
        return self.value <= other.value
    
    def __gt__(self, other) -> bool:
        """Check if this leverage is greater than another."""
        if not isinstance(other, Leverage):
            raise TypeError(f"Cannot compare Leverage with {type(other)}")
        return self.value > other.value
    
    def __ge__(self, other) -> bool:
        """Check if this leverage is greater than or equal to another."""
        if not isinstance(other, Leverage):
            raise TypeError(f"Cannot compare Leverage with {type(other)}")
        return self.value >= other.value
    
    def __hash__(self) -> int:
        """Make Leverage hashable for use in sets/dicts."""
        return hash(self.value)
    
    @classmethod
    def default(cls) -> "Leverage":
        """Create default leverage (1x - no leverage)."""
        return cls(1)
    
    @classmethod
    def conservative(cls) -> "Leverage":
        """Create conservative leverage (2x)."""
        return cls(2)
    
    @classmethod
    def moderate(cls) -> "Leverage":
        """Create moderate leverage (5x)."""
        return cls(5)
    
    @classmethod
    def aggressive(cls) -> "Leverage":
        """Create aggressive leverage (10x)."""
        return cls(10)
    
    @classmethod
    def maximum_safe(cls) -> "Leverage":
        """Create maximum safe leverage (20x)."""
        return cls(20)


# Domain Exceptions
class LeverageError(Exception):
    """Base exception for Leverage value object."""
    pass


class InvalidLeverageError(LeverageError):
    """Raised when leverage value is invalid."""
    pass