from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Symbol:
    """
    Symbol Value Object
    
    Immutable representation of a trading symbol/ticker.
    Enforces business rules around valid symbol formats.
    """
    value: str
    
    def __init__(self, value: str):
        """
        Initialize Symbol with validation
        
        Args:
            value: The trading symbol (e.g., "AAPL", "MSFT", "GOOGL")
        """
        if not value or not isinstance(value, str):
            raise InvalidSymbolError("Symbol must be a non-empty string")
        
        value = value.strip().upper()
        
        if not value:
            raise InvalidSymbolError("Symbol cannot be empty")
        
        # Validate symbol format - support various market types
        # US stocks: 1-5 uppercase letters
        # Futures/Crypto: BTCUSDT, ETHUSDT format
        if not re.match(r"^[A-Z0-9]{1,20}$", value):
            raise InvalidSymbolError(
                f"Invalid symbol format: {value}. "
                "Symbol must be alphanumeric (1-20 characters)"
            )
        
        object.__setattr__(self, "value", value)
    
    @property
    def ticker(self) -> str:
        """Alias for value - returns the ticker symbol"""
        return self.value
    
    def is_valid_for_exchange(self, exchange: str) -> bool:
        """
        Check if symbol is valid for a specific exchange
        
        TODO: Implement exchange-specific validation rules
        """
        # Placeholder for exchange-specific validation
        # Different exchanges have different symbol formats
        if exchange == "NYSE" or exchange == "NASDAQ":
            return re.match(r"^[A-Z]{1,5}$", self.value) is not None
        elif exchange == "CRYPTO":
            # Crypto symbols often have formats like BTC-USD
            return re.match(r"^[A-Z]{2,10}(-[A-Z]{2,10})?$", self.value) is not None
        elif exchange == "BINANCE_FUTURES":
            # Binance futures symbols like BTCUSDT, ETHUSDT
            return re.match(r"^[A-Z]{2,10}USDT$", self.value) is not None
        
        return True
    
    def __str__(self) -> str:
        """String representation of symbol"""
        return self.value
    
    def __repr__(self) -> str:
        """Developer-friendly representation"""
        return f"Symbol('{self.value}')"
    
    def __eq__(self, other) -> bool:
        """Equality comparison"""
        if not isinstance(other, Symbol):
            return False
        return self.value == other.value
    
    def __hash__(self) -> int:
        """Make Symbol hashable for use in sets/dicts"""
        return hash(self.value)
    
    def __lt__(self, other: "Symbol") -> bool:
        """Less than comparison for sorting"""
        if not isinstance(other, Symbol):
            return NotImplemented
        return self.value < other.value
    
    @classmethod
    def from_string(cls, value: str) -> "Symbol":
        """Factory method to create Symbol from string"""
        return cls(value)
    
    @classmethod
    def is_valid_format(cls, value: str) -> bool:
        """Check if a string has valid symbol format without creating object"""
        if not value or not isinstance(value, str):
            return False
        
        value = value.strip().upper()
        return bool(re.match(r"^[A-Z0-9]{1,20}$", value))


# Domain Exceptions
class SymbolError(Exception):
    """Base exception for Symbol value object"""
    pass


class InvalidSymbolError(SymbolError):
    """Raised when symbol format is invalid"""
    pass