from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Union


@dataclass(frozen=True)
class Money:
    """
    Money Value Object
    
    Immutable representation of monetary value with currency.
    Enforces business rules around money operations.
    """
    amount: Decimal
    currency: str
    
    def __init__(self, amount: Union[Decimal, float, int, str], currency: str = "USD"):
        """
        Initialize Money with proper decimal handling
        
        Args:
            amount: The monetary amount (converted to Decimal)
            currency: ISO 4217 currency code (e.g., USD, EUR, GBP)
        """
        if isinstance(amount, (float, int)):
            amount = Decimal(str(amount))
        elif isinstance(amount, str):
            amount = Decimal(amount)
        
        if amount < 0:
            raise NegativeMoneyError(f"Money amount cannot be negative: {amount}")
        
        if not currency or len(currency) != 3:
            raise InvalidCurrencyError(f"Invalid currency code: {currency}")
        
        # Round to 2 decimal places for most currencies
        # TODO: Handle currencies with different decimal places (e.g., JPY has 0)
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency.upper())
    
    def add(self, other: "Money") -> "Money":
        """Add two money values with same currency"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot add Money to {type(other)}")
        
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot add {self.currency} and {other.currency}"
            )
        
        return Money(self.amount + other.amount, self.currency)
    
    def subtract(self, other: "Money") -> "Money":
        """Subtract money value with same currency"""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot subtract {type(other)} from Money")
        
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot subtract {other.currency} from {self.currency}"
            )
        
        result = self.amount - other.amount
        if result < 0:
            raise InsufficientMoneyError(
                f"Cannot subtract {other.amount} from {self.amount}"
            )
        
        return Money(result, self.currency)
    
    def multiply(self, factor: Union[Decimal, float, int]) -> "Money":
        """Multiply money by a factor"""
        if isinstance(factor, (float, int)):
            factor = Decimal(str(factor))
        
        return Money(self.amount * factor, self.currency)
    
    def is_greater_than(self, other: "Money") -> bool:
        """Check if this money is greater than another"""
        self._ensure_same_currency(other)
        return self.amount > other.amount
    
    def is_greater_than_or_equal(self, other: "Money") -> bool:
        """Check if this money is greater than or equal to another"""
        self._ensure_same_currency(other)
        return self.amount >= other.amount
    
    def is_less_than(self, other: "Money") -> bool:
        """Check if this money is less than another"""
        self._ensure_same_currency(other)
        return self.amount < other.amount
    
    def is_equal_to(self, other: "Money") -> bool:
        """Check if two money values are equal"""
        if not isinstance(other, Money):
            return False
        return self.amount == other.amount and self.currency == other.currency
    
    def is_zero(self) -> bool:
        """Check if money amount is zero"""
        return self.amount == Decimal("0")
    
    def _ensure_same_currency(self, other: "Money") -> None:
        """Ensure two money values have the same currency"""
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot compare {self.currency} with {other.currency}"
            )
    
    def __str__(self) -> str:
        """String representation of money"""
        return f"{self.currency} {self.amount:,.2f}"
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"Money(amount={self.amount}, currency='{self.currency}')"
    
    def __eq__(self, other) -> bool:
        """Equality comparison"""
        if not isinstance(other, Money):
            return False
        return self.amount == other.amount and self.currency == other.currency
    
    def __hash__(self) -> int:
        """Make Money hashable for use in sets/dicts"""
        return hash((self.amount, self.currency))
    
    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        """Factory method to create zero money"""
        return cls(Decimal("0"), currency)


# Domain Exceptions
class MoneyError(Exception):
    """Base exception for Money value object"""
    pass


class NegativeMoneyError(MoneyError):
    """Raised when trying to create money with negative amount"""
    pass


class InvalidCurrencyError(MoneyError):
    """Raised when currency code is invalid"""
    pass


class CurrencyMismatchError(MoneyError):
    """Raised when operating on money with different currencies"""
    pass


class InsufficientMoneyError(MoneyError):
    """Raised when subtraction would result in negative money"""
    pass