import logging
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session

from src.domain.trading.repositories.portfolio_repository import IPortfolioRepository
from src.domain.trading.aggregates.portfolio import Portfolio
from ..models.portfolio_model import PortfolioModel
from ..models.base import get_session

logger = logging.getLogger(__name__)


class PostgresPortfolioRepository(IPortfolioRepository):
    """
    PostgreSQL implementation of Portfolio repository.
    
    Handles persistence and retrieval of Portfolio aggregates.
    """
    
    def __init__(self, session: Session = None):
        """
        Initialize repository.
        
        Args:
            session: Optional SQLAlchemy session. If not provided, will create new sessions.
        """
        self._session = session
    
    def save(self, portfolio: Portfolio) -> None:
        """
        Save or update a portfolio.
        
        Args:
            portfolio: Portfolio aggregate to save
        """
        try:
            with get_session() as session:
                # Check if portfolio exists
                existing = session.query(PortfolioModel).filter_by(id=portfolio.id).first()
                
                if existing:
                    # Update existing portfolio
                    self._update_model_from_aggregate(existing, portfolio)
                else:
                    # Create new portfolio
                    model = PortfolioModel.from_domain(portfolio)
                    session.add(model)
                
                session.commit()
                logger.info(f"Portfolio {portfolio.id} saved successfully")
                
        except Exception as e:
            logger.error(f"Failed to save portfolio {portfolio.id}: {e}")
            raise
    
    def find_by_id(self, portfolio_id: UUID) -> Optional[Portfolio]:
        """
        Find portfolio by ID.
        
        Args:
            portfolio_id: Portfolio UUID
            
        Returns:
            Portfolio aggregate or None if not found
        """
        try:
            with get_session() as session:
                model = session.query(PortfolioModel).filter_by(id=portfolio_id).first()
                
                if not model:
                    return None
                
                return self._aggregate_from_model(model)
                
        except Exception as e:
            logger.error(f"Failed to find portfolio {portfolio_id}: {e}")
            raise
    
    def find_by_name(self, name: str) -> Optional[Portfolio]:
        """
        Find portfolio by name.
        
        Args:
            name: Portfolio name
            
        Returns:
            Portfolio aggregate or None if not found
        """
        try:
            with get_session() as session:
                model = session.query(PortfolioModel).filter_by(name=name).first()
                
                if not model:
                    return None
                
                return self._aggregate_from_model(model)
                
        except Exception as e:
            logger.error(f"Failed to find portfolio by name {name}: {e}")
            raise
    
    def find_all_active(self) -> List[Portfolio]:
        """
        Find all active portfolios.
        
        Returns:
            List of active Portfolio aggregates
        """
        try:
            with get_session() as session:
                models = session.query(PortfolioModel).filter_by(is_active=True).all()
                
                return [self._aggregate_from_model(m) for m in models]
                
        except Exception as e:
            logger.error(f"Failed to find active portfolios: {e}")
            raise
    
    def find_live_portfolios(self) -> List[Portfolio]:
        """
        Find all live trading portfolios.
        
        Returns:
            List of live Portfolio aggregates
        """
        try:
            with get_session() as session:
                models = session.query(PortfolioModel).filter_by(
                    is_active=True,
                    is_live=True
                ).all()
                
                return [self._aggregate_from_model(m) for m in models]
                
        except Exception as e:
            logger.error(f"Failed to find live portfolios: {e}")
            raise
    
    def update_balance(
        self,
        portfolio_id: UUID,
        available: Optional[Decimal] = None,
        reserved: Optional[Decimal] = None
    ) -> bool:
        """
        Update portfolio balances.
        
        Args:
            portfolio_id: Portfolio UUID
            available: New available balance
            reserved: New reserved balance
            
        Returns:
            True if updated, False if not found
        """
        try:
            with get_session() as session:
                model = session.query(PortfolioModel).filter_by(id=portfolio_id).first()
                
                if not model:
                    return False
                
                if available is not None:
                    model.available_balance = available
                
                if reserved is not None:
                    model.reserved_balance = reserved
                
                session.commit()
                
                logger.info(f"Portfolio {portfolio_id} balances updated")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update portfolio {portfolio_id} balances: {e}")
            raise
    
    def update_pnl(
        self,
        portfolio_id: UUID,
        realized: Optional[Decimal] = None,
        unrealized: Optional[Decimal] = None
    ) -> bool:
        """
        Update portfolio PnL.
        
        Args:
            portfolio_id: Portfolio UUID
            realized: Realized PnL to add
            unrealized: New unrealized PnL
            
        Returns:
            True if updated, False if not found
        """
        try:
            with get_session() as session:
                model = session.query(PortfolioModel).filter_by(id=portfolio_id).first()
                
                if not model:
                    return False
                
                model.update_pnl(
                    realized=float(realized) if realized else None,
                    unrealized=float(unrealized) if unrealized else None
                )
                
                session.commit()
                
                logger.info(f"Portfolio {portfolio_id} PnL updated")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update portfolio {portfolio_id} PnL: {e}")
            raise
    
    def delete(self, portfolio_id: UUID) -> bool:
        """
        Delete a portfolio.
        
        Args:
            portfolio_id: Portfolio UUID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            with get_session() as session:
                model = session.query(PortfolioModel).filter_by(id=portfolio_id).first()
                
                if not model:
                    return False
                
                session.delete(model)
                session.commit()
                
                logger.info(f"Portfolio {portfolio_id} deleted")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete portfolio {portfolio_id}: {e}")
            raise
    
    def _aggregate_from_model(self, model: PortfolioModel) -> Portfolio:
        """
        Convert database model to domain aggregate.
        
        Args:
            model: PortfolioModel instance
            
        Returns:
            Portfolio aggregate
        """
        # Create portfolio with basic fields
        portfolio = Portfolio(
            id=model.id,
            name=model.name,
            available_cash=model.available_balance,
            reserved_cash=model.reserved_balance or Decimal("0"),
            currency=model.currency
        )
        
        # Note: Positions would need to be loaded separately
        # In a real implementation, you might want to lazy-load them
        # or use a separate query
        
        return portfolio
    
    def _update_model_from_aggregate(self, model: PortfolioModel, portfolio: Portfolio) -> None:
        """
        Update database model from domain aggregate.
        
        Args:
            model: PortfolioModel to update
            portfolio: Portfolio aggregate with new data
        """
        model.available_balance = portfolio.available_cash
        model.reserved_balance = portfolio.reserved_cash
        
        # Update positions count if available
        if hasattr(portfolio, 'positions'):
            # Note: This would need proper position tracking
            pass
        
        # Update trading statistics
        # In production, these would be calculated from actual trades
        model.total_trades = getattr(portfolio, 'total_trades', model.total_trades)