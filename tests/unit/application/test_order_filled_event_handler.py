"""
Unit tests for OrderFilledEventHandler

Tests follow TDD principles with proper test doubles and isolation.
Focuses on handler behavior without external dependencies.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from uuid import uuid4
import logging

from src.application.trading.events.order_filled_handler import (
    OrderFilledEventHandler,
    OrderNotFoundError
)
from src.domain.trading.events import OrderFilled
from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.trading.aggregates.portfolio import Portfolio


class TestOrderFilledEventHandler:
    """Unit tests for OrderFilledEventHandler"""
    
    def setup_method(self):
        """Set up test doubles and handler"""
        # Create test doubles
        self.order_repo = Mock()
        self.portfolio_repo = Mock()
        
        # Create handler with test doubles
        self.handler = OrderFilledEventHandler(
            order_repo=self.order_repo,
            portfolio_repo=self.portfolio_repo
        )
        
        # Create test data
        self.order_id = uuid4()
        self.portfolio_id = uuid4()
        
        self.test_order = Mock(spec=Order)
        self.test_order.id = self.order_id
        self.test_order.fill = Mock()
        
        self.test_portfolio = Mock(spec=Portfolio)
        self.test_portfolio.id = self.portfolio_id
        self.test_portfolio.add_position = Mock()
        self.test_portfolio.complete_order_fill = Mock()
        self.test_portfolio.get_position = Mock(return_value=10)
        self.test_portfolio.available_cash = Decimal("8500.00")
        self.test_portfolio.reserved_cash = Decimal("0")
    
    def test_handle_successful_order_fill(self):
        """Test successful handling of order filled event"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="AAPL",
            quantity=10,
            fill_price=Decimal("150.00"),
            broker_order_id="BROKER-123"
        )
        
        self.order_repo.get.return_value = self.test_order
        self.portfolio_repo.get_all.return_value = [self.test_portfolio]
        self.test_portfolio.reserved_cash = Decimal("1600.00")  # Has reserved funds
        
        # Act
        self.handler.handle(event)
        
        # Assert - Order updated
        self.order_repo.get.assert_called_once_with(self.order_id)
        self.test_order.fill.assert_called_once_with(fill_price=150.0)
        self.order_repo.save.assert_called_once_with(self.test_order)
        
        # Assert - Portfolio updated
        self.test_portfolio.add_position.assert_called_once_with("AAPL", 10)
        self.test_portfolio.complete_order_fill.assert_called_once_with(
            symbol="AAPL",
            quantity=10,
            fill_price=Decimal("150.00"),
            order_id=self.order_id
        )
        self.portfolio_repo.save.assert_called_once_with(self.test_portfolio)
    
    def test_handle_order_not_found(self):
        """Test handling when order doesn't exist"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="AAPL",
            quantity=10,
            fill_price=Decimal("150.00"),
            broker_order_id="BROKER-123"
        )
        
        self.order_repo.get.return_value = None
        
        # Act & Assert
        with pytest.raises(OrderNotFoundError) as exc:
            self.handler.handle(event)
        
        assert str(self.order_id) in str(exc.value)
        
        # Verify no portfolio operations occurred
        self.portfolio_repo.get_all.assert_not_called()
        self.portfolio_repo.save.assert_not_called()
    
    def test_handle_portfolio_not_found_still_updates_order(self):
        """Test that order is still marked as filled even if portfolio not found"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="AAPL",
            quantity=10,
            fill_price=Decimal("150.00"),
            broker_order_id="BROKER-123"
        )
        
        self.order_repo.get.return_value = self.test_order
        self.portfolio_repo.get_all.return_value = []  # No portfolios
        
        # Act
        self.handler.handle(event)  # Should not raise
        
        # Assert - Order was still updated
        self.test_order.fill.assert_called_once_with(fill_price=150.0)
        self.order_repo.save.assert_called_once_with(self.test_order)
        
        # Assert - No portfolio operations
        self.portfolio_repo.save.assert_not_called()
    
    def test_find_portfolio_for_order_with_reserved_funds(self):
        """Test finding portfolio by checking reserved funds"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="MSFT",
            quantity=5,
            fill_price=Decimal("300.00"),
            broker_order_id="BROKER-456"
        )
        
        portfolio_with_funds = Mock(spec=Portfolio)
        portfolio_with_funds.reserved_cash = Decimal("1500.00")
        portfolio_with_funds.add_position = Mock()
        portfolio_with_funds.complete_order_fill = Mock()
        portfolio_with_funds.get_position = Mock(return_value=5)
        portfolio_with_funds.available_cash = Decimal("8500.00")
        
        portfolio_without_funds = Mock(spec=Portfolio)
        portfolio_without_funds.reserved_cash = Decimal("0")
        
        self.order_repo.get.return_value = self.test_order
        self.portfolio_repo.get_all.return_value = [
            portfolio_without_funds,
            portfolio_with_funds  # This one should be selected
        ]
        
        # Act
        self.handler.handle(event)
        
        # Assert - Correct portfolio was updated
        self.portfolio_repo.save.assert_called_once_with(portfolio_with_funds)
        portfolio_with_funds.add_position.assert_called_once()
        portfolio_with_funds.complete_order_fill.assert_called_once()
    
    def test_handle_with_different_fill_prices(self):
        """Test handling fills at different prices than expected"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="GOOGL",
            quantity=2,
            fill_price=Decimal("2500.00"),  # High price
            broker_order_id="BROKER-789"
        )
        
        self.order_repo.get.return_value = self.test_order
        self.portfolio_repo.get_all.return_value = [self.test_portfolio]
        self.test_portfolio.reserved_cash = Decimal("5200.00")  # Reserved more than needed
        
        # Act
        self.handler.handle(event)
        
        # Assert - Order filled with actual price
        self.test_order.fill.assert_called_once_with(fill_price=2500.0)
        
        # Assert - Portfolio adjusted with actual values
        self.test_portfolio.complete_order_fill.assert_called_once_with(
            symbol="GOOGL",
            quantity=2,
            fill_price=Decimal("2500.00"),
            order_id=self.order_id
        )
    
    @patch('src.application.trading.events.order_filled_handler.logger')
    def test_logs_order_fill_information(self, mock_logger):
        """Test that handler logs appropriate information"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="TSLA",
            quantity=3,
            fill_price=Decimal("800.00"),
            broker_order_id="BROKER-999"
        )
        
        self.order_repo.get.return_value = self.test_order
        self.portfolio_repo.get_all.return_value = [self.test_portfolio]
        self.test_portfolio.reserved_cash = Decimal("2500.00")
        
        # Act
        self.handler.handle(event)
        
        # Assert - Info logs were called
        assert mock_logger.info.called
        info_calls = mock_logger.info.call_args_list
        
        # Check that relevant information was logged
        first_log = str(info_calls[0])
        assert str(self.order_id) in first_log
        
        if len(info_calls) > 1:
            second_log = str(info_calls[1])
            assert "TSLA" in second_log
            assert "800" in second_log
    
    @patch('src.application.trading.events.order_filled_handler.logger')
    def test_logs_error_when_portfolio_not_found(self, mock_logger):
        """Test that handler logs error when portfolio not found"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="AAPL",
            quantity=10,
            fill_price=Decimal("150.00"),
            broker_order_id="BROKER-123"
        )
        
        self.order_repo.get.return_value = self.test_order
        self.portfolio_repo.get_all.return_value = []  # No portfolios
        
        # Act
        self.handler.handle(event)
        
        # Assert - Error was logged
        mock_logger.error.assert_called_once()
        error_message = str(mock_logger.error.call_args)
        assert "No portfolio found" in error_message
        assert str(self.order_id) in error_message
    
    def test_handle_exception_propagation(self):
        """Test that exceptions are properly propagated"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="AAPL",
            quantity=10,
            fill_price=Decimal("150.00"),
            broker_order_id="BROKER-123"
        )
        
        self.order_repo.get.side_effect = Exception("Database error")
        
        # Act & Assert
        with pytest.raises(Exception) as exc:
            self.handler.handle(event)
        
        assert "Database error" in str(exc.value)
    
    def test_portfolio_operations_order(self):
        """Test that portfolio operations are called in correct order"""
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="NVDA",
            quantity=4,
            fill_price=Decimal("600.00"),
            broker_order_id="BROKER-777"
        )
        
        self.order_repo.get.return_value = self.test_order
        
        # Create a portfolio mock that tracks call order
        portfolio_mock = Mock(spec=Portfolio)
        portfolio_mock.id = self.portfolio_id
        portfolio_mock.reserved_cash = Decimal("2500.00")
        portfolio_mock.available_cash = Decimal("7500.00")
        portfolio_mock.get_position = Mock(return_value=4)
        
        call_order = []
        portfolio_mock.add_position = Mock(side_effect=lambda *args: call_order.append('add_position'))
        portfolio_mock.complete_order_fill = Mock(side_effect=lambda *args, **kwargs: call_order.append('complete_order_fill'))
        
        self.portfolio_repo.get_all.return_value = [portfolio_mock]
        
        # Act
        self.handler.handle(event)
        
        # Assert - Operations called in correct order
        assert call_order == ['add_position', 'complete_order_fill']
        
        # Assert - Portfolio saved after all operations
        self.portfolio_repo.save.assert_called_once_with(portfolio_mock)
    
    def test_handle_partial_fill_quantity(self):
        """Test handling when fill quantity differs from order quantity"""
        # This tests resilience - handler should process whatever quantity is filled
        # Arrange
        event = OrderFilled(
            order_id=self.order_id,
            symbol="AMD",
            quantity=5,  # Only 5 filled
            fill_price=Decimal("120.00"),
            broker_order_id="BROKER-555"
        )
        
        self.order_repo.get.return_value = self.test_order
        self.portfolio_repo.get_all.return_value = [self.test_portfolio]
        self.test_portfolio.reserved_cash = Decimal("1000.00")  # Reserved for 10, but only 5 filled
        
        # Act
        self.handler.handle(event)
        
        # Assert - Portfolio updated with actual filled quantity
        self.test_portfolio.add_position.assert_called_once_with("AMD", 5)
        self.test_portfolio.complete_order_fill.assert_called_once_with(
            symbol="AMD",
            quantity=5,  # Actual filled quantity
            fill_price=Decimal("120.00"),
            order_id=self.order_id
        )