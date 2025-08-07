from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ..aggregates.order import Order


class IOrderRepository(ABC):
    """
    Repository interface for Order aggregate
    
    Defines the contract for Order persistence.
    Implementation details are left to the infrastructure layer.
    """
    
    @abstractmethod
    def get(self, order_id: UUID) -> Optional[Order]:
        """
        Retrieve an order by its ID
        
        Args:
            order_id: The unique identifier of the order
            
        Returns:
            The Order if found, None otherwise
        """
        pass
    
    @abstractmethod
    def save(self, order: Order) -> None:
        """
        Save or update an order
        
        Args:
            order: The Order aggregate to persist
            
        Raises:
            RepositoryError: If save operation fails
        """
        pass
    
    @abstractmethod
    def get_by_portfolio(self, portfolio_id: UUID) -> List[Order]:
        """
        Retrieve all orders for a specific portfolio
        
        Args:
            portfolio_id: The portfolio's unique identifier
            
        Returns:
            List of orders belonging to the portfolio
        """
        pass
    
    @abstractmethod
    def get_pending_orders(self, portfolio_id: Optional[UUID] = None) -> List[Order]:
        """
        Retrieve all pending orders, optionally filtered by portfolio
        
        Args:
            portfolio_id: Optional portfolio filter
            
        Returns:
            List of pending orders
        """
        pass
    
    @abstractmethod
    def get_by_broker_order_id(self, broker_order_id: str) -> Optional[Order]:
        """
        Retrieve an order by broker's order ID
        
        Args:
            broker_order_id: The broker's order identifier
            
        Returns:
            The Order if found, None otherwise
        """
        pass
    
    @abstractmethod
    def exists(self, order_id: UUID) -> bool:
        """
        Check if an order exists
        
        Args:
            order_id: The order's unique identifier
            
        Returns:
            True if order exists, False otherwise
        """
        pass


class RepositoryError(Exception):
    """Base exception for repository operations"""
    pass


class OrderNotFoundError(RepositoryError):
    """Raised when an order cannot be found"""
    pass


class OrderSaveError(RepositoryError):
    """Raised when an order cannot be saved"""
    pass