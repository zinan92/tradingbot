"""
Order Filled Event Handler

Handles the OrderFilled domain event by updating portfolio positions
and releasing reserved funds.
"""
from decimal import Decimal
from typing import Optional
import logging

from src.domain.trading.events import OrderFilled
from src.domain.trading.repositories import (
    IOrderRepository,
    IPortfolioRepository,
    OrderNotFoundError
)

logger = logging.getLogger(__name__)


class OrderFilledEventHandler:
    """
    Handles OrderFilled events from the broker
    
    Responsibilities:
    1. Load the order and portfolio
    2. Update portfolio position
    3. Convert reserved funds to spent funds
    4. Save updated portfolio
    """
    
    def __init__(self,
                 order_repo: IOrderRepository,
                 portfolio_repo: IPortfolioRepository):
        self._order_repo = order_repo
        self._portfolio_repo = portfolio_repo
    
    def handle(self, event: OrderFilled) -> None:
        """
        Handle order filled event
        
        Args:
            event: OrderFilled domain event
            
        Raises:
            OrderNotFoundError: If order doesn't exist
            PortfolioNotFoundError: If portfolio doesn't exist
        """
        logger.info(f"Handling OrderFilled event for order {event.order_id}")
        
        try:
            # Load the order
            order = self._order_repo.get(event.order_id)
            if not order:
                raise OrderNotFoundError(f"Order {event.order_id} not found")
            
            # Update order status to filled first (regardless of portfolio)
            order.fill(fill_price=float(event.fill_price))
            self._order_repo.save(order)
            
            # Find the portfolio that owns this order
            # In a real system, we'd track portfolio_id in the order or event
            # For now, we'll search for it
            portfolio = self._find_portfolio_for_order(order)
            if not portfolio:
                logger.error(f"No portfolio found for order {event.order_id}")
                # Order is still marked as filled, but portfolio not updated
                return
            
            # Calculate actual cost of the filled order
            total_cost = event.fill_price * Decimal(str(event.quantity))
            
            # Update portfolio:
            # 1. Add the position
            portfolio.add_position(event.symbol, event.quantity)
            
            # 2. Convert reserved funds to spent funds
            # The portfolio reserved funds when placing the order
            # Now we need to adjust for the actual fill price
            portfolio.complete_order_fill(
                symbol=event.symbol,
                quantity=event.quantity,
                fill_price=event.fill_price,
                order_id=event.order_id
            )
            
            # Save portfolio
            self._portfolio_repo.save(portfolio)
            
            logger.info(
                f"Order {event.order_id} filled: "
                f"{event.quantity} shares of {event.symbol} @ ${event.fill_price}"
            )
            logger.info(
                f"Portfolio {portfolio.id} updated: "
                f"Position {event.symbol}={portfolio.get_position(event.symbol)}, "
                f"Available cash=${portfolio.available_cash}"
            )
            
        except Exception as e:
            logger.error(f"Error handling OrderFilled event: {str(e)}")
            raise
    
    def _find_portfolio_for_order(self, order):
        """
        Find the portfolio that placed this order
        
        In a real implementation, we'd have a better way to track this
        For now, we'll check all portfolios
        """
        # This is a simplified approach - in production we'd track this better
        portfolios = self._portfolio_repo.get_all()
        for portfolio in portfolios:
            # Check if this portfolio has reserved funds that could match this order
            # This is a heuristic - better tracking needed in production
            if portfolio.reserved_cash > 0:
                return portfolio
        return None