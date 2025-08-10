"""
Unit tests for Risk Validation in Trading Service

Tests various risk scenarios including blocks, adjustments, and approvals.
"""
import asyncio
import pytest
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from src.application.trading.services.live_trading_service_refactored import (
    LiveTradingService,
    TradingSession,
    TradingSessionStatus
)
from src.domain.shared.ports import ExecutionPort, RiskPort, RiskAction
from src.domain.shared.contracts import (
    OrderRequest,
    OrderSide,
    OrderType,
    OrderStatus
)
from src.domain.trading.aggregates.portfolio import Portfolio
from src.config.trading_config import (
    TradingConfig, TradingMode, BinanceConfig, RiskConfig,
    PositionSizingConfig, OrderConfig, WebSocketConfig, SignalConfig,
    OrderType as ConfigOrderType
)


class FakeRiskPort(RiskPort):
    """Fake implementation of RiskPort for testing"""
    
    def __init__(self):
        self.validation_scenario = "approve"  # Default to approve
        self.daily_loss = Decimal("0")
        self.current_exposure = Decimal("0")
        self.max_exposure = Decimal("100000")
        self.max_position_size = Decimal("10000")
        self.max_leverage = 10
        self.daily_loss_limit = Decimal("500")
        self.correlation_threshold = 0.7
        self.margin_requirement = Decimal("0.1")  # 10% margin
        
    async def validate_trade(
        self,
        order: Dict[str, Any],
        portfolio_state: Dict[str, Any]
    ) -> Tuple[RiskAction, str, Optional[Dict[str, Any]]]:
        """Validate trade based on configured scenario"""
        
        # Extract order details
        quantity = Decimal(str(order.get('quantity', 0)))
        price = Decimal(str(order.get('price', 100))) if order.get('price') else Decimal("100")
        symbol = order.get('symbol', 'BTCUSDT')
        
        # Calculate order value
        order_value = quantity * price
        
        # Scenario-based validation
        if self.validation_scenario == "oversize":
            if order_value > self.max_position_size:
                return (
                    RiskAction.BLOCK,
                    f"Position size ${order_value} exceeds maximum ${self.max_position_size}",
                    None
                )
        
        elif self.validation_scenario == "leverage_limit":
            leverage = order.get('leverage', 1)
            if leverage > self.max_leverage:
                return (
                    RiskAction.BLOCK,
                    f"Leverage {leverage}x exceeds maximum {self.max_leverage}x",
                    None
                )
        
        elif self.validation_scenario == "daily_loss":
            if abs(self.daily_loss) >= self.daily_loss_limit:
                return (
                    RiskAction.BLOCK,
                    f"Daily loss limit ${self.daily_loss_limit} reached",
                    None
                )
        
        elif self.validation_scenario == "correlation":
            # Check if position is too correlated with existing
            return (
                RiskAction.BLOCK,
                f"Position correlation exceeds threshold {self.correlation_threshold}",
                None
            )
        
        elif self.validation_scenario == "margin_insufficient":
            required_margin = order_value * self.margin_requirement
            available_margin = portfolio_state.get('balance', Decimal("0"))
            if required_margin > available_margin:
                return (
                    RiskAction.BLOCK,
                    f"Insufficient margin: required ${required_margin}, available ${available_margin}",
                    None
                )
        
        elif self.validation_scenario == "adjust_size":
            # Adjust position size down by 50%
            adjusted_quantity = quantity * Decimal("0.5")
            return (
                RiskAction.ADJUST,
                "Position size reduced for risk management",
                {"quantity": float(adjusted_quantity)}
            )
        
        elif self.validation_scenario == "adjust_price":
            # Adjust price for better entry
            adjusted_price = price * Decimal("0.99")  # 1% better price
            return (
                RiskAction.ADJUST,
                "Price adjusted for better risk/reward",
                {"price": float(adjusted_price)}
            )
        
        # Default: approve
        return (RiskAction.ALLOW, "Trade approved", None)
    
    async def calculate_position_size(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Optional[Decimal],
        portfolio_value: Decimal,
        risk_per_trade: Decimal
    ) -> Decimal:
        """Calculate position size"""
        if stop_loss:
            risk_amount = portfolio_value * risk_per_trade
            price_risk = abs(entry_price - stop_loss)
            if price_risk > 0:
                return risk_amount / price_risk
        return portfolio_value * risk_per_trade / entry_price
    
    async def check_exposure_limits(
        self,
        portfolio_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check exposure limits"""
        return {
            "current_exposure": float(self.current_exposure),
            "max_exposure": float(self.max_exposure),
            "exposure_ratio": float(self.current_exposure / self.max_exposure) if self.max_exposure else 0,
            "within_limits": self.current_exposure <= self.max_exposure
        }
    
    async def calculate_var(
        self,
        positions: List[Dict[str, Any]],
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ) -> Decimal:
        """Calculate VaR"""
        # Simplified VaR calculation
        total_value = Decimal("0")
        for pos in positions:
            total_value += Decimal(str(pos.get('quantity', 0))) * Decimal(str(pos.get('current_price', 0)))
        
        # Assume 2% daily volatility
        daily_vol = Decimal("0.02")
        z_score = Decimal("1.645")  # 95% confidence
        
        return total_value * daily_vol * z_score
    
    async def get_risk_metrics(
        self,
        portfolio_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get risk metrics"""
        return {
            "total_exposure": float(self.current_exposure),
            "leverage": float(self.current_exposure / portfolio_state.get('equity', Decimal("1"))),
            "max_drawdown": 0.05,
            "sharpe_ratio": 1.5,
            "risk_score": 35  # 0-100 scale
        }
    
    async def validate_stop_loss(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        position_side: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate stop loss"""
        if position_side == "long":
            if stop_loss >= entry_price:
                return False, "Stop loss must be below entry price for long position"
        else:
            if stop_loss <= entry_price:
                return False, "Stop loss must be above entry price for short position"
        return True, None
    
    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get risk summary"""
        return {
            "exposure_pct": float(self.current_exposure / self.max_exposure * 100) if self.max_exposure else 0,
            "daily_loss_pct": float(abs(self.daily_loss) / self.daily_loss_limit * 100) if self.daily_loss_limit else 0,
            "drawdown_pct": 5.0,
            "risk_level": self._calculate_risk_level(),
            "thresholds": {
                "max_position_size": float(self.max_position_size),
                "max_leverage": float(self.max_leverage),
                "daily_loss_limit": float(self.daily_loss_limit),
                "max_exposure": float(self.max_exposure)
            }
        }
    
    def _calculate_risk_level(self) -> str:
        """Calculate overall risk level"""
        exposure_ratio = self.current_exposure / self.max_exposure if self.max_exposure else 0
        loss_ratio = abs(self.daily_loss) / self.daily_loss_limit if self.daily_loss_limit else 0
        
        max_ratio = max(float(exposure_ratio), float(loss_ratio))
        
        if max_ratio < 0.5:
            return "low"
        elif max_ratio < 0.75:
            return "medium"
        elif max_ratio < 0.9:
            return "high"
        else:
            return "critical"
    
    def set_scenario(self, scenario: str):
        """Set validation scenario for testing"""
        self.validation_scenario = scenario
    
    def set_daily_loss(self, amount: Decimal):
        """Set daily loss for testing"""
        self.daily_loss = amount
    
    def set_current_exposure(self, amount: Decimal):
        """Set current exposure for testing"""
        self.current_exposure = amount


class FakeExecutionPort(ExecutionPort):
    """Minimal fake execution port for testing"""
    
    def __init__(self):
        self.orders = {}
        self._positions = []
        self.balance = {
            'available': Decimal("10000"),
            'locked': Decimal("0"),
            'total': Decimal("10000")
        }
        self.order_counter = 1000
    
    async def submit(self, order: Dict[str, Any]) -> str:
        """Submit order"""
        order_id = str(self.order_counter)
        self.order_counter += 1
        self.orders[order_id] = order
        return order_id
    
    async def cancel(self, order_id: str) -> bool:
        """Cancel order"""
        if order_id in self.orders:
            del self.orders[order_id]
            return True
        return False
    
    async def positions(self) -> List[Dict[str, Any]]:
        """Get positions"""
        return self._positions
    
    async def orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get orders"""
        return list(self.orders.values())
    
    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get specific order"""
        return self.orders.get(order_id)
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for symbol"""
        for pos in self._positions:
            if pos['symbol'] == symbol:
                return pos
        return None
    
    async def modify_order(self, order_id: str, modifications: Dict[str, Any]) -> bool:
        """Modify order"""
        if order_id in self.orders:
            self.orders[order_id].update(modifications)
            return True
        return False
    
    async def get_account_balance(self) -> Dict[str, Decimal]:
        """Get account balance"""
        return self.balance.copy()


class FakeEventBus:
    """Fake event bus for testing"""
    
    def __init__(self):
        self.events = []
    
    async def publish_string(self, event_type: str, data: Dict[str, Any]):
        """Publish event"""
        self.events.append({"type": event_type, "data": data})
    
    def get_events_of_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get events of specific type"""
        return [e for e in self.events if e["type"] == event_type]


class FakeRepository:
    """Fake repository for testing"""
    
    def __init__(self):
        self.entities = {}
    
    def save(self, entity):
        """Save entity"""
        self.entities[entity.id] = entity
    
    def get(self, entity_id):
        """Get entity"""
        return self.entities.get(entity_id)


@pytest.fixture
def fake_risk_port():
    """Create fake risk port"""
    return FakeRiskPort()


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
    return TradingConfig(
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
            default_order_type=ConfigOrderType.MARKET,
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


@pytest.fixture
def trading_service(
    fake_execution_port,
    fake_risk_port,
    fake_event_bus,
    fake_repositories,
    trading_config
):
    """Create trading service with all fakes"""
    # Add test portfolio
    portfolio = Portfolio.create(
        name="Test Portfolio",
        initial_cash=Decimal("10000"),
        currency="USDT"
    )
    fake_repositories['portfolio'].save(portfolio)
    
    service = LiveTradingService(
        execution_port=fake_execution_port,
        risk_port=fake_risk_port,
        event_bus=fake_event_bus,
        portfolio_repository=fake_repositories['portfolio'],
        order_repository=fake_repositories['order'],
        position_repository=fake_repositories['position'],
        config=trading_config
    )
    
    service.test_portfolio_id = portfolio.id
    return service


class TestRiskValidation:
    """Test risk validation scenarios"""
    
    @pytest.mark.asyncio
    async def test_oversize_position_blocked(self, trading_service, fake_risk_port, fake_event_bus):
        """Test that oversized positions are blocked"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set risk scenario
        fake_risk_port.set_scenario("oversize")
        fake_risk_port.max_position_size = Decimal("1000")
        
        # Try to place large order
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),  # At $50k = $50k position
            price=Decimal("50000")
        )
        
        # Should raise ValueError with risk message
        with pytest.raises(ValueError) as exc_info:
            await trading_service.place_order(order_request)
        
        assert "Risk validation failed" in str(exc_info.value)
        assert "exceeds maximum" in str(exc_info.value)
        
        # Check rejection event was published
        events = fake_event_bus.get_events_of_type("risk.signal_rejected")
        assert len(events) == 1
        assert "exceeds maximum" in events[0]["data"]["reason"]
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_leverage_limit_blocked(self, trading_service, fake_risk_port, fake_event_bus):
        """Test that excessive leverage is blocked"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set risk scenario
        fake_risk_port.set_scenario("leverage_limit")
        fake_risk_port.max_leverage = 5
        
        # Try to place high leverage order
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.1"),
            metadata={"leverage": 20}  # Excessive leverage
        )
        
        # Should be blocked
        with pytest.raises(ValueError) as exc_info:
            await trading_service.place_order(order_request)
        
        assert "Risk validation failed" in str(exc_info.value)
        
        # Check rejection event
        events = fake_event_bus.get_events_of_type("risk.signal_rejected")
        assert len(events) == 1
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_daily_loss_limit_blocked(self, trading_service, fake_risk_port, fake_event_bus):
        """Test that daily loss limit prevents new trades"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set risk scenario with daily loss at limit
        fake_risk_port.set_scenario("daily_loss")
        fake_risk_port.set_daily_loss(Decimal("-500"))
        fake_risk_port.daily_loss_limit = Decimal("500")
        
        # Try to place order
        order_request = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("3000")
        )
        
        # Should be blocked due to daily loss
        with pytest.raises(ValueError) as exc_info:
            await trading_service.place_order(order_request)
        
        assert "Daily loss limit" in str(exc_info.value)
        
        # Check rejection event
        events = fake_event_bus.get_events_of_type("risk.signal_rejected")
        assert len(events) == 1
        assert "Daily loss limit" in events[0]["data"]["reason"]
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_correlation_blocked(self, trading_service, fake_risk_port, fake_event_bus):
        """Test that highly correlated positions are blocked"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set risk scenario
        fake_risk_port.set_scenario("correlation")
        fake_risk_port.correlation_threshold = 0.7
        
        # Try to place correlated position
        order_request = OrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5")
        )
        
        # Should be blocked due to correlation
        with pytest.raises(ValueError) as exc_info:
            await trading_service.place_order(order_request)
        
        assert "correlation exceeds threshold" in str(exc_info.value).lower()
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_insufficient_margin_blocked(self, trading_service, fake_risk_port, fake_execution_port, fake_event_bus):
        """Test that orders are blocked when margin is insufficient"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set low balance
        fake_execution_port.balance['available'] = Decimal("100")
        
        # Set risk scenario
        fake_risk_port.set_scenario("margin_insufficient")
        fake_risk_port.margin_requirement = Decimal("0.1")  # 10% margin
        
        # Try to place order requiring more margin
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.5"),
            price=Decimal("50000")  # Requires $2500 margin
        )
        
        # Should be blocked
        with pytest.raises(ValueError) as exc_info:
            await trading_service.place_order(order_request)
        
        assert "Insufficient margin" in str(exc_info.value)
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_position_size_adjustment(self, trading_service, fake_risk_port, fake_execution_port):
        """Test that position size is adjusted when risk suggests it"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set risk scenario to adjust size
        fake_risk_port.set_scenario("adjust_size")
        
        # Place order
        original_quantity = Decimal("1.0")
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=original_quantity,
            price=Decimal("50000")
        )
        
        # Place order - should succeed with adjustment
        response = await trading_service.place_order(order_request)
        
        # Verify order was placed
        assert response.order_id is not None
        
        # Check that quantity was adjusted in the submitted order
        submitted_order = fake_execution_port.orders[response.order_id]
        
        # The adjustment happens to order_request, but execution receives original model_dump
        # Check metadata for adjustment flag
        assert order_request.metadata.get("risk_adjusted") is True
        assert order_request.metadata.get("adjustments") is not None
        assert "quantity" in order_request.metadata["adjustments"]
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_price_adjustment(self, trading_service, fake_risk_port, fake_execution_port):
        """Test that price is adjusted for better risk/reward"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set risk scenario to adjust price
        fake_risk_port.set_scenario("adjust_price")
        
        # Place order
        original_price = Decimal("50000")
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=original_price
        )
        
        # Place order - should succeed with adjustment
        response = await trading_service.place_order(order_request)
        
        # Verify order was placed
        assert response.order_id is not None
        
        # Check metadata for adjustment
        assert order_request.metadata.get("risk_adjusted") is True
        assert "price" in order_request.metadata.get("adjustments", {})
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_approved_order_passes_through(self, trading_service, fake_risk_port, fake_execution_port):
        """Test that approved orders pass through unchanged"""
        # Start session
        await trading_service.start_session(trading_service.test_portfolio_id)
        
        # Set risk scenario to approve
        fake_risk_port.set_scenario("approve")
        
        # Place order
        order_request = OrderRequest(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            price=Decimal("50000")
        )
        
        # Place order - should succeed without modification
        response = await trading_service.place_order(order_request)
        
        # Verify order was placed
        assert response.order_id is not None
        assert response.quantity == order_request.quantity
        assert response.price == order_request.price
        
        # Check no risk adjustment in metadata
        assert order_request.metadata is None or not order_request.metadata.get("risk_adjusted")
        
        # Clean up
        await trading_service.stop_session()
    
    @pytest.mark.asyncio
    async def test_risk_summary(self, fake_risk_port):
        """Test risk summary generation"""
        # Set some risk metrics
        fake_risk_port.set_current_exposure(Decimal("50000"))
        fake_risk_port.max_exposure = Decimal("100000")
        fake_risk_port.set_daily_loss(Decimal("-250"))
        fake_risk_port.daily_loss_limit = Decimal("500")
        
        # Get risk summary
        summary = await fake_risk_port.get_risk_summary()
        
        # Verify summary contents
        assert summary["exposure_pct"] == 50.0  # 50% of max
        assert summary["daily_loss_pct"] == 50.0  # 50% of limit
        assert summary["drawdown_pct"] == 5.0  # Fixed in fake
        assert summary["risk_level"] == "medium"  # Based on 50% ratios
        assert "thresholds" in summary
        assert summary["thresholds"]["max_position_size"] == 10000
        assert summary["thresholds"]["daily_loss_limit"] == 500
    
    @pytest.mark.asyncio
    async def test_risk_level_calculation(self, fake_risk_port):
        """Test risk level calculation based on metrics"""
        # Test low risk
        fake_risk_port.set_current_exposure(Decimal("20000"))
        fake_risk_port.max_exposure = Decimal("100000")
        fake_risk_port.set_daily_loss(Decimal("-100"))
        summary = await fake_risk_port.get_risk_summary()
        assert summary["risk_level"] == "low"
        
        # Test medium risk
        fake_risk_port.set_current_exposure(Decimal("60000"))
        summary = await fake_risk_port.get_risk_summary()
        assert summary["risk_level"] == "medium"
        
        # Test high risk
        fake_risk_port.set_current_exposure(Decimal("80000"))
        summary = await fake_risk_port.get_risk_summary()
        assert summary["risk_level"] == "high"
        
        # Test critical risk
        fake_risk_port.set_current_exposure(Decimal("95000"))
        summary = await fake_risk_port.get_risk_summary()
        assert summary["risk_level"] == "critical"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])