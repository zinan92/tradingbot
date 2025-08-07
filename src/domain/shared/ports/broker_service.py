"""
Broker Service Port (Interface)

Defines the contract for broker services in the domain layer.
This is a port in hexagonal architecture - implementations are adapters.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from src.domain.trading.aggregates.order import Order
from src.domain.trading.value_objects.price import Price
from src.domain.trading.value_objects.quantity import Quantity


class IBrokerService(ABC):
    """
    Broker Service Interface
    
    Defines the contract that any broker implementation must fulfill.
    This keeps the domain layer independent of specific broker implementations.
    """
    
    @abstractmethod
    def submit_order_sync(self, order: Order) -> str:
        """
        Submit an order to the broker synchronously
        
        Args:
            order: Domain order object to submit
            
        Returns:
            str: Broker's order identifier
            
        Raises:
            BrokerConnectionError: If unable to connect to broker
            BrokerValidationError: If order validation fails
            BrokerSubmissionError: If submission fails
        """
        pass
    
    @abstractmethod
    async def submit_order_async(self, order: Order) -> str:
        """
        Submit an order to the broker asynchronously
        
        Args:
            order: Domain order object to submit
            
        Returns:
            str: Broker's order identifier
            
        Raises:
            BrokerConnectionError: If unable to connect to broker
            BrokerValidationError: If order validation fails
            BrokerSubmissionError: If submission fails
        """
        pass
    
    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> bool:
        """
        Cancel an order with the broker
        
        Args:
            broker_order_id: Broker's order identifier
            
        Returns:
            bool: True if cancellation was accepted
        """
        pass
    
    @abstractmethod
    async def cancel_order_async(self, broker_order_id: str) -> bool:
        """
        Cancel an order with the broker asynchronously
        
        Args:
            broker_order_id: Broker's order identifier
            
        Returns:
            bool: True if cancellation was accepted
        """
        pass
    
    @abstractmethod
    def get_order_status(self, broker_order_id: str) -> str:
        """
        Get the current status of an order
        
        Args:
            broker_order_id: Broker's order identifier
            
        Returns:
            str: Order status (PENDING, FILLED, CANCELLED, etc.)
        """
        pass
    
    @abstractmethod
    def get_account_balance(self) -> Dict[str, Decimal]:
        """
        Get current account balance
        
        Returns:
            Dict mapping currency to available balance
        """
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current position for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position information or None if no position
        """
        pass
    
    @abstractmethod
    def get_market_price(self, symbol: str) -> Price:
        """
        Get current market price for a symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current market price
            
        Raises:
            SymbolNotFoundError: If symbol doesn't exist
            MarketDataError: If unable to fetch price
        """
        pass
    
    @abstractmethod
    def is_market_open(self) -> bool:
        """
        Check if the market is currently open for trading
        
        Returns:
            bool: True if market is open
        """
        pass
    
    @abstractmethod
    def get_trading_hours(self) -> Dict[str, Any]:
        """
        Get trading hours information
        
        Returns:
            Dictionary with market hours information
        """
        pass


class IMockableBrokerService(IBrokerService):
    """
    Extended broker interface for testing
    
    Adds methods useful for testing and simulation.
    """
    
    @abstractmethod
    def set_fill_behavior(self, behavior: str) -> None:
        """
        Set how the mock broker should handle fills
        
        Args:
            behavior: Fill behavior (IMMEDIATE, DELAYED, REJECT, etc.)
        """
        pass
    
    @abstractmethod
    def set_market_price(self, symbol: str, price: Price) -> None:
        """
        Set the market price for a symbol (for testing)
        
        Args:
            symbol: Trading symbol
            price: Price to set
        """
        pass
    
    @abstractmethod
    def simulate_fill(self, broker_order_id: str, fill_price: Decimal) -> bool:
        """
        Simulate an order fill (for testing)
        
        Args:
            broker_order_id: Order to fill
            fill_price: Price at which to fill
            
        Returns:
            bool: True if fill was simulated
        """
        pass
    
    @abstractmethod
    def get_order_history(self) -> List[Dict[str, Any]]:
        """
        Get history of all orders (for testing/debugging)
        
        Returns:
            List of order information dictionaries
        """
        pass


# Broker Exceptions (Domain Layer)

class BrokerError(Exception):
    """Base exception for broker-related errors"""
    pass


class BrokerConnectionError(BrokerError):
    """Raised when unable to connect to broker"""
    pass


class BrokerValidationError(BrokerError):
    """Raised when broker rejects order due to validation"""
    pass


class BrokerSubmissionError(BrokerError):
    """Raised when order submission fails"""
    pass


class BrokerInsufficientFundsError(BrokerValidationError):
    """Raised when account has insufficient funds"""
    pass


class BrokerSymbolNotFoundError(BrokerValidationError):
    """Raised when symbol is not found or not tradeable"""
    pass


class BrokerMarketClosedError(BrokerError):
    """Raised when attempting to trade while market is closed"""
    pass


class MarketDataError(BrokerError):
    """Raised when unable to fetch market data"""
    pass