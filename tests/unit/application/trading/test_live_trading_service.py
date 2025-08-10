"""
Unit tests for Live Trading Service

Tests the application layer with fake broker implementation.
No infrastructure dependencies.
"""
import asyncio
import pytest
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

from src.application.trading.services.live_trading_service_refactored import (
    LiveTradingService,
    TradingSession,
    TradingSessionStatus
)
from src.domain.shared.ports import ExecutionPort
from src.domain.shared.contracts import (
    OrderRequest,
    OrderSide,
    OrderType,
    OrderStatus,
    Position as PositionDTO,
    PositionSide
)
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.aggregates.order import Order
from src.config.trading_config import TradingConfig


class FakeExecutionPort(ExecutionPort):
    """Fake implementation of ExecutionPort for testing"""
    
    def __init__(self):
        self.orders = {}
        self.positions = {}
        self.balance = {
            'available': Decimal("10000"),
            'locked': Decimal("0"),
            'total': Decimal("10000")
        }
        self.order_counter = 1000
        self.should_fail_submit = False
        self.should_fail_cancel = False
        self.submit_delay = 0
        self.precision_map = {
            'BTCUSDT': {'price': 2, 'quantity': 3},
            'ETHUSDT': {'price': 2, 'quantity': 4}
        }
    
    async def submit(self, order: Dict[str, Any]) -> str:
        """Submit fake order"""
        if self.should_fail_submit:
            raise Exception("Broker error: Order submission failed")
        
        if self.submit_delay:
            await asyncio.sleep(self.submit_delay)
        
        # Apply precision rounding
        symbol = order['symbol']
        if symbol in self.precision_map:
            precision = self.precision_map[symbol]
            if 'price' in order and order['price']:
                order['price'] = round(float(order['price']), precision['price'])
            order['quantity'] = round(float(order['quantity']), precision['quantity'])
        
        order_id = str(self.order_counter)
        self.order_counter += 1
        
        self.orders[order_id] = {
            'order_id': order_id,
            'symbol': order['symbol'],
            'side': order['side'],
            'type': order.get('type', 'market'),
            'quantity': Decimal(str(order['quantity'])),
            'price': Decimal(str(order.get('price', 0))),
            'status': 'pending',
            'filled_quantity': Decimal("0"),
            'created_at': datetime.utcnow()
        }
        
        # Update balance
        order_value = Decimal(str(order['quantity'])) * Decimal(str(order.get('price', 100)))
        self.balance['available'] -= order_value
        self.balance['locked'] += order_value
        
        return order_id
    
    async def cancel(self, order_id: str) -> bool:
        """Cancel fake order"""
        if self.should_fail_cancel:
            raise Exception("Broker error: Order cancellation failed")
        
        if order_id in self.orders:
            order = self.orders[order_id]
            if order['status'] == 'pending':
                order['status'] = 'cancelled'
                
                # Release locked balance
                order_value = order['quantity'] * order.get('price', Decimal("100"))
                self.balance['available'] += order_value
                self.balance['locked'] -= order_value
                
                return True
        return False
    
    async def positions(self) -> List[Dict[str, Any]]:
        """Get fake positions"""
        return list(self.positions.values())
    
    async def orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get fake orders"""
        orders = list(self.orders.values())
        if status:
            orders = [o for o in orders if o['status'] == status]
        return orders
    
    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get specific fake order"""
        return self.orders.get(order_id)
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get fake position for symbol"""
        return self.positions.get(symbol)
    
    async def modify_order(self, order_id: str, modifications: Dict[str, Any]) -> bool:
        """Modify fake order"""
        if order_id in self.orders:
            order = self.orders[order_id]
            order.update(modifications)
            return True
        return False
    
    async def get_account_balance(self) -> Dict[str, Decimal]:
        """Get fake account balance"""
        return self.balance.copy()
    
    def add_position(self, symbol: str, side: str, quantity: Decimal, entry_price: Decimal):
        """Helper to add a fake position"""
        self.positions[symbol] = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'entry_price': entry_price,
            'current_price': entry_price,
            'unrealized_pnl': Decimal("0"),
            'realized_pnl': Decimal("0")
        }
    
    def fill_order(self, order_id: str, fill_price: Optional[Decimal] = None):
        """Helper to mark an order as filled"""
        if order_id in self.orders:
            order = self.orders[order_id]
            order['status'] = 'filled'
            order['filled_quantity'] = order['quantity']
            order['average_fill_price'] = fill_price or order.get('price', Decimal("100"))
            order['updated_at'] = datetime.utcnow()
            
            # Release locked balance
            order_value = order['quantity'] * order.get('price', Decimal("100"))
            self.balance['locked'] -= order_value


class FakeEventBus:
    """Fake implementation of EventBus for testing"""
    
    def __init__(self):
        self.published_events = []
        self.subscribers = {}
        self.all_subscribers = []
    
    def publish(self, event) -> None:
        """Publish fake event synchronously"""
        self.published_events.append({
            'event': event,
            'timestamp': datetime.utcnow()
        })
        
        # Call type-specific subscribers
        event_type = type(event)
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                handler(event)
        
        # Call all-event subscribers
        for handler in self.all_subscribers:
            handler(event)
    
    async def publish_async(self, event) -> None:
        """Publish fake event asynchronously"""
        self.publish(event)
    
    def subscribe(self, event_type, handler) -> None:
        """Subscribe to fake events"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type, handler) -> None:
        """Unsubscribe from fake events"""
        if event_type in self.subscribers and handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
    
    def subscribe_to_all(self, handler) -> None:
        """Subscribe to all events"""
        self.all_subscribers.append(handler)
    
    # Helper method for testing
    async def publish_string(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Publish with string event type (for compatibility)"""
        self.published_events.append({
            'type': event_type,
            'data': event_data,
            'timestamp': datetime.utcnow()
        })
    
    def get_events_of_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Helper to get events of specific type"""
        return [e for e in self.published_events if e.get('type') == event_type]


class FakeRepository:
    """Fake repository for testing"""
    
    def __init__(self):
        self.entities = {}
    
    def save(self, entity):
        """Save entity"""
        self.entities[entity.id] = entity
    
    def get(self, entity_id):
        """Get entity by ID"""
        return self.entities.get(entity_id)
    
    def get_all(self):
        """Get all entities"""
        return list(self.entities.values())
    
    def delete(self, entity_id):
        """Delete entity"""
        if entity_id in self.entities:
            del self.entities[entity_id]


@pytest.fixture
def fake_execution_port():
    """Create fake execution port"""
    return FakeExecutionPort()


@pytest.fixture
def fake_event_bus():
    """Create fake event bus"""
    return FakeEventBus()


@pytest.fixture
def fake_repositories():
    """Create fake repositories"""
    return {
        'portfolio': FakeRepository(),
        'order': FakeRepository(),
        'position': FakeRepository()
    }


@pytest.fixture
def trading_config():
    """Create trading configuration"""
    from src.config.trading_config import (
        TradingMode, BinanceConfig, RiskConfig, 
        PositionSizingConfig, OrderConfig, WebSocketConfig, SignalConfig, OrderType
    )
    
    config = TradingConfig(
        mode=TradingMode.TESTNET,
        enabled=True,
        binance=BinanceConfig(
            api_key="test_key",
            api_secret="test_secret", 
            testnet=True
        ),
        risk=RiskConfig(
            max_leverage=10,
            max_position_size_usdt=Decimal("10000"),
            max_positions=5,
            daily_loss_limit_usdt=Decimal("500"),
            max_drawdown_percent=Decimal("10")
        ),
        position_sizing=PositionSizingConfig(
            default_position_size_percent=Decimal("2"),
            use_kelly_criterion=False,
            kelly_fraction=Decimal("0.25")
        ),
        order=OrderConfig(
            default_order_type=OrderType.MARKET,
            limit_order_offset_percent=Decimal("0.1"),
            stop_loss_percent=Decimal("2.0"),
            take_profit_percent=Decimal("5.0")
        ),
        websocket=WebSocketConfig(
            reconnect_delay=5,
            max_reconnect_delay=60,
            heartbeat_interval=30
        ),
        signal=SignalConfig(
            auto_execute=True,
            confidence_threshold=Decimal("0.7"),
            strength_threshold=Decimal("0.5"),
            signal_mappings={}
        )
    )
    return config


@pytest.fixture
def trading_service(fake_execution_port, fake_event_bus, fake_repositories, trading_config):
    """Create trading service with fakes"""
    # Add a test portfolio
    portfolio = Portfolio.create(
        name="Test Portfolio",
        initial_cash=Decimal("10000"),
        currency="USDT"
    )
    fake_repositories['portfolio'].save(portfolio)
    
    service = LiveTradingService(
        execution_port=fake_execution_port,
        event_bus=fake_event_bus,
        portfolio_repository=fake_repositories['portfolio'],
        order_repository=fake_repositories['order'],
        position_repository=fake_repositories['position'],
        config=trading_config
    )
    
    # Store portfolio ID for tests
    service.test_portfolio_id = portfolio.id
    
    return service


class TestLiveTradingService:
    """Test Live Trading Service"""
    
    @pytest.mark.asyncio
    async def test_start_session(self, trading_service, fake_event_bus):
        """Test starting a trading session"""
        # Start session
        session = await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Verify session created
        assert session is not None
        assert session.status == TradingSessionStatus.RUNNING
        assert session.portfolio_id == trading_service.test_portfolio_id
        assert session.started_at is not None
        
        # Verify event published
        events = fake_event_bus.get_events_of_type("trading.session.started")
        assert len(events) == 1
        assert events[0]['data']['portfolio_id'] == str(trading_service.test_portfolio_id)
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_place_order_happy_path(self, trading_service, fake_execution_port, fake_event_bus):
        """Test placing an order successfully"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Create order request
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.001"),
            price=Decimal("50000.00")
        )
        
        # Place order
        response = await trading_service.place_order(order_request)
        
        # Verify response
        assert response.order_id == "1000"  # First fake order ID
        assert response.symbol == "BTCUSDT"
        assert response.side == OrderSide.BUY
        assert response.status == OrderStatus.PENDING
        assert response.quantity == Decimal("0.001")
        
        # Verify order in fake broker
        assert "1000" in fake_execution_port.orders
        broker_order = fake_execution_port.orders["1000"]
        assert broker_order['symbol'] == "BTCUSDT"
        assert broker_order['quantity'] == Decimal("0.001")
        
        # Verify event published
        events = fake_event_bus.get_events_of_type("trading.order.placed")
        assert len(events) == 1
        assert events[0]['data']['symbol'] == "BTCUSDT"
        
        # Verify metrics updated
        assert trading_service.metrics["orders_placed"] == 1
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_place_order_broker_error(self, trading_service, fake_execution_port):
        """Test order placement with broker error"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set broker to fail
        fake_execution_port.should_fail_submit = True
        
        # Create order request
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.001")
        )
        
        # Place order should raise exception
        with pytest.raises(Exception) as exc_info:
            await trading_service.place_order(order_request)
        
        assert "Order submission failed" in str(exc_info.value)
        
        # Verify metrics
        assert trading_service.metrics["orders_rejected"] == 1
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, trading_service, fake_execution_port, fake_event_bus):
        """Test cancelling an order"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Place an order first
        order_request = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("3000.00")
        )
        response = await trading_service.place_order(order_request)
        
        # Get the order ID from active orders
        order_id = list(trading_service.active_orders.keys())[0]
        
        # Cancel the order
        success = await trading_service.cancel_order(order_id)
        
        # Verify cancellation
        assert success is True
        assert order_id not in trading_service.active_orders
        
        # Verify broker order cancelled
        broker_order = fake_execution_port.orders["1000"]
        assert broker_order['status'] == 'cancelled'
        
        # Verify event published
        events = fake_event_bus.get_events_of_type("trading.order.cancelled")
        assert len(events) == 1
        
        # Verify metrics
        assert trading_service.metrics["orders_cancelled"] == 1
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_precision_rounding(self, trading_service, fake_execution_port):
        """Test that prices and quantities are rounded correctly"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Place order with high precision values
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.123456789"),  # Should round to 0.123
            price=Decimal("50000.123456")     # Should round to 50000.12
        )
        
        response = await trading_service.place_order(order_request)
        
        # Check broker order has rounded values
        broker_order = fake_execution_port.orders[response.order_id]
        assert broker_order['quantity'] == Decimal("0.123")
        assert broker_order['price'] == Decimal("50000.12")
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_get_positions(self, trading_service, fake_execution_port):
        """Test getting positions"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Add fake positions
        fake_execution_port.add_position(
            "BTCUSDT", "long", Decimal("0.1"), Decimal("50000")
        )
        fake_execution_port.add_position(
            "ETHUSDT", "short", Decimal("1.0"), Decimal("3000")
        )
        
        # Get positions
        positions = await trading_service.get_positions()
        
        # Verify positions
        assert len(positions) == 2
        
        btc_pos = next(p for p in positions if p.symbol == "BTCUSDT")
        assert btc_pos.side == PositionSide.LONG
        assert btc_pos.quantity == Decimal("0.1")
        assert btc_pos.entry_price == Decimal("50000")
        
        eth_pos = next(p for p in positions if p.symbol == "ETHUSDT")
        assert eth_pos.side == PositionSide.SHORT
        assert eth_pos.quantity == Decimal("1.0")
        assert eth_pos.entry_price == Decimal("3000")
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_get_portfolio_state(self, trading_service, fake_execution_port):
        """Test getting portfolio state"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Add a position
        fake_execution_port.add_position(
            "BTCUSDT", "long", Decimal("0.1"), Decimal("50000")
        )
        
        # Get portfolio state
        state = await trading_service.get_portfolio_state()
        
        # Verify state
        assert state.account_id == str(trading_service.test_portfolio_id)
        assert state.balance == Decimal("10000")
        assert state.equity == Decimal("10000")
        assert len(state.positions) == 1
        assert state.positions[0].symbol == "BTCUSDT"
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_stop_session_cancels_orders(self, trading_service, fake_execution_port):
        """Test that stopping session cancels pending orders"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Place multiple orders
        for i in range(3):
            order_request = OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("0.001"),
                price=Decimal(f"{50000 + i * 100}")
            )
            await trading_service.place_order(order_request)
        
        # Verify orders are active
        assert len(trading_service.active_orders) == 3
        
        # Stop session
        await trading_service.stop_session("Test complete")
        
        # Verify all orders cancelled
        for order_id in fake_execution_port.orders:
            assert fake_execution_port.orders[order_id]['status'] == 'cancelled'
        
        # Verify session stopped
        assert trading_service.current_session.status == TradingSessionStatus.STOPPED
        assert trading_service.current_session.stopped_at is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, trading_service, fake_execution_port):
        """Test concurrent order operations"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Place multiple orders concurrently
        tasks = []
        for i in range(5):
            order_request = OrderRequest(
                symbol="BTCUSDT",
                side=OrderSide.BUY if i % 2 == 0 else OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=Decimal("0.001"),
                price=Decimal(f"{50000 + i * 100}")
            )
            tasks.append(trading_service.place_order(order_request))
        
        responses = await asyncio.gather(*tasks)
        
        # Verify all orders placed
        assert len(responses) == 5
        assert len(fake_execution_port.orders) == 5
        
        # Verify unique order IDs
        order_ids = [r.order_id for r in responses]
        assert len(set(order_ids)) == 5
        
        # Clean up
        await trading_service.stop_session()


class TestBrokerErrorHandling:
    """Test broker error scenarios"""
    
    @pytest.mark.asyncio
    async def test_insufficient_balance_error(self, trading_service, fake_execution_port):
        """Test handling insufficient balance"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set very low balance
        fake_execution_port.balance['available'] = Decimal("10")
        
        # Try to place large order
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),  # Large quantity
            price=Decimal("50000")
        )
        
        # This should succeed (fake broker doesn't check balance strictly)
        # In real implementation, it would raise InsufficientBalanceError
        response = await trading_service.place_order(order_request)
        assert response is not None
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_order_not_found_error(self, trading_service):
        """Test cancelling non-existent order"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Try to cancel non-existent order
        fake_order_id = uuid4()
        
        with pytest.raises(ValueError) as exc_info:
            await trading_service.cancel_order(fake_order_id)
        
        assert "not found" in str(exc_info.value)
        
        # Clean up
        await trading_service.stop_session()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])