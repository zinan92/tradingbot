import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from src.domain.trading.repositories.order_repository import IOrderRepository
from src.domain.trading.aggregates.order import Order, OrderStatus
from ..models.order_model import OrderModel, OrderStatusEnum
from ..models.base import get_session

logger = logging.getLogger(__name__)


class PostgresOrderRepository(IOrderRepository):
    """
    PostgreSQL implementation of Order repository.
    
    Handles persistence and retrieval of Order aggregates.
    """
    
    def __init__(self, session: Session = None):
        """
        Initialize repository.
        
        Args:
            session: Optional SQLAlchemy session. If not provided, will create new sessions.
        """
        self._session = session
    
    def _get_session(self) -> Session:
        """Get database session."""
        if self._session:
            return self._session
        # This should be handled better in production with proper session management
        raise RuntimeError("No session provided to repository")
    
    def save(self, order: Order) -> None:
        """
        Save or update an order.
        
        Args:
            order: Order aggregate to save
        """
        try:
            with get_session() as session:
                # Check if order exists
                existing = session.query(OrderModel).filter_by(id=order.id).first()
                
                if existing:
                    # Update existing order
                    self._update_model_from_aggregate(existing, order)
                else:
                    # Create new order
                    model = OrderModel.from_domain(order)
                    session.add(model)
                
                session.commit()
                logger.info(f"Order {order.id} saved successfully")
                
        except Exception as e:
            logger.error(f"Failed to save order {order.id}: {e}")
            raise
    
    def find_by_id(self, order_id: UUID) -> Optional[Order]:
        """
        Find order by ID.
        
        Args:
            order_id: Order UUID
            
        Returns:
            Order aggregate or None if not found
        """
        try:
            with get_session() as session:
                model = session.query(OrderModel).filter_by(id=order_id).first()
                
                if not model:
                    return None
                
                return self._aggregate_from_model(model)
                
        except Exception as e:
            logger.error(f"Failed to find order {order_id}: {e}")
            raise
    
    def find_by_broker_order_id(self, broker_order_id: str) -> Optional[Order]:
        """
        Find order by broker order ID.
        
        Args:
            broker_order_id: Broker's order identifier
            
        Returns:
            Order aggregate or None if not found
        """
        try:
            with get_session() as session:
                model = session.query(OrderModel).filter_by(
                    broker_order_id=broker_order_id
                ).first()
                
                if not model:
                    return None
                
                return self._aggregate_from_model(model)
                
        except Exception as e:
            logger.error(f"Failed to find order by broker ID {broker_order_id}: {e}")
            raise
    
    def find_pending_orders(self, portfolio_id: Optional[UUID] = None) -> List[Order]:
        """
        Find all pending orders.
        
        Args:
            portfolio_id: Optional portfolio filter
            
        Returns:
            List of pending Order aggregates
        """
        try:
            with get_session() as session:
                query = session.query(OrderModel).filter(
                    OrderModel.status == OrderStatusEnum.PENDING
                )
                
                if portfolio_id:
                    query = query.filter(OrderModel.portfolio_id == portfolio_id)
                
                models = query.all()
                
                return [self._aggregate_from_model(m) for m in models]
                
        except Exception as e:
            logger.error(f"Failed to find pending orders: {e}")
            raise
    
    def find_orders_by_symbol(
        self,
        symbol: str,
        portfolio_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[Order]:
        """
        Find orders by symbol.
        
        Args:
            symbol: Trading symbol
            portfolio_id: Optional portfolio filter
            limit: Maximum number of orders to return
            
        Returns:
            List of Order aggregates
        """
        try:
            with get_session() as session:
                query = session.query(OrderModel).filter(
                    OrderModel.symbol == symbol
                )
                
                if portfolio_id:
                    query = query.filter(OrderModel.portfolio_id == portfolio_id)
                
                query = query.order_by(desc(OrderModel.created_at)).limit(limit)
                
                models = query.all()
                
                return [self._aggregate_from_model(m) for m in models]
                
        except Exception as e:
            logger.error(f"Failed to find orders for symbol {symbol}: {e}")
            raise
    
    def find_recent_orders(
        self,
        portfolio_id: Optional[UUID] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[Order]:
        """
        Find recent orders.
        
        Args:
            portfolio_id: Optional portfolio filter
            hours: Number of hours to look back
            limit: Maximum number of orders to return
            
        Returns:
            List of recent Order aggregates
        """
        try:
            with get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                
                query = session.query(OrderModel).filter(
                    OrderModel.created_at >= cutoff_time
                )
                
                if portfolio_id:
                    query = query.filter(OrderModel.portfolio_id == portfolio_id)
                
                query = query.order_by(desc(OrderModel.created_at)).limit(limit)
                
                models = query.all()
                
                return [self._aggregate_from_model(m) for m in models]
                
        except Exception as e:
            logger.error(f"Failed to find recent orders: {e}")
            raise
    
    def count_orders(
        self,
        portfolio_id: Optional[UUID] = None,
        status: Optional[OrderStatus] = None
    ) -> int:
        """
        Count orders with optional filters.
        
        Args:
            portfolio_id: Optional portfolio filter
            status: Optional status filter
            
        Returns:
            Count of orders
        """
        try:
            with get_session() as session:
                query = session.query(OrderModel)
                
                if portfolio_id:
                    query = query.filter(OrderModel.portfolio_id == portfolio_id)
                
                if status:
                    query = query.filter(
                        OrderModel.status == OrderStatusEnum[status.value]
                    )
                
                return query.count()
                
        except Exception as e:
            logger.error(f"Failed to count orders: {e}")
            raise
    
    def delete(self, order_id: UUID) -> bool:
        """
        Delete an order.
        
        Args:
            order_id: Order UUID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            with get_session() as session:
                model = session.query(OrderModel).filter_by(id=order_id).first()
                
                if not model:
                    return False
                
                session.delete(model)
                session.commit()
                
                logger.info(f"Order {order_id} deleted")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete order {order_id}: {e}")
            raise
    
    def _aggregate_from_model(self, model: OrderModel) -> Order:
        """
        Convert database model to domain aggregate.
        
        Args:
            model: OrderModel instance
            
        Returns:
            Order aggregate
        """
        # Create order with basic fields
        order = Order(
            id=model.id,
            symbol=model.symbol,
            quantity=int(model.quantity),
            order_type=model.order_type.value if model.order_type else "MARKET",
            price=float(model.price) if model.price else None,
            status=OrderStatus[model.status.value] if model.status else OrderStatus.PENDING,
            created_at=model.created_at,
            filled_at=model.filled_at,
            cancelled_at=model.cancelled_at,
            cancellation_reason=model.cancellation_reason,
            broker_order_id=model.broker_order_id
        )
        
        # Set additional fields if present
        if model.cancelled_by:
            order.cancelled_by = model.cancelled_by
        
        if model.average_fill_price:
            order.fill_price = float(model.average_fill_price)
        
        return order
    
    def _update_model_from_aggregate(self, model: OrderModel, order: Order) -> None:
        """
        Update database model from domain aggregate.
        
        Args:
            model: OrderModel to update
            order: Order aggregate with new data
        """
        model.status = OrderStatusEnum[order.status.value]
        model.filled_at = order.filled_at
        model.cancelled_at = order.cancelled_at
        model.cancellation_reason = order.cancellation_reason
        model.broker_order_id = order.broker_order_id
        
        # Update fill information if available
        if hasattr(order, 'fill_price') and order.fill_price:
            model.average_fill_price = order.fill_price
        
        if hasattr(order, 'filled_quantity'):
            model.filled_quantity = order.filled_quantity
        
        model.updated_at = datetime.utcnow()