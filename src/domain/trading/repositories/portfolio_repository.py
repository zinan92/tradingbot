from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ..aggregates.portfolio import Portfolio


class IPortfolioRepository(ABC):
    """
    Repository interface for Portfolio aggregate
    
    Defines the contract for Portfolio persistence.
    Implementation details are left to the infrastructure layer.
    """
    
    @abstractmethod
    def get(self, portfolio_id: UUID) -> Optional[Portfolio]:
        """
        Retrieve a portfolio by its ID
        
        Args:
            portfolio_id: The unique identifier of the portfolio
            
        Returns:
            The Portfolio if found, None otherwise
        """
        pass
    
    @abstractmethod
    def save(self, portfolio: Portfolio) -> None:
        """
        Save or update a portfolio
        
        Args:
            portfolio: The Portfolio aggregate to persist
            
        Raises:
            RepositoryError: If save operation fails
        """
        pass
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Portfolio]:
        """
        Retrieve a portfolio by its name
        
        Args:
            name: The portfolio name
            
        Returns:
            The Portfolio if found, None otherwise
        """
        pass
    
    @abstractmethod
    def get_all(self) -> List[Portfolio]:
        """
        Retrieve all portfolios
        
        Returns:
            List of all portfolios in the system
        """
        pass
    
    @abstractmethod
    def exists(self, portfolio_id: UUID) -> bool:
        """
        Check if a portfolio exists
        
        Args:
            portfolio_id: The portfolio's unique identifier
            
        Returns:
            True if portfolio exists, False otherwise
        """
        pass
    
    @abstractmethod
    def delete(self, portfolio_id: UUID) -> bool:
        """
        Delete a portfolio (soft delete recommended)
        
        Args:
            portfolio_id: The portfolio's unique identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass


class PortfolioRepositoryError(Exception):
    """Base exception for portfolio repository operations"""
    pass


class PortfolioNotFoundError(PortfolioRepositoryError):
    """Raised when a portfolio cannot be found"""
    pass


class PortfolioSaveError(PortfolioRepositoryError):
    """Raised when a portfolio cannot be saved"""
    pass


class DuplicatePortfolioError(PortfolioRepositoryError):
    """Raised when trying to create a portfolio with duplicate name"""
    pass