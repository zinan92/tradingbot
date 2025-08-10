"""
Abstract interface for execution adapters.

Defines the contract that all execution implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.domain.entities import Order, Position
from src.domain.value_objects import Symbol, Price, Quantity


class OrderStatus(Enum):
    """Order status enumeration."""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class ExecutionResult:
    """Result of order execution."""
    success: bool
    order_id: str
    status: OrderStatus
    filled_quantity: Decimal
    average_price: Decimal
    commission: Decimal
    commission_asset: str
    timestamp: datetime
    raw_response: Dict[str, Any]
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class MarketData:
    """Market data snapshot."""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume_24h: Decimal
    timestamp: datetime


@dataclass
class AccountInfo:
    """Account information."""
    balances: Dict[str, Decimal]
    positions: List[Position]
    margin_level: Optional[Decimal]
    free_margin: Optional[Decimal]
    equity: Decimal
    timestamp: datetime


@dataclass
class SymbolInfo:
    """Trading symbol information."""
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    min_quantity: Decimal
    max_quantity: Decimal
    step_size: Decimal
    min_notional: Decimal
    price_precision: int
    quantity_precision: int
    base_precision: int
    quote_precision: int
    filters: Dict[str, Any]


class ExecutionAdapter(ABC):
    """Abstract base class for execution adapters."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to exchange."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection to exchange."""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to exchange."""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> ExecutionResult:
        """Place an order on the exchange."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order."""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str, symbol: str) -> ExecutionResult:
        """Get status of an existing order."""
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all open orders."""
        pass
    
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """Get account information."""
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get current market data for symbol."""
        pass
    
    @abstractmethod
    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get trading rules for symbol."""
        pass
    
    @abstractmethod
    async def get_precision_map(self) -> Dict[str, Tuple[int, int]]:
        """Get precision map for all symbols."""
        pass
    
    @abstractmethod
    def get_adapter_name(self) -> str:
        """Get adapter implementation name."""
        pass
    
    @abstractmethod
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the adapter."""
        pass
    
    def format_quantity(self, quantity: Decimal, symbol: str) -> Decimal:
        """Format quantity according to exchange rules."""
        # Default implementation - can be overridden
        return quantity.quantize(Decimal("0.00000001"))
    
    def format_price(self, price: Decimal, symbol: str) -> Decimal:
        """Format price according to exchange rules."""
        # Default implementation - can be overridden
        return price.quantize(Decimal("0.01"))
    
    def validate_order(self, order: Order) -> Tuple[bool, Optional[str]]:
        """Validate order before submission."""
        # Basic validation - can be extended
        if order.quantity.value <= 0:
            return False, "Invalid quantity"
        
        if order.price and order.price.value <= 0:
            return False, "Invalid price"
        
        return True, None