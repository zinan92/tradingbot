import pytest
from uuid import uuid4
from decimal import Decimal

from src.application.trading.commands.cancel_order_command import (
    CancelOrderCommand,
    CancelOrderCommandHandler,
    CancelOrderResult,
    BrokerCancellationError,
)
from src.domain.trading.aggregates.order import (
    Order,
    OrderStatus,
    CannotCancelFilledOrderError,
)
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.repositories import OrderNotFoundError
from src.infrastructure.persistence.in_memory import (
    InMemoryOrderRepository,
    InMemoryPortfolioRepository,
)
from src.infrastructure.brokers.mock_broker import MockBrokerService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus


class TestCancelOrderCommandHandler:
    """Tests for CancelOrderCommandHandler"""
    
    def setup_method(self):
        """Set up test dependencies"""
        self.order_repo = InMemoryOrderRepository()
        # Use 100% success rate for deterministic tests
        self.broker_service = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=1.0  # Always succeed for tests
        )
        self.event_bus = InMemoryEventBus()
        
        self.handler = CancelOrderCommandHandler(
            order_repo=self.order_repo,
            broker_service=self.broker_service,
            event_bus=self.event_bus
        )
        
        # Create a test order
        self.test_order = Order.create(
            symbol="AAPL",
            quantity=100,
            order_type="MARKET"
        )
        self.test_order.set_broker_order_id("BROKER-123")
        self.order_repo.save(self.test_order)
    
    def test_successful_order_cancellation(self):
        """Test successfully cancelling a pending order"""
        # Arrange
        command = CancelOrderCommand(
            order_id=self.test_order.id,
            reason="User requested cancellation"
        )
        
        # Submit order to broker first (this sets up the broker's internal state)
        broker_id = self.broker_service.submit_order_sync(self.test_order)
        # Make sure the test order has the same broker ID
        self.test_order.set_broker_order_id(broker_id)
        self.order_repo.save(self.test_order)
        
        # Act
        result = self.handler.handle(command)
        
        # Assert - Result is successful
        assert result.success is True
        assert result.order_id == self.test_order.id
        assert "cancelled successfully" in result.message
        assert result.cancelled_at is not None
        
        # Assert - Order is cancelled in repository
        cancelled_order = self.order_repo.get(self.test_order.id)
        assert cancelled_order.status == OrderStatus.CANCELLED
        assert cancelled_order.cancelled_at is not None
        
        # Assert - Events were published
        events = self.event_bus.get_published_events()
        assert len(events) > 0
        # Check for OrderCancelled event (either string or actual event)
        assert any("OrderCancelled" in str(e) or 
                  (hasattr(e, 'event_name') and e.event_name == 'order.cancelled') 
                  for e in events)
    
    def test_order_not_found(self):
        """Test cancelling a non-existent order"""
        # Arrange
        non_existent_id = uuid4()
        command = CancelOrderCommand(
            order_id=non_existent_id,
            reason="Test cancellation"
        )
        
        # Act & Assert
        with pytest.raises(OrderNotFoundError) as exc:
            self.handler.handle(command)
        assert str(non_existent_id) in str(exc.value)
        assert "not found" in str(exc.value)
    
    def test_cannot_cancel_filled_order(self):
        """Test that filled orders cannot be cancelled"""
        # Arrange
        # Fill the order first
        self.test_order.fill()
        self.order_repo.save(self.test_order)
        
        command = CancelOrderCommand(
            order_id=self.test_order.id,
            reason="Trying to cancel filled order"
        )
        
        # Act & Assert
        with pytest.raises(CannotCancelFilledOrderError) as exc:
            self.handler.handle(command)
        assert "already filled" in str(exc.value)
        
        # Assert - Order remains filled
        order = self.order_repo.get(self.test_order.id)
        assert order.status == OrderStatus.FILLED
    
    def test_cancel_without_reason(self):
        """Test cancelling an order without providing a reason"""
        # Arrange
        command = CancelOrderCommand(
            order_id=self.test_order.id
            # No reason provided
        )
        
        # Submit order to broker and update order
        broker_id = self.broker_service.submit_order_sync(self.test_order)
        self.test_order.set_broker_order_id(broker_id)
        self.order_repo.save(self.test_order)
        
        # Act
        result = self.handler.handle(command)
        
        # Assert
        assert result.success is True
        assert result.order_id == self.test_order.id
    
    def test_cancel_order_without_broker_id(self):
        """Test cancelling an order that has no broker_order_id"""
        # Arrange
        # Create order without broker ID
        order_without_broker = Order.create(
            symbol="MSFT",
            quantity=50,
            order_type="LIMIT",
            price=300.00
        )
        # Don't set broker_order_id
        self.order_repo.save(order_without_broker)
        
        command = CancelOrderCommand(
            order_id=order_without_broker.id,
            reason="Cancel before broker submission"
        )
        
        # Act
        result = self.handler.handle(command)
        
        # Assert - Should succeed even without broker notification
        assert result.success is True
        assert result.order_id == order_without_broker.id
        
        # Order should be cancelled
        cancelled_order = self.order_repo.get(order_without_broker.id)
        assert cancelled_order.status == OrderStatus.CANCELLED
    
    def test_broker_cancellation_failure(self):
        """Test handling broker cancellation failure"""
        # Arrange
        command = CancelOrderCommand(
            order_id=self.test_order.id,
            reason="Test broker failure"
        )
        
        # Mock broker failure by not submitting the order first
        # (broker will return False for unknown orders)
        
        # Act & Assert
        with pytest.raises(BrokerCancellationError) as exc:
            self.handler.handle(command)
        assert "Broker failed" in str(exc.value)
        
        # Note: Order should still be cancelled in our system
        # This is a business decision - the order is cancelled locally
        # even if broker fails
        order = self.order_repo.get(self.test_order.id)
        assert order.status == OrderStatus.CANCELLED
    
    def test_idempotent_cancellation_attempt(self):
        """Test that trying to cancel an already cancelled order is handled gracefully"""
        # Arrange
        # First cancellation
        command = CancelOrderCommand(
            order_id=self.test_order.id,
            reason="First cancellation"
        )
        broker_id = self.broker_service.submit_order_sync(self.test_order)
        self.test_order.set_broker_order_id(broker_id)
        self.order_repo.save(self.test_order)
        self.handler.handle(command)
        
        # Second cancellation attempt
        command2 = CancelOrderCommand(
            order_id=self.test_order.id,
            reason="Second cancellation attempt"
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc:
            self.handler.handle(command2)
        assert "already cancelled" in str(exc.value)
    
    def test_events_published_on_cancellation(self):
        """Test that proper events are published when order is cancelled"""
        # Arrange
        command = CancelOrderCommand(
            order_id=self.test_order.id,
            reason="Testing event publication"
        )
        broker_id = self.broker_service.submit_order_sync(self.test_order)
        self.test_order.set_broker_order_id(broker_id)
        self.order_repo.save(self.test_order)
        
        # Subscribe to events
        received_events = []
        self.event_bus.subscribe("order.cancelled", lambda e: received_events.append(e))
        
        # Act
        result = self.handler.handle(command)
        
        # Assert
        assert result.success is True
        
        # Check all published events
        all_events = self.event_bus.get_published_events()
        assert len(all_events) > 0
        
        # Should have OrderCancelled event
        cancelled_events = [e for e in all_events 
                          if "OrderCancelled" in str(e) or 
                          (hasattr(e, 'event_name') and e.event_name == 'order.cancelled')]
        assert len(cancelled_events) > 0