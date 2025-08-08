import logging
from typing import Optional, List, Dict
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from src.domain.trading.repositories.position_repository import IPositionRepository
from src.domain.trading.entities.position import Position
from src.domain.trading.value_objects.price import Price
from src.domain.trading.value_objects.quantity import Quantity
from src.domain.trading.value_objects.leverage import Leverage
from src.domain.trading.value_objects.side import PositionSide
from ..models.position_model import PositionModel
from ..models.base import get_session

logger = logging.getLogger(__name__)


class PostgresPositionRepository(IPositionRepository):
    """
    PostgreSQL implementation of Position repository.
    
    Handles persistence and retrieval of Position entities.
    """
    
    def __init__(self, session: Session = None):
        """
        Initialize repository.
        
        Args:
            session: Optional SQLAlchemy session. If not provided, will create new sessions.
        """
        self._session = session
    
    def save(self, position: Position) -> None:
        """
        Save or update a position.
        
        Args:
            position: Position entity to save
        """
        try:
            with get_session() as session:
                # Check if position exists
                existing = session.query(PositionModel).filter_by(id=position.id).first()
                
                if existing:
                    # Update existing position
                    self._update_model_from_entity(existing, position)
                else:
                    # Create new position
                    model = self._model_from_entity(position)
                    session.add(model)
                
                session.commit()
                logger.info(f"Position {position.id} saved successfully")
                
        except Exception as e:
            logger.error(f"Failed to save position {position.id}: {e}")
            raise
    
    def find_by_id(self, position_id: UUID) -> Optional[Position]:
        """
        Find position by ID.
        
        Args:
            position_id: Position UUID
            
        Returns:
            Position entity or None if not found
        """
        try:
            with get_session() as session:
                model = session.query(PositionModel).filter_by(id=position_id).first()
                
                if not model:
                    return None
                
                return self._entity_from_model(model)
                
        except Exception as e:
            logger.error(f"Failed to find position {position_id}: {e}")
            raise
    
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
        try:
            with get_session() as session:
                query = session.query(PositionModel).filter(
                    PositionModel.is_open == True
                )
                
                if portfolio_id:
                    query = query.filter(PositionModel.portfolio_id == portfolio_id)
                
                if symbol:
                    query = query.filter(PositionModel.symbol == symbol)
                
                models = query.all()
                
                return [self._entity_from_model(m) for m in models]
                
        except Exception as e:
            logger.error(f"Failed to find open positions: {e}")
            raise
    
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
        try:
            with get_session() as session:
                model = session.query(PositionModel).filter(
                    and_(
                        PositionModel.symbol == symbol,
                        PositionModel.portfolio_id == portfolio_id,
                        PositionModel.is_open == True
                    )
                ).first()
                
                if not model:
                    return None
                
                return self._entity_from_model(model)
                
        except Exception as e:
            logger.error(f"Failed to find position for {symbol} in portfolio {portfolio_id}: {e}")
            raise
    
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
        try:
            with get_session() as session:
                query = session.query(PositionModel).filter(
                    and_(
                        PositionModel.is_open == True,
                        PositionModel.margin_ratio <= margin_threshold,
                        PositionModel.margin_ratio > 0
                    )
                )
                
                if portfolio_id:
                    query = query.filter(PositionModel.portfolio_id == portfolio_id)
                
                models = query.all()
                
                return [self._entity_from_model(m) for m in models]
                
        except Exception as e:
            logger.error(f"Failed to find positions at risk: {e}")
            raise
    
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
        try:
            with get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                
                query = session.query(PositionModel).filter(
                    and_(
                        PositionModel.is_open == False,
                        PositionModel.closed_at >= cutoff_time
                    )
                )
                
                if portfolio_id:
                    query = query.filter(PositionModel.portfolio_id == portfolio_id)
                
                query = query.order_by(desc(PositionModel.closed_at)).limit(limit)
                
                models = query.all()
                
                return [self._entity_from_model(m) for m in models]
                
        except Exception as e:
            logger.error(f"Failed to find recently closed positions: {e}")
            raise
    
    def get_portfolio_exposure(self, portfolio_id: UUID) -> Dict[str, Decimal]:
        """
        Calculate total exposure by symbol for a portfolio.
        
        Args:
            portfolio_id: Portfolio UUID
            
        Returns:
            Dictionary of symbol to exposure amount
        """
        try:
            with get_session() as session:
                positions = session.query(PositionModel).filter(
                    and_(
                        PositionModel.portfolio_id == portfolio_id,
                        PositionModel.is_open == True
                    )
                ).all()
                
                exposure = {}
                for pos in positions:
                    value = pos.quantity * pos.mark_price
                    if pos.symbol in exposure:
                        exposure[pos.symbol] += value
                    else:
                        exposure[pos.symbol] = value
                
                return exposure
                
        except Exception as e:
            logger.error(f"Failed to calculate portfolio exposure: {e}")
            raise
    
    def update_mark_prices(self, price_updates: Dict[str, Decimal]) -> int:
        """
        Batch update mark prices for multiple positions.
        
        Args:
            price_updates: Dictionary of symbol to new price
            
        Returns:
            Number of positions updated
        """
        try:
            with get_session() as session:
                updated_count = 0
                
                for symbol, price in price_updates.items():
                    positions = session.query(PositionModel).filter(
                        and_(
                            PositionModel.symbol == symbol,
                            PositionModel.is_open == True
                        )
                    ).all()
                    
                    for pos in positions:
                        pos.mark_price = price
                        pos.last_update = datetime.utcnow()
                        
                        # Recalculate PnL and margin ratio
                        self._update_position_metrics(pos)
                        updated_count += 1
                
                session.commit()
                
                logger.info(f"Updated mark prices for {updated_count} positions")
                return updated_count
                
        except Exception as e:
            logger.error(f"Failed to update mark prices: {e}")
            raise
    
    def close_position(self, position_id: UUID, close_price: Decimal) -> bool:
        """
        Mark a position as closed.
        
        Args:
            position_id: Position UUID
            close_price: Closing price
            
        Returns:
            True if closed, False if not found
        """
        try:
            with get_session() as session:
                model = session.query(PositionModel).filter_by(id=position_id).first()
                
                if not model:
                    return False
                
                # Calculate final PnL
                final_pnl = self._calculate_pnl(
                    model.side,
                    model.quantity,
                    model.entry_price,
                    close_price,
                    model.leverage
                )
                
                model.realized_pnl += final_pnl
                model.unrealized_pnl = Decimal("0")
                model.is_open = False
                model.closed_at = datetime.utcnow()
                
                session.commit()
                
                logger.info(f"Position {position_id} closed at {close_price}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to close position {position_id}: {e}")
            raise
    
    def delete(self, position_id: UUID) -> bool:
        """
        Delete a position.
        
        Args:
            position_id: Position UUID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            with get_session() as session:
                model = session.query(PositionModel).filter_by(id=position_id).first()
                
                if not model:
                    return False
                
                session.delete(model)
                session.commit()
                
                logger.info(f"Position {position_id} deleted")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete position {position_id}: {e}")
            raise
    
    def _entity_from_model(self, model: PositionModel) -> Position:
        """
        Convert database model to domain entity.
        
        Args:
            model: PositionModel instance
            
        Returns:
            Position entity
        """
        position = Position(
            id=model.id,
            symbol=model.symbol,
            side=PositionSide[model.side],
            quantity=Quantity(model.quantity),
            entry_price=Price(model.entry_price),
            leverage=Leverage(model.leverage),
            mark_price=Price(model.mark_price) if model.mark_price else None,
            last_update=model.last_update,
            initial_margin=model.initial_margin,
            maintenance_margin=model.maintenance_margin,
            margin_ratio=model.margin_ratio,
            unrealized_pnl=model.unrealized_pnl,
            realized_pnl=model.realized_pnl,
            liquidation_price=Price(model.liquidation_price) if model.liquidation_price else None,
            portfolio_id=model.portfolio_id,
            created_at=model.created_at,
            closed_at=model.closed_at,
            is_open=model.is_open
        )
        
        return position
    
    def _model_from_entity(self, position: Position) -> PositionModel:
        """
        Convert domain entity to database model.
        
        Args:
            position: Position entity
            
        Returns:
            PositionModel instance
        """
        model = PositionModel(
            id=position.id,
            symbol=position.symbol,
            side=position.side.value,
            quantity=position.quantity.value,
            entry_price=position.entry_price.value,
            leverage=position.leverage.value,
            mark_price=position.mark_price.value if position.mark_price else position.entry_price.value,
            last_update=position.last_update,
            initial_margin=position.initial_margin,
            maintenance_margin=position.maintenance_margin,
            margin_ratio=position.margin_ratio,
            unrealized_pnl=position.unrealized_pnl,
            realized_pnl=position.realized_pnl,
            liquidation_price=position.liquidation_price.value if position.liquidation_price else None,
            portfolio_id=position.portfolio_id,
            created_at=position.created_at,
            closed_at=position.closed_at,
            is_open=position.is_open
        )
        
        return model
    
    def _update_model_from_entity(self, model: PositionModel, position: Position) -> None:
        """
        Update database model from domain entity.
        
        Args:
            model: PositionModel to update
            position: Position entity with new data
        """
        model.quantity = position.quantity.value
        model.entry_price = position.entry_price.value
        model.leverage = position.leverage.value
        model.mark_price = position.mark_price.value if position.mark_price else model.mark_price
        model.last_update = position.last_update
        model.initial_margin = position.initial_margin
        model.maintenance_margin = position.maintenance_margin
        model.margin_ratio = position.margin_ratio
        model.unrealized_pnl = position.unrealized_pnl
        model.realized_pnl = position.realized_pnl
        model.liquidation_price = position.liquidation_price.value if position.liquidation_price else None
        model.closed_at = position.closed_at
        model.is_open = position.is_open
        model.updated_at = datetime.utcnow()
    
    def _update_position_metrics(self, model: PositionModel) -> None:
        """
        Update position PnL and margin metrics.
        
        Args:
            model: PositionModel to update
        """
        if not model.mark_price or not model.is_open:
            return
        
        # Calculate unrealized PnL
        model.unrealized_pnl = self._calculate_pnl(
            model.side,
            model.quantity,
            model.entry_price,
            model.mark_price,
            model.leverage
        )
        
        # Calculate margin ratio
        position_value = model.mark_price * model.quantity
        if position_value > 0:
            available_margin = model.initial_margin + model.unrealized_pnl
            model.margin_ratio = available_margin / position_value
        else:
            model.margin_ratio = Decimal("0")
    
    def _calculate_pnl(
        self,
        side: str,
        quantity: int,
        entry_price: Decimal,
        current_price: Decimal,
        leverage: int
    ) -> Decimal:
        """
        Calculate PnL for a position.
        
        Args:
            side: Position side (LONG/SHORT)
            quantity: Position quantity
            entry_price: Entry price
            current_price: Current price
            leverage: Position leverage
            
        Returns:
            PnL amount
        """
        if side == "LONG":
            pnl = (current_price - entry_price) * Decimal(str(quantity))
        else:  # SHORT
            pnl = (entry_price - current_price) * Decimal(str(quantity))
        
        return pnl