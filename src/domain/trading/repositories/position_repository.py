from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from uuid import UUID
from decimal import Decimal

from ..entities.position import Position


class IPositionRepository(ABC):
    """
    Repository interface for Position entities.
    
    Defines the contract for position persistence operations.
    """
    
    @abstractmethod
    def save(self, position: Position) -> None:
        """
        Save or update a position.
        
        Args:
            position: Position entity to save
        """
        pass
    
    @abstractmethod
    def find_by_id(self, position_id: UUID) -> Optional[Position]:
        """
        Find position by ID.
        
        Args:
            position_id: Position UUID
            
        Returns:
            Position entity or None if not found
        """
        pass
    
    @abstractmethod
    def find_open_positions(
        self,
        portfolio_id: Optional[UUID] = None,
        symbol: Optional[str] = None
    ) -> List[Position]:
        """
        Find all open positions with optional filters.
        
        Args:
            portfolio_id: Optional portfolio filter
            symbol: Optional symbol filter
            
        Returns:
            List of open Position entities
        """
        pass
    
    @abstractmethod
    def find_by_symbol_and_portfolio(
        self,
        symbol: str,
        portfolio_id: UUID
    ) -> Optional[Position]:
        """
        Find open position for a symbol in a portfolio.
        
        Args:
            symbol: Trading symbol
            portfolio_id: Portfolio UUID
            
        Returns:
            Position entity or None if not found
        """
        pass
    
    @abstractmethod
    def find_positions_at_risk(
        self,
        margin_threshold: float = 0.05,
        portfolio_id: Optional[UUID] = None
    ) -> List[Position]:
        """
        Find positions at risk of liquidation.
        
        Args:
            margin_threshold: Margin ratio threshold (default 5%)
            portfolio_id: Optional portfolio filter
            
        Returns:
            List of at-risk Position entities
        """
        pass
    
    @abstractmethod
    def find_recently_closed(
        self,
        portfolio_id: Optional[UUID] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[Position]:
        """
        Find recently closed positions.
        
        Args:
            portfolio_id: Optional portfolio filter
            hours: Number of hours to look back
            limit: Maximum number of positions to return
            
        Returns:
            List of recently closed Position entities
        """
        pass
    
    @abstractmethod
    def get_portfolio_exposure(self, portfolio_id: UUID) -> Dict[str, Decimal]:
        """
        Calculate total exposure by symbol for a portfolio.
        
        Args:
            portfolio_id: Portfolio UUID
            
        Returns:
            Dictionary of symbol to exposure amount
        """
        pass
    
    @abstractmethod
    def update_mark_prices(self, price_updates: Dict[str, Decimal]) -> int:
        """
        Batch update mark prices for multiple positions.
        
        Args:
            price_updates: Dictionary of symbol to new price
            
        Returns:
            Number of positions updated
        """
        pass
    
    @abstractmethod
    def close_position(self, position_id: UUID, close_price: Decimal) -> bool:
        """
        Mark a position as closed.
        
        Args:
            position_id: Position UUID
            close_price: Closing price
            
        Returns:
            True if closed, False if not found
        """
        pass
    
    @abstractmethod
    def delete(self, position_id: UUID) -> bool:
        """
        Delete a position.
        
        Args:
            position_id: Position UUID
            
        Returns:
            True if deleted, False if not found
        """
        pass