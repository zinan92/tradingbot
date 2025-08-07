from typing import Optional, Dict, Set
from enum import Enum
import uuid
import asyncio
import random
import logging
from datetime import datetime
from src.domain.trading.aggregates.order import Order
from src.domain.trading.repositories.broker_interface import IBroker, BrokerOrderId

logger = logging.getLogger(__name__)


class BrokerOrderStatus(Enum):
    """Internal broker order status"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    CANCELLING = "cancelling"  # Cancellation in progress


class MockBrokerService(IBroker):
    """
    Mock broker service for testing
    
    Simulates broker interactions without real API calls.
    Implements the IBroker interface with async methods.
    Maintains internal order state and simulates realistic behaviors.
    """
    
    def __init__(self, 
                 simulate_delay: bool = True,
                 cancellation_success_rate: float = 0.9,
                 event_bus=None):
        """
        Initialize mock broker service
        
        Args:
            simulate_delay: If True, add artificial delays to simulate network latency
            cancellation_success_rate: Probability of successful cancellation (0.0-1.0)
            event_bus: Optional event bus for sending async notifications
        """
        self._submitted_orders: Dict[str, Order] = {}
        self._order_status: Dict[str, BrokerOrderStatus] = {}
        self._cancelled_orders: Set[str] = set()
        self._simulate_delay = simulate_delay
        self._cancellation_success_rate = cancellation_success_rate
        self._event_bus = event_bus
        # Add public 'orders' dict for integration tests to access order data
        self.orders: Dict[str, Dict] = {}
        # Add flag for test control of cancellation failures
        self.fail_next_cancel = False
        logger.info(f"MockBrokerService initialized with {cancellation_success_rate:.0%} cancellation success rate")
    
    async def submit_order(self, order: Order) -> BrokerOrderId:
        """
        Submit an order to the broker
        
        Args:
            order: The order to submit
            
        Returns:
            BrokerOrderId: The broker's order identifier
        """
        # Simulate network delay if configured
        if self._simulate_delay:
            delay = random.uniform(0.05, 0.2)  # 50-200ms
            await asyncio.sleep(delay)
        
        # Generate a mock broker order ID
        broker_order_id = BrokerOrderId(f"BROKER-{uuid.uuid4().hex[:8].upper()}")
        
        # Store order and its status
        self._submitted_orders[broker_order_id] = order
        self._order_status[broker_order_id] = BrokerOrderStatus.PENDING
        
        logger.info(f"Order {order.id} submitted to broker as {broker_order_id}")
        
        # Simulate random order fills after some time (for testing)
        if self._simulate_delay:
            asyncio.create_task(self._simulate_order_fill(broker_order_id))
        
        return broker_order_id
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order with broker.
        Returns True if cancellation request accepted.
        Note: This doesn't mean order is cancelled, just that request was received.
        
        Args:
            order_id: The broker's order identifier
            
        Returns:
            bool: True if cancellation request was accepted, False otherwise
        """
        logger.info(f"Received cancellation request for order {order_id}")
        
        # Check if order exists
        if order_id not in self._submitted_orders:
            logger.warning(f"Order {order_id} not found in broker")
            return False
        
        # Check current status
        current_status = self._order_status.get(order_id)
        
        # Cannot cancel if already filled or cancelled
        if current_status == BrokerOrderStatus.FILLED:
            logger.warning(f"Cannot cancel order {order_id} - already filled")
            return False
        
        if current_status == BrokerOrderStatus.CANCELLED:
            logger.warning(f"Order {order_id} already cancelled")
            return True  # Still return True as it's already cancelled
        
        if current_status == BrokerOrderStatus.CANCELLING:
            logger.info(f"Order {order_id} cancellation already in progress")
            return True
        
        # Simulate network delay for cancellation request
        if self._simulate_delay:
            delay = random.uniform(0.1, 0.5)  # 100-500ms
            await asyncio.sleep(delay)
        
        # Determine if cancellation will succeed based on success rate
        will_succeed = random.random() < self._cancellation_success_rate
        
        if will_succeed:
            # Mark as cancelling (async process)
            self._order_status[order_id] = BrokerOrderStatus.CANCELLING
            logger.info(f"Cancellation request for order {order_id} accepted")
            
            # Schedule async cancellation completion
            if self._simulate_delay:
                asyncio.create_task(self._complete_cancellation(order_id))
            else:
                # Immediate cancellation for tests without delay
                self._order_status[order_id] = BrokerOrderStatus.CANCELLED
                self._cancelled_orders.add(order_id)
            
            return True
        else:
            # Simulate cancellation rejection
            logger.warning(f"Broker rejected cancellation request for order {order_id}")
            return False
    
    async def _complete_cancellation(self, order_id: str):
        """
        Complete the cancellation process asynchronously
        
        Args:
            order_id: The broker's order identifier
        """
        # Simulate processing time
        await asyncio.sleep(random.uniform(0.5, 2.0))  # 0.5-2 seconds
        
        # Check if still in cancelling state (might have been filled in the meantime)
        if self._order_status.get(order_id) == BrokerOrderStatus.CANCELLING:
            self._order_status[order_id] = BrokerOrderStatus.CANCELLED
            self._cancelled_orders.add(order_id)
            logger.info(f"Order {order_id} cancellation completed by broker")
            
            # Send async notification via event if event bus is available
            if self._event_bus and order_id in self._submitted_orders:
                order = self._submitted_orders[order_id]
                await self._send_cancellation_notification(order_id, order)
    
    async def _send_cancellation_notification(self, broker_order_id: str, order: Order):
        """
        Send async notification that broker has cancelled the order
        
        Args:
            broker_order_id: The broker's order identifier
            order: The original order
        """
        try:
            # Import the OrderCancelledByBroker event
            from src.domain.trading.events import OrderCancelledByBroker
            
            event = OrderCancelledByBroker(
                order_id=order.id,
                broker_order_id=broker_order_id,
                cancelled_at=datetime.utcnow()
            )
            
            # Publish event asynchronously
            if hasattr(self._event_bus, 'publish_async'):
                await self._event_bus.publish_async(event)
            else:
                self._event_bus.publish(event)
            
            logger.info(f"Sent OrderCancelledByBroker notification for {broker_order_id}")
            
        except Exception as e:
            logger.error(f"Failed to send cancellation notification: {str(e)}")
    
    async def _simulate_order_fill(self, order_id: str):
        """
        Simulate random order fills for testing
        
        Args:
            order_id: The broker's order identifier
        """
        # Wait random time before potentially filling
        await asyncio.sleep(random.uniform(5, 15))  # 5-15 seconds
        
        # Only fill if still pending (not cancelled)
        if self._order_status.get(order_id) == BrokerOrderStatus.PENDING:
            # 30% chance of fill
            if random.random() < 0.3:
                self._order_status[order_id] = BrokerOrderStatus.FILLED
                logger.info(f"Order {order_id} filled by broker simulation")
    
    # Synchronous versions for backward compatibility
    def submit_order_sync(self, order: Order) -> str:
        """
        Synchronous version of submit_order for backward compatibility
        
        Returns:
            str: The broker's order identifier
        """
        # Generate a mock broker order ID
        broker_order_id = f"BROKER-{uuid.uuid4().hex[:8].upper()}"
        
        # Store order and its status
        self._submitted_orders[broker_order_id] = order
        self._order_status[broker_order_id] = BrokerOrderStatus.PENDING
        
        # Store in public orders dict for test access
        self.orders[broker_order_id] = {
            "order_id": str(order.id),
            "status": "pending",
            "symbol": order.symbol,
            "quantity": order.quantity,
            "order_type": order.order_type,
            "price": order.price
        }
        
        logger.info(f"Order {order.id} submitted to broker as {broker_order_id} (sync)")
        
        return broker_order_id
    
    def cancel_order_sync(self, broker_order_id: str) -> bool:
        """
        Synchronous version of cancel_order for backward compatibility
        
        Returns:
            True if cancellation successful, False otherwise
        """
        logger.info(f"Received sync cancellation request for order {broker_order_id}")
        
        if broker_order_id not in self._submitted_orders:
            logger.warning(f"Order {broker_order_id} not found in broker")
            return False
        
        # Check current status
        current_status = self._order_status.get(broker_order_id)
        
        # Cannot cancel if already filled
        if current_status == BrokerOrderStatus.FILLED:
            logger.warning(f"Cannot cancel order {broker_order_id} - already filled")
            return False
        
        # Check if test wants us to fail
        if self.fail_next_cancel:
            self.fail_next_cancel = False  # Reset flag
            logger.warning(f"Test flag set to fail cancellation for order {broker_order_id}")
            return False
        
        # Determine if cancellation will succeed based on success rate
        will_succeed = random.random() < self._cancellation_success_rate
        
        if will_succeed:
            self._order_status[broker_order_id] = BrokerOrderStatus.CANCELLED
            self._cancelled_orders.add(broker_order_id)
            # Update public orders dict
            if broker_order_id in self.orders:
                self.orders[broker_order_id]["status"] = "cancelled"
            logger.info(f"Order {broker_order_id} cancelled successfully (sync)")
            return True
        else:
            logger.warning(f"Broker rejected sync cancellation for order {broker_order_id}")
            return False
    
    def get_order_status(self, broker_order_id: str) -> Optional[str]:
        """Get order status from broker"""
        status = self._order_status.get(broker_order_id)
        return status.value if status else None
    
    def is_order_cancelled(self, broker_order_id: str) -> bool:
        """Check if an order has been cancelled"""
        return broker_order_id in self._cancelled_orders
    
    def get_submitted_orders_count(self) -> int:
        """Get count of submitted orders (for testing)"""
        return len(self._submitted_orders)
    
    def reset(self):
        """Reset broker state (for testing)"""
        self._submitted_orders.clear()
        self._order_status.clear()
        self._cancelled_orders.clear()
        logger.info("MockBrokerService state reset")
    
    def fill_order(self, broker_order_id: str, fill_price: Optional[float] = None) -> bool:
        """
        Manually trigger an order fill (for testing and simulation)
        
        This simulates the broker executing an order at market.
        
        Args:
            broker_order_id: The broker's order identifier
            fill_price: Optional fill price. If not provided, uses order price or a random price
            
        Returns:
            bool: True if order was filled, False otherwise
        """
        logger.info(f"Fill request received for order {broker_order_id}")
        
        # Check if order exists
        if broker_order_id not in self._submitted_orders:
            logger.warning(f"Order {broker_order_id} not found")
            return False
        
        # Check current status
        current_status = self._order_status.get(broker_order_id)
        
        # Can only fill pending orders
        if current_status != BrokerOrderStatus.PENDING:
            logger.warning(f"Cannot fill order {broker_order_id} with status {current_status}")
            return False
        
        # Get the order
        order = self._submitted_orders[broker_order_id]
        
        # Determine fill price
        if fill_price is None:
            if order.price:
                fill_price = order.price
            else:
                # Simulate market price (random for demo)
                fill_price = random.uniform(90, 110)
        
        # Update status
        self._order_status[broker_order_id] = BrokerOrderStatus.FILLED
        
        # Update public orders dict
        if broker_order_id in self.orders:
            self.orders[broker_order_id]["status"] = "filled"
            self.orders[broker_order_id]["fill_price"] = fill_price
        
        # Publish OrderFilled event
        if self._event_bus:
            from decimal import Decimal
            from src.domain.trading.events import OrderFilled
            
            event = OrderFilled(
                order_id=order.id,
                symbol=order.symbol,
                quantity=order.quantity,
                fill_price=Decimal(str(fill_price)),
                broker_order_id=broker_order_id
            )
            
            self._event_bus.publish(event)
            logger.info(
                f"Order {broker_order_id} filled: "
                f"{order.quantity} shares of {order.symbol} @ ${fill_price}"
            )
        
        return True
    
    async def fill_order_async(self, broker_order_id: str, fill_price: Optional[float] = None) -> bool:
        """
        Async version of fill_order for testing
        
        Args:
            broker_order_id: The broker's order identifier
            fill_price: Optional fill price
            
        Returns:
            bool: True if order was filled, False otherwise
        """
        # Add a small delay to simulate network
        if self._simulate_delay:
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        return self.fill_order(broker_order_id, fill_price)