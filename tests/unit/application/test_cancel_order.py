import pytest
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, List, Any
from unittest.mock import Mock, MagicMock, patch, call
from uuid import UUID, uuid4

from src.application.trading.commands.cancel_order_command import (
    CancelOrderCommand,
    CancelOrderCommandHandler,
    CancelOrderResult,
    BrokerCancellationError
)
from src.domain.trading.aggregates.order import (
    Order,
    OrderStatus,
    CannotCancelFilledOrderError,
    OrderAlreadyCancelledError
)
from src.domain.trading.events import OrderCancelled, OrderPlaced
from src.domain.trading.repositories import OrderNotFoundError


class MockOrderRepository:
    """Mock implementation of IOrderRepository for testing"""
    
    def __init__(self):
        self.orders: Dict[UUID, Order] = {}
        self.save_called = False
        self.save_count = 0
        self.get_called = False
        self.get_count = 0
    
    def save(self, order: Order) -> None:
        """Save order to repository"""
        self.save_called = True
        self.save_count += 1
        self.orders[order.id] = order
    
    def get(self, order_id: UUID) -> Optional[Order]:
        """Get order by ID"""
        self.get_called = True
        self.get_count += 1
        return self.orders.get(order_id)
    
    def add_order(self, order: Order) -> None:
        """Helper method to add order to test repository"""
        self.orders[order.id] = order


class MockBrokerService:
    """Mock implementation of broker service for testing"""
    
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.cancel_order_sync_called = False
        self.cancel_order_sync_count = 0
        self.cancelled_orders: List[str] = []
    
    def cancel_order_sync(self, broker_order_id: str) -> bool:
        """Mock cancel order synchronously"""
        self.cancel_order_sync_called = True
        self.cancel_order_sync_count += 1
        self.cancelled_orders.append(broker_order_id)
        return self.should_succeed


class MockEventBus:
    """Mock implementation of event bus for testing"""
    
    def __init__(self):
        self.published_events: List[Any] = []
        self.publish_called = False
        self.publish_count = 0
    
    def publish(self, event: Any) -> None:
        """Publish event to bus"""
        self.publish_called = True
        self.publish_count += 1
        self.published_events.append(event)


