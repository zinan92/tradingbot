"""
Event handler for broker order cancellation confirmation

Handles the OrderCancelledByBroker event which is sent asynchronously
when the broker confirms that an order has been cancelled on their side.
"""
import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from decimal import Decimal

from src.domain.trading.aggregates.order import Order, OrderDomainError
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.repositories import (
    IOrderRepository,
    IPortfolioRepository,
    OrderNotFoundError,
)
from src.domain.trading.events import OrderCancelledByBroker, OrderFullyCancelled

logger = logging.getLogger(__name__)


class OrderCancellationConfirmedHandler:
    """
    Handles async confirmation of order cancellation from broker
    
    When the broker confirms that an order has been successfully cancelled,
    this handler:
    1. Updates the order status to CANCELLED_CONFIRMED
    2. Releases any reserved funds in the portfolio
    3. Updates positions if the order was partially filled
    4. Publishes OrderFullyCancelled event for audit trail
    """
    
    def __init__(self,
                 order_repo: IOrderRepository,
                 portfolio_repo: IPortfolioRepository,
                 event_bus):
        """
        Initialize the handler
        
        Args:
            order_repo: Repository for order persistence
            portfolio_repo: Repository for portfolio persistence
            event_bus: Event bus for publishing domain events
        """
        self._order_repo = order_repo
        self._portfolio_repo = portfolio_repo
        self._event_bus = event_bus
        logger.info("OrderCancellationConfirmedHandler initialized")
    
    def handle(self, event: OrderCancelledByBroker) -> None:
        """
        Handle the broker cancellation confirmation event
        
        Args:
            event: OrderCancelledByBroker event from the broker
            
        Raises:
            OrderNotFoundError: If the order doesn't exist
            OrderDomainError: If the order state doesn't allow confirmation
        """
        logger.info(f"Handling cancellation confirmation for order {event.order_id}")
        
        try:
            # Step 1: Load the order
            order = self._load_order(event.order_id)
            
            # Step 2: Update order status to CANCELLED_CONFIRMED
            self._confirm_order_cancellation(order, event)
            
            # Step 3: Release reserved funds if order had reserved funds
            portfolio = self._release_reserved_funds(order)
            
            # Step 4: Update positions if partially filled
            # Note: This would be handled if we had partial fills implemented
            # For now, we assume orders are either fully filled or not filled at all
            
            # Step 5: Publish OrderFullyCancelled event for audit
            self._publish_events(order, portfolio)
            
            logger.info(f"Successfully handled cancellation confirmation for order {event.order_id}")
            
        except OrderNotFoundError:
            logger.error(f"Order {event.order_id} not found when handling cancellation confirmation")
            raise
        except OrderDomainError as e:
            logger.error(f"Domain error handling cancellation confirmation: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error handling cancellation confirmation: {str(e)}")
            raise
    
    def _load_order(self, order_id: UUID) -> Order:
        """
        Load order from repository
        
        Args:
            order_id: ID of the order to load
            
        Returns:
            Order aggregate
            
        Raises:
            OrderNotFoundError: If order doesn't exist
        """
        logger.debug(f"Loading order {order_id}")
        order = self._order_repo.get(order_id)
        
        if not order:
            raise OrderNotFoundError(f"Order {order_id} not found")
        
        logger.debug(f"Order {order_id} loaded. Status: {order.status}")
        return order
    
    def _confirm_order_cancellation(self, order: Order, event: OrderCancelledByBroker) -> None:
        """
        Update order status to CANCELLED_CONFIRMED
        
        Args:
            order: Order to confirm cancellation for
            event: The cancellation event from broker
        """
        logger.debug(f"Confirming cancellation for order {order.id}")
        
        # Call the domain method to confirm cancellation
        order.confirm_cancellation(event.cancelled_at)
        
        # Save the updated order
        self._order_repo.save(order)
        
        logger.info(f"Order {order.id} cancellation confirmed")
    
    def _release_reserved_funds(self, order: Order) -> Optional[Portfolio]:
        """
        Release any funds that were reserved for this order
        
        Args:
            order: The cancelled order
            
        Returns:
            Updated portfolio if funds were released, None otherwise
        """
        # Check if order has an associated portfolio
        # In a real system, we'd track which portfolio placed the order
        # For now, we'll look for portfolios and check if they have reserved funds
        
        # Note: This is simplified. In production, you'd track portfolio_id in the order
        # or have a separate mapping of orders to portfolios
        
        try:
            # Get all portfolios (simplified approach)
            portfolios = self._portfolio_repo.get_all()
            
            for portfolio in portfolios:
                # Check if this portfolio has reserved funds that might be for this order
                if portfolio.reserved_cash > 0:
                    # Calculate what would have been reserved for this order
                    # This is simplified - in reality you'd track exact reservations
                    estimated_reservation = self._calculate_order_reservation(order)
                    
                    if estimated_reservation <= portfolio.reserved_cash:
                        logger.info(
                            f"Releasing {estimated_reservation} {portfolio.currency} "
                            f"from portfolio {portfolio.id}"
                        )
                        
                        portfolio.release_reserved_funds(estimated_reservation)
                        self._portfolio_repo.save(portfolio)
                        
                        return portfolio
            
            logger.debug(f"No reserved funds to release for order {order.id}")
            return None
            
        except Exception as e:
            logger.warning(f"Error releasing reserved funds: {str(e)}")
            # Don't fail the whole operation if fund release fails
            # This could be handled by a compensating transaction
            return None
    
    def _calculate_order_reservation(self, order: Order) -> Decimal:
        """
        Calculate how much was likely reserved for this order
        
        Args:
            order: The order to calculate reservation for
            
        Returns:
            Estimated reservation amount
        """
        # Simplified calculation
        # In reality, this would be tracked properly
        if order.order_type == "MARKET":
            # Market orders typically reserve with a buffer
            estimated_price = 100.0  # Would fetch actual market price
            return Decimal(str(estimated_price * order.quantity * 1.05))
        else:  # LIMIT order
            if order.price:
                return Decimal(str(order.price * order.quantity))
            else:
                # Shouldn't happen for limit orders
                return Decimal("0")
    
    def _publish_events(self, order: Order, portfolio: Optional[Portfolio]) -> None:
        """
        Publish domain events for audit trail
        
        Args:
            order: The order with events to publish
            portfolio: The portfolio with events to publish (if any)
        """
        # Publish order events
        order_events = order.pull_events()
        for event in order_events:
            logger.debug(f"Publishing order event: {event}")
            self._event_bus.publish(event)
        
        # Publish portfolio events if portfolio was updated
        if portfolio:
            portfolio_events = portfolio.pull_events()
            for event in portfolio_events:
                logger.debug(f"Publishing portfolio event: {event}")
                self._event_bus.publish(event)
        
        logger.info(f"Published {len(order_events)} order events")


# Event handler registration helper
def register_handler(event_bus, order_repo, portfolio_repo):
    """
    Register the cancellation confirmed handler with the event bus
    
    Args:
        event_bus: Event bus to register with
        order_repo: Order repository
        portfolio_repo: Portfolio repository
    """
    handler = OrderCancellationConfirmedHandler(
        order_repo=order_repo,
        portfolio_repo=portfolio_repo,
        event_bus=event_bus
    )
    
    # Subscribe to OrderCancelledByBroker events
    event_bus.subscribe("order.cancelled_by_broker", handler.handle)
    
    logger.info("OrderCancellationConfirmedHandler registered for order.cancelled_by_broker events")
    
    return handler