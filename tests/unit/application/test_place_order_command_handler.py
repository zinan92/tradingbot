"""
Unit tests for PlaceOrderCommandHandler

Tests follow TDD principles with proper mocking and isolation.
Tests focus on the handler's behavior, not integration with external systems.
"""
import pytest
from unittest.mock import Mock, MagicMock, call
from decimal import Decimal
from uuid import uuid4

from src.application.trading.commands.place_order_command import (
    PlaceOrderCommand,
    PlaceOrderCommandHandler,
    PortfolioNotFoundError
)
from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.value_objects import Symbol


class TestPlaceOrderCommandHandler:
    """Unit tests for PlaceOrderCommandHandler"""
    
    def setup_method(self):
        """Set up test doubles and handler"""
        # Create test doubles
        self.portfolio_repo = Mock()
        self.order_repo = Mock()
        self.broker_service = Mock()
        self.event_bus = Mock()
        
        # Create handler with test doubles
        self.handler = PlaceOrderCommandHandler(
            portfolio_repo=self.portfolio_repo,
            order_repo=self.order_repo,
            broker_service=self.broker_service,
            event_bus=self.event_bus
        )
        
        # Create test data
        self.portfolio_id = uuid4()
        self.test_portfolio = Mock(spec=Portfolio)
        self.test_portfolio.id = self.portfolio_id
        self.test_portfolio.pull_events.return_value = []
        
        self.test_order = Mock(spec=Order)
        self.test_order.id = uuid4()
        self.test_order.pull_events.return_value = []
        self.test_order.set_broker_order_id = Mock()
    
    def test_handle_valid_market_order(self):
        """Test handling a valid market order command"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=10,
            order_type="MARKET"
        )
        
        self.portfolio_repo.get.return_value = self.test_portfolio
        self.test_portfolio.place_order.return_value = self.test_order
        self.broker_service.submit_order_sync.return_value = "BROKER-123"
        
        # Act
        result = self.handler.handle(command)
        
        # Assert
        assert result == self.test_order.id
        
        # Verify interactions
        self.portfolio_repo.get.assert_called_once_with(self.portfolio_id)
        self.test_portfolio.place_order.assert_called_once_with(
            symbol="AAPL",
            quantity=10,
            order_type="MARKET",
            price=None
        )
        self.order_repo.save.assert_called_with(self.test_order)
        self.broker_service.submit_order_sync.assert_called_once_with(self.test_order)
        self.test_order.set_broker_order_id.assert_called_once_with("BROKER-123")
        self.portfolio_repo.save.assert_called_once_with(self.test_portfolio)
        
        # Verify order was saved twice (before and after broker submission)
        assert self.order_repo.save.call_count == 2
    
    def test_handle_valid_limit_order(self):
        """Test handling a valid limit order command"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="MSFT",
            quantity=5,
            order_type="LIMIT",
            price=Decimal("300.00")
        )
        
        self.portfolio_repo.get.return_value = self.test_portfolio
        self.test_portfolio.place_order.return_value = self.test_order
        self.broker_service.submit_order_sync.return_value = "BROKER-456"
        
        # Act
        result = self.handler.handle(command)
        
        # Assert
        assert result == self.test_order.id
        
        # Verify portfolio.place_order was called with correct price
        self.test_portfolio.place_order.assert_called_once_with(
            symbol="MSFT",
            quantity=5,
            order_type="LIMIT",
            price=300.0  # Converted to float
        )
    
    def test_handle_portfolio_not_found(self):
        """Test handling when portfolio doesn't exist"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=10,
            order_type="MARKET"
        )
        
        self.portfolio_repo.get.return_value = None
        
        # Act & Assert
        with pytest.raises(PortfolioNotFoundError) as exc:
            self.handler.handle(command)
        
        assert str(self.portfolio_id) in str(exc.value)
        
        # Verify no order was created or saved
        self.order_repo.save.assert_not_called()
        self.broker_service.submit_order_sync.assert_not_called()
    
    def test_handle_publishes_domain_events(self):
        """Test that domain events are published to event bus"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=10,
            order_type="MARKET"
        )
        
        order_event = Mock()
        portfolio_event = Mock()
        
        self.portfolio_repo.get.return_value = self.test_portfolio
        self.test_portfolio.place_order.return_value = self.test_order
        self.test_order.pull_events.return_value = [order_event]
        self.test_portfolio.pull_events.return_value = [portfolio_event]
        self.broker_service.submit_order_sync.return_value = "BROKER-789"
        
        # Act
        self.handler.handle(command)
        
        # Assert - Events were published
        self.event_bus.publish.assert_has_calls([
            call(order_event),
            call(portfolio_event)
        ])
        assert self.event_bus.publish.call_count == 2
    
    def test_validation_rejects_empty_portfolio_id(self):
        """Test validation rejects commands with missing portfolio ID"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=None,
            symbol="AAPL",
            quantity=10,
            order_type="MARKET"
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        
        assert "Portfolio ID is required" in str(exc.value)
    
    def test_validation_rejects_empty_symbol(self):
        """Test validation rejects empty symbol"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="",
            quantity=10,
            order_type="MARKET"
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        
        assert "Symbol is required" in str(exc.value)
    
    def test_validation_rejects_zero_quantity(self):
        """Test validation rejects zero quantity"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=0,
            order_type="MARKET"
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        
        assert "Quantity must be positive" in str(exc.value)
    
    def test_validation_rejects_negative_quantity(self):
        """Test validation rejects negative quantity"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=-5,
            order_type="MARKET"
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        
        assert "Quantity must be positive" in str(exc.value)
    
    def test_validation_rejects_invalid_order_type(self):
        """Test validation rejects invalid order type"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=10,
            order_type="INVALID"
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        
        assert "Order type must be MARKET or LIMIT" in str(exc.value)
    
    def test_validation_rejects_limit_order_without_price(self):
        """Test validation rejects limit order without price"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=10,
            order_type="LIMIT",
            price=None
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        
        assert "Price is required for LIMIT orders" in str(exc.value)
    
    def test_validation_rejects_negative_price(self):
        """Test validation rejects negative price"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=10,
            order_type="LIMIT",
            price=Decimal("-100.00")
        )
        
        # Act & Assert
        with pytest.raises(ValueError) as exc:
            self.handler.handle(command)
        
        assert "Price must be positive" in str(exc.value)
    
    def test_broker_failure_does_not_save_order(self):
        """Test that order is not saved if broker submission fails"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="AAPL",
            quantity=10,
            order_type="MARKET"
        )
        
        self.portfolio_repo.get.return_value = self.test_portfolio
        self.test_portfolio.place_order.return_value = self.test_order
        self.broker_service.submit_order_sync.side_effect = Exception("Broker error")
        
        # Act & Assert
        with pytest.raises(Exception) as exc:
            self.handler.handle(command)
        
        assert "Broker error" in str(exc.value)
        
        # Verify order was saved once but not updated with broker ID
        assert self.order_repo.save.call_count == 1
        self.test_order.set_broker_order_id.assert_not_called()
    
    def test_handle_with_whitespace_symbol(self):
        """Test that whitespace in symbol is handled correctly"""
        # Arrange
        command = PlaceOrderCommand(
            portfolio_id=self.portfolio_id,
            symbol="  AAPL  ",
            quantity=10,
            order_type="MARKET"
        )
        
        self.portfolio_repo.get.return_value = self.test_portfolio
        self.test_portfolio.place_order.return_value = self.test_order
        self.broker_service.submit_order_sync.return_value = "BROKER-123"
        
        # Act
        result = self.handler.handle(command)
        
        # Assert - Symbol should be trimmed
        self.test_portfolio.place_order.assert_called_once_with(
            symbol="AAPL",  # Trimmed
            quantity=10,
            order_type="MARKET",
            price=None
        )