class TestCancelOrderCommandHandler:
    """Test suite for CancelOrderCommandHandler"""
    
    def setup_method(self):
        """Setup test fixtures before each test"""
        self.order_repo = MockOrderRepository()
        self.broker_service = MockBrokerService()
        self.event_bus = MockEventBus()
        
        self.handler = CancelOrderCommandHandler(
            order_repo=self.order_repo,
            broker_service=self.broker_service,
            event_bus=self.event_bus
        )
        
        # Create a sample order for testing
        self.order_id = uuid4()
        # Use the factory method to create the order
        self.sample_order = Order.create(
            symbol="AAPL",
            quantity=100,
            order_type="MARKET",
            side="BUY",
            price=150.0
        )
        # Override some attributes for testing
        self.sample_order.id = self.order_id
        self.sample_order.broker_order_id = "BROKER123"
    
    def test_cancel_pending_order_success(self):
        """Test 1: Successfully cancel a pending order"""
        # Arrange
        self.order_repo.add_order(self.sample_order)
        command = CancelOrderCommand(
            order_id=self.order_id,
            reason="User requested cancellation",
            cancelled_by=uuid4()
        )
        
        # Act
        result = self.handler.handle(command)
        
        # Assert - Verify result
        assert result.success is True
        assert result.order_id == self.order_id
        assert "cancelled successfully" in result.message.lower()
        assert result.cancelled_at is not None
        
        # Assert - Verify repository interactions
        assert self.order_repo.get_called is True
        assert self.order_repo.get_count == 1
        assert self.order_repo.save_called is True
        assert self.order_repo.save_count == 1
        
        # Assert - Verify order state changed
        saved_order = self.order_repo.orders[self.order_id]
        assert saved_order.status == OrderStatus.CANCELLED
        assert saved_order.cancelled_at is not None
        assert saved_order.cancellation_reason == "User requested cancellation"
        
        # Assert - Verify broker was called
        assert self.broker_service.cancel_order_sync_called is True
        assert self.broker_service.cancel_order_sync_count == 1
        assert "BROKER123" in self.broker_service.cancelled_orders
        
        # Assert - Verify events were published
        assert self.event_bus.publish_called is True
        assert self.event_bus.publish_count >= 1
        assert any(isinstance(event, OrderCancelled) for event in self.event_bus.published_events)
        
        # Verify the OrderCancelled event details
        cancelled_event = next(
            event for event in self.event_bus.published_events 
            if isinstance(event, OrderCancelled)
        )
        assert cancelled_event.order_id == self.order_id
        assert cancelled_event.reason == "User requested cancellation"
    
    def test_cancel_filled_order_fails(self):
        """Test 2: Cannot cancel an already filled order"""
        # Arrange
        filled_order = Order.create(
            symbol="AAPL",
            quantity=100,
            order_type="MARKET",
            side="BUY",
            price=150.0
        )
        filled_order.id = self.order_id
        filled_order.status = OrderStatus.FILLED
        filled_order.filled_at = datetime.utcnow()
        filled_order.broker_order_id = "BROKER123"
        self.order_repo.add_order(filled_order)
        command = CancelOrderCommand(order_id=self.order_id)
        
        # Act & Assert
        with pytest.raises(CannotCancelFilledOrderError) as exc_info:
            self.handler.handle(command)
        
        assert "already filled" in str(exc_info.value).lower()
        
        # Verify order was retrieved but not saved
        assert self.order_repo.get_called is True
        assert self.order_repo.save_called is False
        
        # Verify broker was not called
        assert self.broker_service.cancel_order_sync_called is False
        
        # Verify no events were published
        assert self.event_bus.publish_called is False
    
    def test_cancel_already_cancelled_order_fails(self):
        """Test 3: Cannot cancel an already cancelled order"""
        # Arrange
        cancelled_order = Order.create(
            symbol="AAPL",
            quantity=100,
            order_type="MARKET",
            side="BUY",
            price=150.0
        )
        cancelled_order.id = self.order_id
        cancelled_order.status = OrderStatus.CANCELLED
        cancelled_order.cancelled_at = datetime.utcnow()
        cancelled_order.cancellation_reason = "Previous cancellation"
        cancelled_order.broker_order_id = "BROKER123"
        self.order_repo.add_order(cancelled_order)
        command = CancelOrderCommand(order_id=self.order_id)
        
        # Act & Assert
        with pytest.raises(OrderAlreadyCancelledError) as exc_info:
            self.handler.handle(command)
        
        assert "already cancelled" in str(exc_info.value).lower()
        
        # Verify order was retrieved but not saved
        assert self.order_repo.get_called is True
        assert self.order_repo.save_called is False
        
        # Verify broker was not called
        assert self.broker_service.cancel_order_sync_called is False
        
        # Verify no events were published
        assert self.event_bus.publish_called is False
    
    def test_cancel_nonexistent_order_fails(self):
        """Test 4: Cannot cancel a non-existent order"""
        # Arrange
        non_existent_id = uuid4()
        command = CancelOrderCommand(order_id=non_existent_id)
        
        # Act & Assert
        with pytest.raises(OrderNotFoundError) as exc_info:
            self.handler.handle(command)
        
        assert "not found" in str(exc_info.value).lower()
        assert str(non_existent_id) in str(exc_info.value)
        
        # Verify order was attempted to be retrieved
        assert self.order_repo.get_called is True
        assert self.order_repo.get_count == 1
        
        # Verify nothing else was called
        assert self.order_repo.save_called is False
        assert self.broker_service.cancel_order_sync_called is False
        assert self.event_bus.publish_called is False
    
    def test_broker_cancellation_failure_handling(self):
        """Test 5: Handle broker cancellation failure"""
        # Arrange
        self.order_repo.add_order(self.sample_order)
        # Configure broker to fail
        self.broker_service.should_succeed = False
        command = CancelOrderCommand(
            order_id=self.order_id,
            reason="User cancellation"
        )
        
        # Act & Assert
        with pytest.raises(BrokerCancellationError) as exc_info:
            self.handler.handle(command)
        
        assert "broker failed to cancel" in str(exc_info.value).lower()
        
        # Verify order was still saved with cancelled status (business decision)
        assert self.order_repo.save_called is True
        saved_order = self.order_repo.orders[self.order_id]
        assert saved_order.status == OrderStatus.CANCELLED
        assert saved_order.cancelled_at is not None
        
        # Verify broker was called
        assert self.broker_service.cancel_order_sync_called is True
        assert self.broker_service.cancel_order_sync_count == 1
        
        # Verify events were NOT published due to broker failure
        # (This is a design decision - could be different based on requirements)
        assert self.event_bus.publish_called is False
    
    def test_cancellation_event_published(self):
        """Test 6: Verify correct events are published on successful cancellation"""
        # Arrange
        self.order_repo.add_order(self.sample_order)
        cancelled_by_user = uuid4()
        command = CancelOrderCommand(
            order_id=self.order_id,
            reason="Test cancellation",
            cancelled_by=cancelled_by_user
        )
        
        # Act
        result = self.handler.handle(command)
        
        # Assert - Verify success
        assert result.success is True
        
        # Assert - Verify events published
        assert self.event_bus.publish_called is True
        assert len(self.event_bus.published_events) > 0
        
        # Find the OrderCancelled event
        cancelled_events = [
            event for event in self.event_bus.published_events
            if isinstance(event, OrderCancelled)
        ]
        assert len(cancelled_events) == 1
        
        # Verify event details
        event = cancelled_events[0]
        assert event.order_id == self.order_id
        assert event.reason == "Test cancellation"
        assert event.cancelled_by == cancelled_by_user
        assert event.cancelled_at is not None
        assert event.symbol == "AAPL"
        assert event.original_quantity == 100
        assert event.order_type == "MARKET"
        assert event.unfilled_quantity == 100
    
    def test_cancel_order_without_broker_id(self):
        """Test cancelling an order that has no broker_order_id"""
        # Arrange
        order_without_broker_id = Order.create(
            symbol="AAPL",
            quantity=100,
            order_type="MARKET",
            side="BUY",
            price=150.0
        )
        order_without_broker_id.id = self.order_id
        order_without_broker_id.broker_order_id = None  # No broker ID
        self.order_repo.add_order(order_without_broker_id)
        command = CancelOrderCommand(order_id=self.order_id)
        
        # Act
        result = self.handler.handle(command)
        
        # Assert - Should succeed without calling broker
        assert result.success is True
        assert self.order_repo.save_called is True
        assert self.broker_service.cancel_order_sync_called is False  # Broker not called
        assert self.event_bus.publish_called is True
        
        # Verify order is cancelled
        saved_order = self.order_repo.orders[self.order_id]
        assert saved_order.status == OrderStatus.CANCELLED
    
    def test_cancel_order_with_minimal_command(self):
        """Test cancellation with minimal command (no reason or cancelled_by)"""
        # Arrange
        self.order_repo.add_order(self.sample_order)
        command = CancelOrderCommand(order_id=self.order_id)  # Minimal command
        
        # Act
        result = self.handler.handle(command)
        
        # Assert
        assert result.success is True
        
        # Verify default values were used
        saved_order = self.order_repo.orders[self.order_id]
        assert saved_order.cancellation_reason == "No reason provided"
        
        # Check event has default values
        cancelled_event = next(
            event for event in self.event_bus.published_events
            if isinstance(event, OrderCancelled)
        )
        assert cancelled_event.reason == "No reason provided"
        assert cancelled_event.cancelled_by == UUID(int=0)  # Null UUID
    
    def test_broker_exception_wrapped_correctly(self):
        """Test that broker exceptions are properly wrapped"""
        # Arrange
        self.order_repo.add_order(self.sample_order)
        
        # Mock broker to raise an exception
        self.broker_service.cancel_order_sync = Mock(
            side_effect=RuntimeError("Network error")
        )
        command = CancelOrderCommand(order_id=self.order_id)
        
        # Act & Assert
        with pytest.raises(BrokerCancellationError) as exc_info:
            self.handler.handle(command)
        
        assert "Failed to cancel order with broker" in str(exc_info.value)
        assert "Network error" in str(exc_info.value)
    
    def test_multiple_events_from_aggregate(self):
        """Test handling multiple events from the aggregate"""
        # Arrange
        self.order_repo.add_order(self.sample_order)
        
        # Add an extra event to the order's event list
        extra_event = OrderPlaced(
            order_id=self.order_id,
            portfolio_id=uuid4(),
            symbol="AAPL",
            quantity=100,
            order_type="MARKET",
            price=150.0
        )
        self.sample_order._add_event(extra_event)
        
        command = CancelOrderCommand(order_id=self.order_id)
        
        # Act
        result = self.handler.handle(command)
        
        # Assert
        assert result.success is True
        assert self.event_bus.publish_count >= 2  # At least 2 events
        
        # Verify both events were published
        event_types = [type(event) for event in self.event_bus.published_events]
        assert OrderPlaced in event_types
        assert OrderCancelled in event_types