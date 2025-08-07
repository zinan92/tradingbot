import pytest
from datetime import datetime
from uuid import uuid4

from src.domain.trading.aggregates.order import (
    Order,
    OrderStatus,
    CannotCancelFilledOrderError,
    OrderAlreadyCancelledError,
    OrderAlreadyFilledError,
    CannotFillCancelledOrderError,
)
from src.domain.trading.events import (
    OrderPlaced,
    OrderCancelled,
    OrderFilled,
)


class TestOrderAggregate:
    """Unit tests for Order aggregate"""
    
    def test_create_order(self):
        """Test creating a new order"""
        # Act
        order = Order.create(
            symbol="AAPL",
            quantity=100,
            order_type="MARKET",
            price=None
        )
        
        # Assert
        assert order.id is not None
        assert order.symbol == "AAPL"
        assert order.quantity == 100
        assert order.order_type == "MARKET"
        assert order.price is None
        assert order.status == OrderStatus.PENDING
        assert order.created_at is not None
        assert order.filled_at is None
        assert order.cancelled_at is None
        
        # Check domain event was recorded
        events = order.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], OrderPlaced)
    
    def test_create_limit_order_with_price(self):
        """Test creating a limit order with price"""
        # Act
        order = Order.create(
            symbol="MSFT",
            quantity=50,
            order_type="LIMIT",
            price=300.50
        )
        
        # Assert
        assert order.symbol == "MSFT"
        assert order.quantity == 50
        assert order.order_type == "LIMIT"
        assert order.price == 300.50
        assert order.status == OrderStatus.PENDING
    
    def test_cancel_pending_order(self):
        """Test cancelling a pending order"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        user_id = uuid4()
        
        # Act
        event = order.cancel(reason="User cancelled", cancelled_by=user_id)
        
        # Assert
        assert order.status == OrderStatus.CANCELLED
        assert order.cancelled_at is not None
        assert order.cancellation_reason == "User cancelled"
        assert event.order_id == order.id
        assert event.reason == "User cancelled"
        assert event.cancelled_by == user_id
        assert event.original_quantity == 100
        assert event.symbol == "AAPL"
        
        # Check domain event was recorded
        events = order.pull_events()
        assert len(events) == 2  # OrderPlaced and OrderCancelled
        assert isinstance(events[1], OrderCancelled)
    
    def test_cannot_cancel_filled_order(self):
        """Test that filled orders cannot be cancelled"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        order.fill()
        
        # Act & Assert
        with pytest.raises(CannotCancelFilledOrderError) as exc:
            order.cancel()
        assert "already filled" in str(exc.value)
    
    def test_cannot_cancel_already_cancelled_order(self):
        """Test that cancelled orders cannot be cancelled again"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        order.cancel()
        
        # Act & Assert
        with pytest.raises(OrderAlreadyCancelledError) as exc:
            order.cancel()
        assert "already cancelled" in str(exc.value)
    
    def test_fill_pending_order(self):
        """Test filling a pending order"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        fill_time = datetime.utcnow()
        
        # Act
        order.fill(fill_time)
        
        # Assert
        assert order.status == OrderStatus.FILLED
        assert order.filled_at == fill_time
        
        # Check domain event was recorded
        events = order.pull_events()
        assert len(events) == 2  # OrderPlaced and OrderFilled
        assert isinstance(events[1], OrderFilled)
    
    def test_fill_order_without_timestamp(self):
        """Test filling an order without providing timestamp"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        
        # Act
        order.fill()
        
        # Assert
        assert order.status == OrderStatus.FILLED
        assert order.filled_at is not None
    
    def test_cannot_fill_already_filled_order(self):
        """Test that filled orders cannot be filled again"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        order.fill()
        
        # Act & Assert
        with pytest.raises(OrderAlreadyFilledError) as exc:
            order.fill()
        assert "already filled" in str(exc.value)
    
    def test_cannot_fill_cancelled_order(self):
        """Test that cancelled orders cannot be filled"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        order.cancel()
        
        # Act & Assert
        with pytest.raises(CannotFillCancelledOrderError) as exc:
            order.fill()
        assert "cancelled" in str(exc.value)
    
    def test_set_broker_order_id(self):
        """Test setting broker order ID"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        broker_id = "BROKER-12345"
        
        # Act
        order.set_broker_order_id(broker_id)
        
        # Assert
        assert order.broker_order_id == broker_id
    
    def test_order_status_predicates(self):
        """Test order status predicate methods"""
        # Arrange
        pending_order = Order.create("AAPL", 100, "MARKET")
        filled_order = Order.create("MSFT", 50, "MARKET")
        filled_order.fill()
        cancelled_order = Order.create("GOOGL", 25, "MARKET")
        cancelled_order.cancel()
        
        # Assert pending order
        assert pending_order.is_pending() is True
        assert pending_order.is_filled() is False
        assert pending_order.is_cancelled() is False
        
        # Assert filled order
        assert filled_order.is_pending() is False
        assert filled_order.is_filled() is True
        assert filled_order.is_cancelled() is False
        
        # Assert cancelled order
        assert cancelled_order.is_pending() is False
        assert cancelled_order.is_filled() is False
        assert cancelled_order.is_cancelled() is True
    
    def test_pull_events_clears_events(self):
        """Test that pulling events clears the event list"""
        # Arrange
        order = Order.create("AAPL", 100, "MARKET")
        
        # Act
        first_pull = order.pull_events()
        second_pull = order.pull_events()
        
        # Assert
        assert len(first_pull) == 1
        assert len(second_pull) == 0  # Events cleared after first pull