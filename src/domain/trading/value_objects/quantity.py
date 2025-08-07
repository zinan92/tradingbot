from pydantic import BaseModel, Field, field_validator, ConfigDict
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from typing import Union


class Quantity(BaseModel):
    """
    Quantity Value Object
    
    Immutable representation of trading quantity.
    Enforces business rules around quantity operations.
    Uses Pydantic v2 for strict runtime validation.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Make immutable
        str_strip_whitespace=True,
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    value: Decimal = Field(
        ...,
        gt=0,
        description="The quantity value must be positive"
    )
    
    def __init__(self, value: Union[Decimal, float, int, str]):
        """
        Initialize Quantity with proper decimal handling and Pydantic validation
        
        Args:
            value: The quantity value (converted to Decimal)
            
        Raises:
            ValueError: If quantity is not positive or invalid type
        """
        if isinstance(value, (float, int)):
            decimal_value = Decimal(str(value))
        elif isinstance(value, str):
            decimal_value = Decimal(value)
        elif isinstance(value, Decimal):
            decimal_value = value
        else:
            raise ValueError(f"Invalid quantity type: {type(value)}")
        
        # Round to 8 decimal places (common for crypto, adjustable for stocks)
        decimal_value = decimal_value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        
        super().__init__(value=decimal_value)
    
    @field_validator('value')
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        """Ensure quantity is positive using Pydantic validator"""
        if v <= 0:
            raise ValueError(f"Quantity must be positive, got {v}")
        return v
    
    def add(self, other: "Quantity") -> "Quantity":
        """Add two quantities"""
        if not isinstance(other, Quantity):
            raise TypeError(f"Cannot add Quantity to {type(other)}")
        
        return Quantity(self.value + other.value)
    
    def subtract(self, other: "Quantity") -> "Quantity":
        """Subtract quantity"""
        if not isinstance(other, Quantity):
            raise TypeError(f"Cannot subtract {type(other)} from Quantity")
        
        result = self.value - other.value
        if result <= 0:
            raise InsufficientQuantityError(
                f"Cannot subtract {other.value} from {self.value}"
            )
        
        return Quantity(result)
    
    def multiply(self, factor: Union[Decimal, float, int]) -> "Quantity":
        """Multiply quantity by a factor"""
        if isinstance(factor, (float, int)):
            factor = Decimal(str(factor))
        
        if factor <= 0:
            raise InvalidQuantityError("Multiplication factor must be positive")
        
        return Quantity(self.value * factor)
    
    def divide(self, divisor: Union["Quantity", Decimal, float, int]) -> Union["Quantity", Decimal]:
        """
        Divide quantity by another quantity or number
        
        Returns:
            Quantity if divided by number
            Decimal if divided by another Quantity (ratio)
        """
        if isinstance(divisor, Quantity):
            # Division of two quantities gives a ratio (Decimal)
            return self.value / divisor.value
        
        if isinstance(divisor, (float, int)):
            divisor = Decimal(str(divisor))
        
        if divisor <= 0:
            raise InvalidQuantityError("Division factor must be positive")
        
        return Quantity(self.value / divisor)
    
    def split(self, parts: int) -> list["Quantity"]:
        """
        Split quantity into equal parts
        
        Args:
            parts: Number of parts to split into
            
        Returns:
            List of Quantity objects
        """
        if parts <= 0:
            raise InvalidQuantityError("Number of parts must be positive")
        
        part_size = self.value / Decimal(str(parts))
        return [Quantity(part_size) for _ in range(parts)]
    
    def calculate_value(self, price: "Price") -> "Money":
        """
        Calculate the monetary value given a price
        
        Args:
            price: Price value object
            
        Returns:
            Money value object representing quantity * price
        """
        from .price import Price
        from .money import Money
        
        if not isinstance(price, Price):
            raise TypeError(f"Expected Price, got {type(price)}")
        
        return Money(self.value * price.value, price.currency)
    
    def is_greater_than(self, other: "Quantity") -> bool:
        """Check if this quantity is greater than another"""
        if not isinstance(other, Quantity):
            raise TypeError(f"Cannot compare Quantity with {type(other)}")
        return self.value > other.value
    
    def is_greater_than_or_equal(self, other: "Quantity") -> bool:
        """Check if this quantity is greater than or equal to another"""
        if not isinstance(other, Quantity):
            raise TypeError(f"Cannot compare Quantity with {type(other)}")
        return self.value >= other.value
    
    def is_less_than(self, other: "Quantity") -> bool:
        """Check if this quantity is less than another"""
        if not isinstance(other, Quantity):
            raise TypeError(f"Cannot compare Quantity with {type(other)}")
        return self.value < other.value
    
    def is_less_than_or_equal(self, other: "Quantity") -> bool:
        """Check if this quantity is less than or equal to another"""
        if not isinstance(other, Quantity):
            raise TypeError(f"Cannot compare Quantity with {type(other)}")
        return self.value <= other.value
    
    def is_equal_to(self, other: "Quantity") -> bool:
        """Check if two quantities are equal"""
        if not isinstance(other, Quantity):
            return False
        return self.value == other.value
    
    def to_int(self) -> int:
        """Convert to integer (for whole shares/units)"""
        return int(self.value)
    
    def to_decimal(self) -> Decimal:
        """Get the raw decimal value"""
        return self.value
    
    def __str__(self) -> str:
        """String representation of quantity"""
        # Remove trailing zeros for cleaner display
        normalized = self.value.normalize()
        # Convert scientific notation to regular for whole numbers
        if self.value == self.value.to_integral_value():
            return str(int(self.value))
        return str(normalized)
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        # Show cleaner repr for whole numbers
        if self.value == self.value.to_integral_value():
            return f"Quantity(value={int(self.value)})"
        return f"Quantity(value={self.value})"
    
    def __eq__(self, other) -> bool:
        """Equality comparison"""
        if not isinstance(other, Quantity):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Make Quantity hashable for use in sets/dicts"""
        return hash(self.value)
    
    def __mul__(self, other):
        """Support multiplication with * operator"""
        if isinstance(other, (Decimal, float, int)):
            return self.multiply(other)
        
        # Support quantity * price = money
        from .price import Price
        if isinstance(other, Price):
            return self.calculate_value(other)
        
        raise TypeError(f"Cannot multiply Quantity with {type(other)}")
    
    def __rmul__(self, other):
        """Support reverse multiplication"""
        return self.__mul__(other)
    
    def __truediv__(self, other):
        """Support division with / operator"""
        return self.divide(other)
    
    def __add__(self, other):
        """Support addition with + operator"""
        if isinstance(other, Quantity):
            return self.add(other)
        raise TypeError(f"Cannot add Quantity to {type(other)}")
    
    def __sub__(self, other):
        """Support subtraction with - operator"""
        if isinstance(other, Quantity):
            return self.subtract(other)
        raise TypeError(f"Cannot subtract {type(other)} from Quantity")
    
    def __lt__(self, other):
        """Support < comparison"""
        return self.is_less_than(other)
    
    def __le__(self, other):
        """Support <= comparison"""
        return self.is_less_than_or_equal(other)
    
    def __gt__(self, other):
        """Support > comparison"""
        return self.is_greater_than(other)
    
    def __ge__(self, other):
        """Support >= comparison"""
        return self.is_greater_than_or_equal(other)
    
    @classmethod
    def from_lots(cls, lots: int, lot_size: int = 100) -> "Quantity":
        """
        Factory method to create quantity from lots
        
        Args:
            lots: Number of lots
            lot_size: Size of each lot (default 100 for stocks)
            
        Returns:
            Quantity representing total units
        """
        return cls(lots * lot_size)
    
    @classmethod
    def minimum(cls) -> "Quantity":
        """Factory method to create minimum tradeable quantity"""
        return cls(Decimal("0.00000001"))


# Domain Exceptions
class QuantityError(Exception):
    """Base exception for Quantity value object"""
    pass


class NonPositiveQuantityError(QuantityError):
    """Raised when trying to create quantity with non-positive value"""
    pass


class InvalidQuantityError(QuantityError):
    """Raised when quantity value is invalid"""
    pass


class InsufficientQuantityError(QuantityError):
    """Raised when operation would result in negative or zero quantity"""
    pass