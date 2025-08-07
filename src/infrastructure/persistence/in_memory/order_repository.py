from typing import Dict, List, Optional
from uuid import UUID
import copy

from src.domain.trading.aggregates.order import Order
from src.domain.trading.repositories import IOrderRepository, OrderNotFoundError


class InMemoryOrderRepository(IOrderRepository):
    """
    In-memory implementation of IOrderRepository for testing
    
    Stores orders in a dictionary for fast lookups.
    Creates deep copies to prevent external modifications.
    """
    
    def __init__(self):
        self._orders: Dict[UUID, Order] = {}
        self._broker_order_index: Dict[str, UUID] = {}  # broker_order_id -> order_id
    
    def get(self, order_id: UUID) -> Optional[Order]:
        """Retrieve an order by its ID"""
        order = self._orders.get(order_id)
        return copy.deepcopy(order) if order else None
    
    def save(self, order: Order) -> None:
        """Save or update an order"""
        # Deep copy to prevent external modifications
        order_copy = copy.deepcopy(order)
        self._orders[order.id] = order_copy
        
        # Update broker order index if present
        if order.broker_order_id:
            self._broker_order_index[order.broker_order_id] = order.id
    
    def get_by_portfolio(self, portfolio_id: UUID) -> List[Order]:
        """Retrieve all orders for a specific portfolio"""
        # In a real implementation, orders would track their portfolio_id
        # For now, returning empty list as orders don't have portfolio_id yet
        # This would need to be added to the Order aggregate
        return []
    
    def get_pending_orders(self, portfolio_id: Optional[UUID] = None) -> List[Order]:
        """Retrieve all pending orders"""
        pending_orders = [
            copy.deepcopy(order) 
            for order in self._orders.values() 
            if order.is_pending()
        ]
        
        # If portfolio_id is provided, filter by it
        # Note: This requires Order to track portfolio_id
        if portfolio_id:
            # For now, return all pending orders
            pass
        
        return pending_orders
    
    def get_by_broker_order_id(self, broker_order_id: str) -> Optional[Order]:
        """Retrieve an order by broker's order ID"""
        order_id = self._broker_order_index.get(broker_order_id)
        if order_id:
            return self.get(order_id)
        return None
    
    def exists(self, order_id: UUID) -> bool:
        """Check if an order exists"""
        return order_id in self._orders
    
    def clear(self) -> None:
        """Clear all orders (useful for testing)"""
        self._orders.clear()
        self._broker_order_index.clear()
    
    def count(self) -> int:
        """Get total number of orders (useful for testing)"""
        return len(self._orders)