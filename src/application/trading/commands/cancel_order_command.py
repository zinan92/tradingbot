import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.domain.trading.aggregates.order import Order, CannotCancelFilledOrderError
from src.domain.trading.repositories import IOrderRepository, OrderNotFoundError
from src.domain.trading.events import OrderCancelled

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class CancelOrderCommand:
    """Command to cancel an existing order"""
    order_id: UUID
    reason: Optional[str] = None
    cancelled_by: Optional[UUID] = None  # User ID who is cancelling


@dataclass
class CancelOrderResult:
    """Result of cancel order operation"""
    success: bool
    order_id: UUID
    message: str
    cancelled_at: Optional[str] = None


class CancelOrderCommandHandler:
    """
    Handler for cancelling orders
    
    Orchestrates the order cancellation flow:
    1. Load order from repository
    2. Apply cancellation business rules (via aggregate)
    3. Notify broker
    4. Publish domain events
    """
    
    def __init__(self,
                 order_repo: IOrderRepository,
                 broker_service,  # MockBrokerService or IBrokerService
                 event_bus):      # InMemoryEventBus or IEventBus
        self._order_repo = order_repo
        self._broker_service = broker_service
        self._event_bus = event_bus
        logger.info("CancelOrderCommandHandler initialized")
    
    def handle(self, command: CancelOrderCommand) -> CancelOrderResult:
        """
        Execute the cancel order use case
        
        Args:
            command: The cancel order command containing order_id and reason
            
        Returns:
            CancelOrderResult with success status and details
            
        Raises:
            OrderNotFoundError: If order doesn't exist
            CannotCancelFilledOrderError: If order is already filled
            BrokerCancellationError: If broker fails to cancel
        """
        logger.info(f"Processing cancel order command for order {command.order_id}")
        
        # Step 1: Load order from repository
        logger.debug(f"Loading order {command.order_id} from repository")
        order = self._order_repo.get(command.order_id)
        
        if not order:
            logger.error(f"Order {command.order_id} not found")
            raise OrderNotFoundError(f"Order {command.order_id} not found")
        
        logger.info(f"Order {command.order_id} loaded successfully. Status: {order.status}")
        
        # Step 2: Apply cancellation through aggregate (enforces business rules)
        try:
            logger.debug(f"Attempting to cancel order {command.order_id}")
            cancelled_event = order.cancel(
                reason=command.reason,
                cancelled_by=command.cancelled_by
            )  # Returns OrderCancelled event
            logger.info(f"Order {command.order_id} cancelled successfully in domain")
        except CannotCancelFilledOrderError as e:
            logger.warning(f"Cannot cancel order {command.order_id}: {str(e)}")
            raise  # Re-raise domain exception
        except Exception as e:
            logger.error(f"Unexpected error cancelling order {command.order_id}: {str(e)}")
            raise
        
        # Step 3: Save the updated order
        logger.debug(f"Saving cancelled order {command.order_id} to repository")
        self._order_repo.save(order)
        logger.info(f"Cancelled order {command.order_id} saved to repository")
        
        # Step 4: Notify broker about cancellation
        if order.broker_order_id:
            try:
                logger.debug(f"Notifying broker to cancel order {order.broker_order_id}")
                broker_success = self._broker_service.cancel_order_sync(order.broker_order_id)
                
                if not broker_success:
                    logger.error(f"Broker failed to cancel order {order.broker_order_id}")
                    # Note: We don't rollback the domain cancellation here
                    # The order is cancelled in our system even if broker fails
                    # This is a business decision - could be different based on requirements
                    raise BrokerCancellationError(
                        f"Broker failed to cancel order {order.broker_order_id}"
                    )
                
                logger.info(f"Broker successfully cancelled order {order.broker_order_id}")
            except Exception as e:
                logger.error(f"Error communicating with broker: {str(e)}")
                # Wrap any broker errors
                if not isinstance(e, BrokerCancellationError):
                    raise BrokerCancellationError(
                        f"Failed to cancel order with broker: {str(e)}"
                    )
                raise
        else:
            logger.warning(f"Order {command.order_id} has no broker_order_id, skipping broker notification")
        
        # Step 5: Publish domain events
        logger.debug(f"Publishing domain events for cancelled order {command.order_id}")
        domain_events = order.pull_events()
        
        for event in domain_events:
            logger.debug(f"Publishing event: {event}")
            self._event_bus.publish(event)
        
        logger.debug(f"Published {len(domain_events)} domain events for order {command.order_id}")
        
        logger.info(f"Successfully completed cancel order flow for {command.order_id}")
        
        # Step 6: Return result
        return CancelOrderResult(
            success=True,
            order_id=command.order_id,
            message=f"Order {command.order_id} cancelled successfully",
            cancelled_at=order.cancelled_at.isoformat() if order.cancelled_at else None
        )


# Custom Exceptions
class BrokerCancellationError(Exception):
    """Raised when broker fails to cancel an order"""
    pass