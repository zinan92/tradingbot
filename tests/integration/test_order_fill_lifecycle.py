"""
Integration test for complete order lifecycle including fills and portfolio updates
"""
import pytest
from decimal import Decimal
from uuid import uuid4

from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.trading.aggregates.portfolio import Portfolio
from src.application.trading.commands.place_order_command import (
    PlaceOrderCommand,
    PlaceOrderCommandHandler
)
from src.application.trading.events.order_filled_handler import OrderFilledEventHandler
from src.infrastructure.persistence.in_memory import (
    InMemoryOrderRepository,
    InMemoryPortfolioRepository
)
from src.infrastructure.brokers.mock_broker import MockBrokerService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus


class TestOrderFillLifecycle:
    """Test the complete order lifecycle from placement to fill to portfolio update"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create repositories
        self.portfolio_repo = InMemoryPortfolioRepository()
        self.order_repo = InMemoryOrderRepository()
        
        # Create event bus and broker
        self.event_bus = InMemoryEventBus()
        self.broker = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=1.0,
            event_bus=self.event_bus
        )
        
        # Create command handler
        self.place_order_handler = PlaceOrderCommandHandler(
            portfolio_repo=self.portfolio_repo,
            order_repo=self.order_repo,
            broker_service=self.broker,
            event_bus=self.event_bus
        )
        
        # Create and register event handler
        self.order_filled_handler = OrderFilledEventHandler(
            order_repo=self.order_repo,
            portfolio_repo=self.portfolio_repo
        )
        self.event_bus.subscribe("order.filled", self.order_filled_handler.handle)
        
        # Create a test portfolio
        self.portfolio = Portfolio.create(
            name="Test Portfolio",
            initial_cash=Decimal("10000.00"),
            currency="USD"
        )
        self.portfolio_repo.save(self.portfolio)
    
    def test_complete_order_lifecycle(self):
        """Test order placement → fill → portfolio update"""
        # Arrange
        symbol = "AAPL"
        quantity = 10
        fill_price = 150.00
        
        # Act 1: Place the order
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio.id,
            symbol=symbol,
            quantity=quantity,
            order_type="MARKET"
        )
        order_id = self.place_order_handler.handle(command)
        
        # Assert 1: Order created and portfolio funds reserved
        order = self.order_repo.get(order_id)
        assert order is not None
        assert order.status == OrderStatus.PENDING
        assert order.broker_order_id is not None
        
        portfolio = self.portfolio_repo.get(self.portfolio.id)
        assert portfolio.reserved_cash > 0
        assert portfolio.available_cash < Decimal("10000.00")
        initial_available = portfolio.available_cash
        
        # Act 2: Fill the order
        success = self.broker.fill_order(order.broker_order_id, fill_price)
        assert success is True
        
        # Assert 2: Order filled and portfolio updated
        # Reload order and portfolio
        order = self.order_repo.get(order_id)
        portfolio = self.portfolio_repo.get(self.portfolio.id)
        
        # Check order status
        assert order.status == OrderStatus.FILLED
        
        # Check portfolio cash adjustment
        total_cost = Decimal(str(fill_price * quantity))
        assert portfolio.reserved_cash == Decimal("0")  # No more reserved funds
        expected_cash = Decimal("10000.00") - total_cost
        assert portfolio.available_cash == expected_cash
        
        # Check portfolio position
        assert portfolio.get_position(symbol) == quantity
        assert symbol in portfolio.positions
    
    def test_multiple_orders_same_symbol(self):
        """Test multiple orders for the same symbol accumulate positions"""
        # Arrange
        symbol = "TSLA"
        
        # Place and fill first order
        command1 = PlaceOrderCommand(
            portfolio_id=self.portfolio.id,
            symbol=symbol,
            quantity=5,
            order_type="MARKET"
        )
        order_id1 = self.place_order_handler.handle(command1)
        order1 = self.order_repo.get(order_id1)
        self.broker.fill_order(order1.broker_order_id, 200.00)
        
        # Place and fill second order
        command2 = PlaceOrderCommand(
            portfolio_id=self.portfolio.id,
            symbol=symbol,
            quantity=3,
            order_type="MARKET"
        )
        order_id2 = self.place_order_handler.handle(command2)
        order2 = self.order_repo.get(order_id2)
        self.broker.fill_order(order2.broker_order_id, 205.00)
        
        # Assert: Positions accumulated
        portfolio = self.portfolio_repo.get(self.portfolio.id)
        assert portfolio.get_position(symbol) == 8  # 5 + 3
        
        # Check cash spent correctly
        total_cost = Decimal("1000.00") + Decimal("615.00")  # 5*200 + 3*205
        expected_cash = Decimal("10000.00") - total_cost
        assert portfolio.available_cash == expected_cash
    
    def test_fill_adjusts_for_different_prices(self):
        """Test that fills at different prices than expected adjust cash correctly"""
        # Arrange
        symbol = "GOOGL"
        quantity = 5
        
        # Place order (broker reserves estimated funds)
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio.id,
            symbol=symbol,
            quantity=quantity,
            order_type="MARKET"
        )
        order_id = self.place_order_handler.handle(command)
        order = self.order_repo.get(order_id)
        
        # Get reserved amount
        portfolio = self.portfolio_repo.get(self.portfolio.id)
        reserved_before = portfolio.reserved_cash
        available_before = portfolio.available_cash
        
        # Fill at a lower price than estimated
        actual_price = 90.00  # Lower than the estimated 100
        self.broker.fill_order(order.broker_order_id, actual_price)
        
        # Assert: Portfolio adjusted correctly
        portfolio = self.portfolio_repo.get(self.portfolio.id)
        actual_cost = Decimal(str(actual_price * quantity))
        
        # All reserved funds released, actual cost deducted
        assert portfolio.reserved_cash == Decimal("0")
        assert portfolio.available_cash == Decimal("10000.00") - actual_cost
        
        # Position created
        assert portfolio.get_position(symbol) == quantity
    
    def test_partial_fill_scenario(self):
        """Test handling when not all reserved funds are used"""
        # This tests the scenario where we reserve more funds than needed
        # (common with market orders where we estimate high)
        
        # Arrange
        symbol = "NVDA"
        quantity = 2
        
        # Place order
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio.id,
            symbol=symbol,
            quantity=quantity,
            order_type="MARKET"
        )
        order_id = self.place_order_handler.handle(command)
        order = self.order_repo.get(order_id)
        
        portfolio = self.portfolio_repo.get(self.portfolio.id)
        # We reserved: 2 * 100 * 1.05 = 210
        assert portfolio.reserved_cash == Decimal("210.00")
        assert portfolio.available_cash == Decimal("9790.00")
        
        # Fill at lower price
        self.broker.fill_order(order.broker_order_id, 80.00)
        
        # Assert: Excess funds returned
        portfolio = self.portfolio_repo.get(self.portfolio.id)
        actual_cost = Decimal("160.00")  # 2 * 80
        
        assert portfolio.reserved_cash == Decimal("0")
        assert portfolio.available_cash == Decimal("10000.00") - actual_cost
        assert portfolio.available_cash == Decimal("9840.00")
        assert portfolio.get_position(symbol) == quantity
    
    def test_no_portfolio_found_for_order(self):
        """Test graceful handling when portfolio can't be found for an order"""
        # Create an order without a portfolio
        order = Order.create(
            symbol="FAKE",
            quantity=1,
            order_type="MARKET"
        )
        self.order_repo.save(order)
        
        # Clear all portfolios
        self.portfolio_repo._portfolios.clear()
        
        # Trigger fill
        from src.domain.trading.events import OrderFilled
        event = OrderFilled(
            order_id=order.id,
            symbol="FAKE",
            quantity=1,
            fill_price=Decimal("100.00"),
            broker_order_id="BROKER-123"
        )
        
        # Should handle gracefully (log error but not crash)
        self.order_filled_handler.handle(event)
        
        # Order should still be updated
        order = self.order_repo.get(order.id)
        assert order.status == OrderStatus.FILLED