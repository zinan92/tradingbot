"""
Price Value Object

Represents a price with currency and proper validation.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class Price(BaseModel):
    """
    Price Value Object
    
    Immutable representation of a price with currency.
    Enforces business rules around price operations.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutable
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    value: Decimal = Field(
        ...,
        gt=0,
        description="The price value must be positive"
    )
    
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code"
    )
    
    def __init__(self, value: Union[Decimal, float, int, str], currency: str = "USD"):
        """
        Initialize Price with proper decimal handling
        
        Args:
            value: The price value (converted to Decimal)
            currency: ISO 4217 currency code (default USD)
            
        Raises:
            ValueError: If price is not positive or currency invalid
        """
        if isinstance(value, (float, int)):
            decimal_value = Decimal(str(value))
        elif isinstance(value, str):
            decimal_value = Decimal(value)
        elif isinstance(value, Decimal):
            decimal_value = value
        else:
            raise ValueError(f"Invalid price type: {type(value)}")
        
        # Round to 2 decimal places for fiat, 8 for crypto
        if currency in ["BTC", "ETH", "USDT", "BUSD"]:
            decimal_value = decimal_value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        else:
            decimal_value = decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        super().__init__(value=decimal_value, currency=currency.upper())
    
    @field_validator('value')
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        """Ensure price is positive"""
        if v <= 0:
            raise ValueError(f"Price must be positive, got {v}")
        return v
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency code"""
        v = v.upper()
        if len(v) != 3:
            raise ValueError(f"Currency must be 3-letter ISO code, got {v}")
        if not v.isalpha():
            raise ValueError(f"Currency must contain only letters, got {v}")
        return v
    
    def add(self, other: "Price") -> "Price":
        """Add two prices with same currency"""
        if not isinstance(other, Price):
            raise TypeError(f"Cannot add Price to {type(other)}")
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot add prices with different currencies: {self.currency} and {other.currency}"
            )
        return Price(self.value + other.value, self.currency)
    
    def subtract(self, other: "Price") -> "Price":
        """Subtract price with same currency"""
        if not isinstance(other, Price):
            raise TypeError(f"Cannot subtract {type(other)} from Price")
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot subtract prices with different currencies: {self.currency} and {other.currency}"
            )
        
        result = self.value - other.value
        if result <= 0:
            raise InvalidPriceError(f"Price subtraction would result in non-positive value: {result}")
        
        return Price(result, self.currency)
    
    def multiply(self, factor: Union[Decimal, float, int]) -> "Price":
        """Multiply price by a factor"""
        if isinstance(factor, (float, int)):
            factor = Decimal(str(factor))
        
        if factor <= 0:
            raise InvalidPriceError("Multiplication factor must be positive")
        
        return Price(self.value * factor, self.currency)
    
    def divide(self, divisor: Union[Decimal, float, int]) -> "Price":
        """Divide price by a factor"""
        if isinstance(divisor, (float, int)):
            divisor = Decimal(str(divisor))
        
        if divisor <= 0:
            raise InvalidPriceError("Division factor must be positive")
        
        return Price(self.value / divisor, self.currency)
    
    def calculate_total(self, quantity: "Quantity") -> "Money":
        """
        Calculate total value for a quantity
        
        Args:
            quantity: Quantity value object
            
        Returns:
            Money value object representing price * quantity
        """
        from .quantity import Quantity
        from .money import Money
        
        if not isinstance(quantity, Quantity):
            raise TypeError(f"Expected Quantity, got {type(quantity)}")
        
        return Money(self.value * quantity.value, self.currency)
    
    def apply_percentage(self, percentage: Union[Decimal, float]) -> "Price":
        """
        Apply a percentage change to the price
        
        Args:
            percentage: Percentage change (e.g., 5 for 5% increase, -5 for 5% decrease)
            
        Returns:
            New Price with percentage applied
        """
        if isinstance(percentage, float):
            percentage = Decimal(str(percentage))
        
        factor = Decimal("1") + (percentage / Decimal("100"))
        if factor <= 0:
            raise InvalidPriceError(f"Percentage change would result in non-positive price: {percentage}%")
        
        return Price(self.value * factor, self.currency)
    
    def is_greater_than(self, other: "Price") -> bool:
        """Check if this price is greater than another"""
        if not isinstance(other, Price):
            raise TypeError(f"Cannot compare Price with {type(other)}")
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot compare prices with different currencies")
        return self.value > other.value
    
    def is_less_than(self, other: "Price") -> bool:
        """Check if this price is less than another"""
        if not isinstance(other, Price):
            raise TypeError(f"Cannot compare Price with {type(other)}")
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot compare prices with different currencies")
        return self.value < other.value
    
    def is_between(self, lower: "Price", upper: "Price") -> bool:
        """Check if price is between two prices"""
        if not isinstance(lower, Price) or not isinstance(upper, Price):
            raise TypeError("Bounds must be Price objects")
        if self.currency != lower.currency or self.currency != upper.currency:
            raise CurrencyMismatchError("All prices must have same currency for comparison")
        return lower.value <= self.value <= upper.value
    
    def to_decimal(self) -> Decimal:
        """Get the raw decimal value"""
        return self.value
    
    def to_float(self) -> float:
        """Convert to float (may lose precision)"""
        return float(self.value)
    
    def to_int(self) -> int:
        """Convert to integer (truncates decimal places)"""
        return int(self.value)
    
    def format(self, include_currency: bool = True) -> str:
        """
        Format price for display
        
        Args:
            include_currency: Whether to include currency symbol
            
        Returns:
            Formatted price string
        """
        # Currency symbols mapping
        symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥",
            "BTC": "₿",
            "ETH": "Ξ",
        }
        
        if include_currency and self.currency in symbols:
            return f"{symbols[self.currency]}{self.value:,.2f}"
        elif include_currency:
            return f"{self.value:,.2f} {self.currency}"
        else:
            return f"{self.value:,.2f}"
    
    def __str__(self) -> str:
        """String representation"""
        return self.format()
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"Price(value={self.value}, currency='{self.currency}')"
    
    def __eq__(self, other) -> bool:
        """Equality comparison"""
        if not isinstance(other, Price):
            return False
        return self.value == other.value and self.currency == other.currency
    
    def __hash__(self) -> int:
        """Make Price hashable"""
        return hash((self.value, self.currency))
    
    def __lt__(self, other):
        """Less than comparison"""
        return self.is_less_than(other)
    
    def __gt__(self, other):
        """Greater than comparison"""
        return self.is_greater_than(other)
    
    def __le__(self, other):
        """Less than or equal comparison"""
        if not isinstance(other, Price):
            raise TypeError(f"Cannot compare Price with {type(other)}")
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot compare prices with different currencies")
        return self.value <= other.value
    
    def __ge__(self, other):
        """Greater than or equal comparison"""
        if not isinstance(other, Price):
            raise TypeError(f"Cannot compare Price with {type(other)}")
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot compare prices with different currencies")
        return self.value >= other.value
    
    @classmethod
    def from_cents(cls, cents: int, currency: str = "USD") -> "Price":
        """
        Factory method to create from cents/minor units
        
        Args:
            cents: Amount in minor units (e.g., cents for USD)
            currency: Currency code
            
        Returns:
            Price instance
        """
        return cls(Decimal(cents) / Decimal("100"), currency)
    
    @classmethod
    def zero(cls, currency: str = "USD") -> "Price":
        """Factory method for zero price (useful for calculations)"""
        # Note: This violates the positive constraint, so we use minimum
        return cls(Decimal("0.01"), currency)


# Exceptions
class PriceError(Exception):
    """Base exception for price errors"""
    pass


class InvalidPriceError(PriceError):
    """Raised when price value is invalid"""
    pass


class CurrencyMismatchError(PriceError):
    """Raised when operating on prices with different currencies"""
    pass