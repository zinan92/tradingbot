"""
Tests for the order cancellation endpoint

Tests the DELETE /api/v1/orders/{order_id} endpoint
"""
import pytest
from fastapi.testclient import TestClient
from uuid import UUID, uuid4
from decimal import Decimal

from src.adapters.api.app import app
# Import the module directly to access its functions for mocking
import importlib.util
spec = importlib.util.spec_from_file_location(
    "trading_router_module", 
    "/Users/park/tradingbot_v2/src/adapters/api/routers/trading_router.py"
)
trading_router_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trading_router_module)
router = trading_router_module.router
from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.trading.aggregates.portfolio import Portfolio
from src.infrastructure.persistence.in_memory import (
    InMemoryOrderRepository,
    InMemoryPortfolioRepository,
)
from src.infrastructure.brokers.mock_broker import MockBrokerService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

# Include the router in the app for testing
app.include_router(router)

# Create test client
client = TestClient(app)


class TestCancelOrderEndpoint:
    """Tests for the order cancellation endpoint"""
    
    def setup_method(self):
        """Set up test data"""
        # Reset repositories (they're singletons in the current implementation)
        # In production, use dependency injection
        
        # Create test portfolio
        self.portfolio_id = uuid4()
        self.portfolio = Portfolio.create(
            name="Test Portfolio",
            initial_cash=Decimal("10000.00"),
            currency="USD"
        )
        self.portfolio.id = self.portfolio_id
        
        # Create test order
        self.order_id = uuid4()
        self.test_order = Order(
            id=self.order_id,
            symbol="AAPL",
            quantity=100,
            order_type="MARKET",
            price=None,
            status=OrderStatus.PENDING,
            broker_order_id="BROKER-TEST123",
            created_at=None,
            filled_at=None,
            cancelled_at=None,
            cancellation_reason=None
        )
    
    def test_successful_order_cancellation(self, monkeypatch):
        """Test successful order cancellation via DELETE endpoint"""
        # Setup mock repositories
        order_repo = InMemoryOrderRepository()
        order_repo.save(self.test_order)
        
        broker_service = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=1.0
        )
        broker_service._submitted_orders["BROKER-TEST123"] = self.test_order
        
        # Monkey patch the dependencies
        def mock_get_repositories():
            return {
                "order_repo": order_repo,
                "portfolio_repo": InMemoryPortfolioRepository()
            }
        
        def mock_get_infrastructure():
            return {
                "broker_service": broker_service,
                "event_bus": InMemoryEventBus()
            }
        
        monkeypatch.setattr(
            trading_router_module,
            "get_repositories",
            mock_get_repositories
        )
        monkeypatch.setattr(
            trading_router_module,
            "get_infrastructure",
            mock_get_infrastructure
        )
        
        # Make request
        response = client.request(
            "DELETE",
            f"/api/v1/orders/{self.order_id}",
            json={"reason": "User requested cancellation"}
        )
        
        # Assert response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["order_id"] == str(self.order_id)
        assert data["message"] == "Order cancellation requested"
        
        # Verify order was cancelled
        cancelled_order = order_repo.get(self.order_id)
        assert cancelled_order.status == OrderStatus.CANCELLED
    
    def test_order_not_found(self, monkeypatch):
        """Test 404 when order doesn't exist"""
        # Setup empty repository
        order_repo = InMemoryOrderRepository()
        
        def mock_get_repositories():
            return {
                "order_repo": order_repo,
                "portfolio_repo": InMemoryPortfolioRepository()
            }
        
        def mock_get_infrastructure():
            return {
                "broker_service": MockBrokerService(),
                "event_bus": InMemoryEventBus()
            }
        
        monkeypatch.setattr(
            trading_router_module,
            "get_repositories",
            mock_get_repositories
        )
        monkeypatch.setattr(
            trading_router_module,
            "get_infrastructure",
            mock_get_infrastructure
        )
        
        # Make request with non-existent order ID
        non_existent_id = uuid4()
        response = client.request(
            "DELETE",
            f"/api/v1/orders/{non_existent_id}",
            json={"reason": "Test cancellation"}
        )
        
        # Assert 404 response
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_cannot_cancel_filled_order(self, monkeypatch):
        """Test 409 when trying to cancel a filled order"""
        # Setup order as filled
        self.test_order.status = OrderStatus.FILLED
        
        order_repo = InMemoryOrderRepository()
        order_repo.save(self.test_order)
        
        def mock_get_repositories():
            return {
                "order_repo": order_repo,
                "portfolio_repo": InMemoryPortfolioRepository()
            }
        
        def mock_get_infrastructure():
            return {
                "broker_service": MockBrokerService(),
                "event_bus": InMemoryEventBus()
            }
        
        monkeypatch.setattr(
            trading_router_module,
            "get_repositories",
            mock_get_repositories
        )
        monkeypatch.setattr(
            trading_router_module,
            "get_infrastructure",
            mock_get_infrastructure
        )
        
        # Make request
        response = client.request(
            "DELETE",
            f"/api/v1/orders/{self.order_id}",
            json={"reason": "Try to cancel filled order"}
        )
        
        # Assert 409 Conflict response
        assert response.status_code == 409
        data = response.json()
        assert "cannot be cancelled" in data["detail"].lower()
        assert "filled" in data["detail"].lower()
    
    def test_broker_error_handling(self, monkeypatch):
        """Test 500 when broker fails to cancel"""
        # Setup order
        order_repo = InMemoryOrderRepository()
        order_repo.save(self.test_order)
        
        # Setup broker with 0% success rate
        broker_service = MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=0.0  # Always fail
        )
        # Don't add order to broker's internal list so it will fail
        
        def mock_get_repositories():
            return {
                "order_repo": order_repo,
                "portfolio_repo": InMemoryPortfolioRepository()
            }
        
        def mock_get_infrastructure():
            return {
                "broker_service": broker_service,
                "event_bus": InMemoryEventBus()
            }
        
        monkeypatch.setattr(
            trading_router_module,
            "get_repositories",
            mock_get_repositories
        )
        monkeypatch.setattr(
            trading_router_module,
            "get_infrastructure",
            mock_get_infrastructure
        )
        
        # Make request
        response = client.request(
            "DELETE",
            f"/api/v1/orders/{self.order_id}",
            json={"reason": "Test broker failure"}
        )
        
        # Assert 500 response for broker error
        assert response.status_code == 500
        data = response.json()
        assert "broker" in data["detail"].lower()
    
    def test_missing_reason_validation(self):
        """Test that reason is required in request body"""
        response = client.request(
            "DELETE",
            f"/api/v1/orders/{uuid4()}",
            json={}  # Missing reason
        )
        
        # Should get validation error
        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "reason" in str(data["detail"]).lower()
    
    def test_empty_reason_validation(self):
        """Test that reason cannot be empty"""
        response = client.request(
            "DELETE",
            f"/api/v1/orders/{uuid4()}",
            json={"reason": ""}  # Empty reason
        )
        
        # Should get validation error
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_invalid_order_id_format(self):
        """Test that invalid UUID format is rejected"""
        response = client.request(
            "DELETE",
            "/api/v1/orders/not-a-uuid",
            json={"reason": "Test"}
        )
        
        # Should get validation error
        assert response.status_code == 422  # Unprocessable Entity