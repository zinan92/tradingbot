"""
Broker port interface.

Defines the contract for broker integrations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal

from src.domain.entities import Order, Position, Trade
from src.domain.value_objects import Symbol, OrderId, PositionId


class BrokerPort(ABC):
    """
    Port interface for broker integrations.
    
    All broker implementations must implement this interface.
    """
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to broker.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from broker.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to broker.
        
        Returns:
            True if connected
        """
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> OrderId:
        """
        Place an order with broker.
        
        Args:
            order: Order to place
            
        Returns:
            Order ID from broker
            
        Raises:
            BrokerException: If order placement fails
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: OrderId) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: OrderId) -> Dict[str, Any]:
        """
        Get order status.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order status information
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: Optional[Symbol] = None) -> List[Order]:
        """
        Get open orders.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of open orders
        """
        pass
    
    @abstractmethod
    async def get_positions(self, symbol: Optional[Symbol] = None) -> List[Position]:
        """
        Get current positions.
        
        Args:
            symbol: Optional symbol filter
            
        Returns:
            List of positions
        """
        pass
    
    @abstractmethod
    async def get_position(self, position_id: PositionId) -> Optional[Position]:
        """
        Get specific position.
        
        Args:
            position_id: Position ID
            
        Returns:
            Position or None if not found
        """
        pass
    
    @abstractmethod
    async def close_position(self, position_id: PositionId) -> bool:
        """
        Close a position.
        
        Args:
            position_id: Position ID to close
            
        Returns:
            True if closed successfully
        """
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> Dict[str, Decimal]:
        """
        Get account balances.
        
        Returns:
            Dictionary of asset balances
        """
        pass
    
    @abstractmethod
    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Account information including margins, equity, etc.
        """
        pass
    
    @abstractmethod
    async def get_trades(
        self,
        symbol: Optional[Symbol] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Trade]:
        """
        Get historical trades.
        
        Args:
            symbol: Optional symbol filter
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of trades
            
        Returns:
            List of trades
        """
        pass
    
    @abstractmethod
    async def get_market_price(self, symbol: Symbol) -> Decimal:
        """
        Get current market price.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current market price
        """
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: Symbol, depth: int = 10) -> Dict[str, Any]:
        """
        Get order book.
        
        Args:
            symbol: Trading symbol
            depth: Order book depth
            
        Returns:
            Order book with bids and asks
        """
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: Symbol) -> Dict[str, Any]:
        """
        Get ticker information.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Ticker information (price, volume, etc.)
        """
        pass
    
    @abstractmethod
    def get_broker_name(self) -> str:
        """
        Get broker name.
        
        Returns:
            Broker name
        """
        pass
    
    @abstractmethod
    def get_supported_symbols(self) -> List[Symbol]:
        """
        Get list of supported symbols.
        
        Returns:
            List of supported trading symbols
        """
        pass


class BrokerException(Exception):
    """Base exception for broker errors."""
    pass


class OrderPlacementException(BrokerException):
    """Exception for order placement errors."""
    pass


class InsufficientBalanceException(BrokerException):
    """Exception for insufficient balance errors."""
    pass


class ConnectionException(BrokerException):
    """Exception for connection errors."""
    pass