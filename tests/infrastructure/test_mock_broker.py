import pytest
import asyncio
from uuid import uuid4
from src.infrastructure.brokers.mock_broker import MockBrokerService, BrokerOrderStatus
from src.domain.trading.aggregates.order import Order


class TestMockBrokerService:
    """Tests for MockBrokerService with realistic behaviors"""
    
    @pytest.mark.asyncio
    async def test_successful_order_submission(self):
        """Test successful order submission"""
        # Arrange
        broker = MockBrokerService(simulate_delay=False)
        order = Order.create("AAPL", 100, "MARKET")
        
        # Act
        broker_id = await broker.submit_order(order)
        
        # Assert
        assert broker_id is not None
        assert broker_id.startswith("BROKER-")
        assert broker.get_order_status(broker_id) == "pending"
    
    @pytest.mark.asyncio
    async def test_successful_cancellation(self):
        """Test successful order cancellation"""
        # Arrange
        broker = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=1.0  # Always succeed
        )
        order = Order.create("AAPL", 100, "MARKET")
        broker_id = await broker.submit_order(order)
        
        # Act
        result = await broker.cancel_order(broker_id)
        
        # Assert
        assert result is True
        assert broker.get_order_status(broker_id) == "cancelled"
        assert broker.is_order_cancelled(broker_id) is True
    
    @pytest.mark.asyncio
    async def test_failed_cancellation(self):
        """Test failed order cancellation"""
        # Arrange
        broker = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=0.0  # Always fail
        )
        order = Order.create("AAPL", 100, "MARKET")
        broker_id = await broker.submit_order(order)
        
        # Act
        result = await broker.cancel_order(broker_id)
        
        # Assert
        assert result is False
        assert broker.get_order_status(broker_id) == "pending"  # Still pending
        assert broker.is_order_cancelled(broker_id) is False
    
    @pytest.mark.asyncio
    async def test_cannot_cancel_nonexistent_order(self):
        """Test cancelling a non-existent order"""
        # Arrange
        broker = MockBrokerService(simulate_delay=False)
        
        # Act
        result = await broker.cancel_order("FAKE-ORDER-ID")
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cannot_cancel_filled_order(self):
        """Test that filled orders cannot be cancelled"""
        # Arrange
        broker = MockBrokerService(simulate_delay=False)
        order = Order.create("AAPL", 100, "MARKET")
        broker_id = await broker.submit_order(order)
        
        # Manually mark as filled (simulating broker fill)
        broker._order_status[broker_id] = BrokerOrderStatus.FILLED
        
        # Act
        result = await broker.cancel_order(broker_id)
        
        # Assert
        assert result is False
        assert broker.get_order_status(broker_id) == "filled"
    
    @pytest.mark.asyncio
    async def test_idempotent_cancellation(self):
        """Test that cancelling already cancelled order returns True"""
        # Arrange
        broker = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=1.0
        )
        order = Order.create("AAPL", 100, "MARKET")
        broker_id = await broker.submit_order(order)
        
        # First cancellation
        await broker.cancel_order(broker_id)
        
        # Act - Second cancellation
        result = await broker.cancel_order(broker_id)
        
        # Assert - Should return True (already cancelled)
        assert result is True
        assert broker.get_order_status(broker_id) == "cancelled"
    
    @pytest.mark.asyncio
    async def test_random_cancellation_success_rate(self):
        """Test that cancellation success rate works as expected"""
        # Arrange
        broker = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=0.5  # 50% success rate
        )
        
        success_count = 0
        total_attempts = 100
        
        # Act - Submit and try to cancel many orders
        for _ in range(total_attempts):
            order = Order.create("AAPL", 100, "MARKET")
            broker_id = await broker.submit_order(order)
            
            if await broker.cancel_order(broker_id):
                success_count += 1
        
        # Assert - Should be roughly 50% success rate (with some tolerance)
        success_rate = success_count / total_attempts
        assert 0.35 < success_rate < 0.65  # Allow 15% deviation
    
    def test_sync_order_submission(self):
        """Test synchronous order submission"""
        # Arrange
        broker = MockBrokerService(simulate_delay=False)
        order = Order.create("AAPL", 100, "MARKET")
        
        # Act
        broker_id = broker.submit_order_sync(order)
        
        # Assert
        assert broker_id is not None
        assert broker_id.startswith("BROKER-")
        assert broker.get_order_status(broker_id) == "pending"
    
    def test_sync_cancellation(self):
        """Test synchronous order cancellation"""
        # Arrange
        broker = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=1.0
        )
        order = Order.create("AAPL", 100, "MARKET")
        broker_id = broker.submit_order_sync(order)
        
        # Act
        result = broker.cancel_order_sync(broker_id)
        
        # Assert
        assert result is True
        assert broker.get_order_status(broker_id) == "cancelled"
    
    def test_broker_state_tracking(self):
        """Test that broker properly tracks order state"""
        # Arrange
        broker = MockBrokerService(simulate_delay=False)
        order1 = Order.create("AAPL", 100, "MARKET")
        order2 = Order.create("MSFT", 50, "LIMIT", 200.0)
        
        # Act
        broker_id1 = broker.submit_order_sync(order1)
        broker_id2 = broker.submit_order_sync(order2)
        
        # Assert
        assert broker.get_submitted_orders_count() == 2
        assert broker.get_order_status(broker_id1) == "pending"
        assert broker.get_order_status(broker_id2) == "pending"
        
        # Cancel one order
        broker.cancel_order_sync(broker_id1)
        
        assert broker.get_order_status(broker_id1) == "cancelled"
        assert broker.get_order_status(broker_id2) == "pending"
        assert broker.is_order_cancelled(broker_id1) is True
        assert broker.is_order_cancelled(broker_id2) is False
    
    def test_broker_reset(self):
        """Test broker state reset"""
        # Arrange
        broker = MockBrokerService(simulate_delay=False)
        order = Order.create("AAPL", 100, "MARKET")
        broker_id = broker.submit_order_sync(order)
        
        # Act
        broker.reset()
        
        # Assert
        assert broker.get_submitted_orders_count() == 0
        assert broker.get_order_status(broker_id) is None
        assert broker.is_order_cancelled(broker_id) is False
    
    @pytest.mark.asyncio
    async def test_cancellation_with_delay(self):
        """Test cancellation with simulated delay"""
        # Arrange
        broker = MockBrokerService(
            simulate_delay=True,  # Enable delay
            cancellation_success_rate=1.0
        )
        order = Order.create("AAPL", 100, "MARKET")
        
        # Act
        broker_id = await broker.submit_order(order)
        
        # Cancel order (should have delay)
        start_time = asyncio.get_event_loop().time()
        result = await broker.cancel_order(broker_id)
        end_time = asyncio.get_event_loop().time()
        
        # Assert
        assert result is True
        # Should have some delay (100-500ms)
        elapsed = end_time - start_time
        assert elapsed > 0.05  # At least 50ms (allowing for some variance)