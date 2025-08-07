from typing import Dict, List, Optional
from uuid import UUID
import copy

from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.repositories import (
    IPortfolioRepository,
    PortfolioNotFoundError,
    DuplicatePortfolioError,
)


class InMemoryPortfolioRepository(IPortfolioRepository):
    """
    In-memory implementation of IPortfolioRepository for testing
    
    Stores portfolios in memory with indexing for fast lookups.
    Creates deep copies to prevent external modifications.
    """
    
    def __init__(self):
        self._portfolios: Dict[UUID, Portfolio] = {}
        self._name_index: Dict[str, UUID] = {}  # name -> portfolio_id
    
    def get(self, portfolio_id: UUID) -> Optional[Portfolio]:
        """Retrieve a portfolio by its ID"""
        portfolio = self._portfolios.get(portfolio_id)
        return copy.deepcopy(portfolio) if portfolio else None
    
    def save(self, portfolio: Portfolio) -> None:
        """Save or update a portfolio"""
        # Check for duplicate names (except when updating same portfolio)
        existing_id = self._name_index.get(portfolio.name)
        if existing_id and existing_id != portfolio.id:
            raise DuplicatePortfolioError(
                f"Portfolio with name '{portfolio.name}' already exists"
            )
        
        # Deep copy to prevent external modifications
        portfolio_copy = copy.deepcopy(portfolio)
        self._portfolios[portfolio.id] = portfolio_copy
        self._name_index[portfolio.name] = portfolio.id
    
    def get_by_name(self, name: str) -> Optional[Portfolio]:
        """Retrieve a portfolio by its name"""
        portfolio_id = self._name_index.get(name)
        if portfolio_id:
            return self.get(portfolio_id)
        return None
    
    def get_all(self) -> List[Portfolio]:
        """Retrieve all portfolios"""
        return [copy.deepcopy(p) for p in self._portfolios.values()]
    
    def exists(self, portfolio_id: UUID) -> bool:
        """Check if a portfolio exists"""
        return portfolio_id in self._portfolios
    
    def delete(self, portfolio_id: UUID) -> bool:
        """Delete a portfolio (soft delete in real implementation)"""
        portfolio = self._portfolios.get(portfolio_id)
        if portfolio:
            # Remove from both indices
            del self._portfolios[portfolio_id]
            if portfolio.name in self._name_index:
                del self._name_index[portfolio.name]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all portfolios (useful for testing)"""
        self._portfolios.clear()
        self._name_index.clear()
    
    def count(self) -> int:
        """Get total number of portfolios (useful for testing)"""
        return len(self._portfolios)