import pytest
from decimal import Decimal
from uuid import uuid4

from src.application.trading.commands.place_order_command import (
    PlaceOrderCommand,
    PlaceOrderCommandHandler,
    PortfolioNotFoundError,
)
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.aggregates.order import OrderStatus
from src.infrastructure.persistence.in_memory import (
    InMemoryOrderRepository,
    InMemoryPortfolioRepository,
)
from src.infrastructure.brokers.mock_broker import MockBrokerService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus


class TestPlaceOrderUseCase:
    """Integration tests for the complete place order flow"""
    
    def setup_method(self):
        """Set up test dependencies"""
        # Create repositories
        self.portfolio_repo = InMemoryPortfolioRepository()
        self.order_repo = InMemoryOrderRepository()
        
        # Create infrastructure services
        self.broker_service = MockBrokerService()
        self.event_bus = InMemoryEventBus()
        
        # Create command handler
        self.handler = PlaceOrderCommandHandler(
            portfolio_repo=self.portfolio_repo,
            order_repo=self.order_repo,
            broker_service=self.broker_service,
            event_bus=self.event_bus
        )
        
        # Create test portfolio with initial cash
        self.test_portfolio = Portfolio.create(
            name="Test Portfolio",
            initial_cash=Decimal("10000.00"),
            currency="USD"
        )
        self.portfolio_repo.save(self.test_portfolio)
    
    def test_successful_market_order_placement(self):
        """Test successfully placing a market order"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="AAPL",
            quantity=10,
            order_type="MARKET"
        )
        
        # Act
        order_id = self.handler.handle(command)
        
        # Assert - Order was created and saved
        assert order_id is not None
        saved_order = self.order_repo.get(order_id)
        assert saved_order is not None
        assert saved_order.symbol == "AAPL"
        assert saved_order.quantity == 10
        assert saved_order.order_type == "MARKET"
        assert saved_order.status == OrderStatus.PENDING
        assert saved_order.broker_order_id is not None
        assert saved_order.broker_order_id.startswith("BROKER-")
        
        # Assert - Portfolio funds were reserved
        updated_portfolio = self.portfolio_repo.get(self.test_portfolio.id)
        assert updated_portfolio.available_cash < Decimal("10000.00")
        assert updated_portfolio.reserved_cash > Decimal("0")
        
        # Assert - Events were published
        events = self.event_bus.get_published_events()
        assert len(events) > 0
        assert any("OrderPlaced" in str(e) for e in events)
    
    def test_successful_limit_order_placement(self):
        """Test successfully placing a limit order"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="MSFT",
            quantity=5,
            order_type="LIMIT",
            price=Decimal("300.00")
        )
        
        # Act
        order_id = self.handler.handle(command)
        
        # Assert - Order was created with price
        saved_order = self.order_repo.get(order_id)
        assert saved_order is not None
        assert saved_order.symbol == "MSFT"
        assert saved_order.quantity == 5
        assert saved_order.order_type == "LIMIT"
        assert saved_order.price == 300.00
        
        # Assert - Exact funds were reserved (5 * 300 = 1500)
        updated_portfolio = self.portfolio_repo.get(self.test_portfolio.id)
        assert updated_portfolio.reserved_cash == Decimal("1500.00")
        assert updated_portfolio.available_cash == Decimal("8500.00")
    
    def test_insufficient_funds_rejection(self):
        """Test that orders are rejected when insufficient funds"""
        # Arrange - Try to buy too many shares
        command = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="AAPL",
            quantity=1000,  # Too many shares
            order_type="MARKET"
        )
        
        # Act & Assert
        with pytest.raises(Exception) as exc:
            self.handler.handle(command)
        assert "Insufficient funds" in str(exc.value)
        
        # Assert - No order was saved
        assert self.order_repo.count() == 0
        
        # Assert - Portfolio funds unchanged
        portfolio = self.portfolio_repo.get(self.test_portfolio.id)
        assert portfolio.available_cash == Decimal("10000.00")
        assert portfolio.reserved_cash == Decimal("0")
    
    def test_portfolio_not_found(self):
        """Test handling non-existent portfolio"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=uuid4(),  # Non-existent portfolio
            symbol="AAPL",
            quantity=10,
            order_type="MARKET"
        )
        
        # Act & Assert
        with pytest.raises(PortfolioNotFoundError) as exc:
            self.handler.handle(command)
        assert "not found" in str(exc.value)
    
    def test_invalid_symbol_validation(self):
        """Test validation of invalid symbol"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="",  # Invalid empty symbol
            quantity=10,
            order_type="MARKET"
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        assert "Symbol is required" in str(exc.value)
    
    def test_invalid_quantity_validation(self):
        """Test validation of invalid quantity"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="AAPL",
            quantity=0,  # Invalid zero quantity
            order_type="MARKET"
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        assert "Quantity must be positive" in str(exc.value)
    
    def test_limit_order_without_price_validation(self):
        """Test that limit orders require a price"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="AAPL",
            quantity=10,
            order_type="LIMIT",
            price=None  # Missing price for limit order
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        assert "Price is required for LIMIT orders" in str(exc.value)
    
    def test_multiple_orders_from_same_portfolio(self):
        """Test placing multiple orders from the same portfolio"""
        # Arrange
        command1 = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="AAPL",
            quantity=5,
            order_type="LIMIT",
            price=Decimal("150.00")
        )
        command2 = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="MSFT",
            quantity=3,
            order_type="LIMIT",
            price=Decimal("300.00")
        )
        
        # Act
        order_id1 = self.handler.handle(command1)
        order_id2 = self.handler.handle(command2)
        
        # Assert - Both orders created
        assert order_id1 != order_id2
        assert self.order_repo.exists(order_id1)
        assert self.order_repo.exists(order_id2)
        
        # Assert - Funds reserved for both orders
        # Order 1: 5 * 150 = 750
        # Order 2: 3 * 300 = 900
        # Total reserved: 1650
        portfolio = self.portfolio_repo.get(self.test_portfolio.id)
        assert portfolio.reserved_cash == Decimal("1650.00")
        assert portfolio.available_cash == Decimal("8350.00")
    
    def test_broker_integration(self):
        """Test that orders are submitted to broker"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.test_portfolio.id,
            symbol="AAPL",
            quantity=10,
            order_type="MARKET"
        )
        
        # Act
        order_id = self.handler.handle(command)
        
        # Assert - Order has broker ID
        order = self.order_repo.get(order_id)
        assert order.broker_order_id is not None
        
        # Assert - Broker has the order (status is now lowercase)
        broker_status = self.broker_service.get_order_status(order.broker_order_id)
        assert broker_status == "pending"