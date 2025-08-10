"""
Integration tests for execution adapters.

Tests all three implementations and feature flag switching.
"""

import pytest
import asyncio
import os
from decimal import Decimal
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.infrastructure.config.feature_flags import (
    FeatureFlagManager, ExecutionImplementation, Environment
)
from src.infrastructure.exchange.adapter_factory import (
    get_adapter_factory, get_execution_adapter
)
from src.infrastructure.exchange.execution_adapter import OrderStatus
from src.infrastructure.exchange.paper_adapter import PaperTradingAdapter
from src.domain.entities import Order, OrderType, OrderSide
from src.domain.value_objects import Symbol, Price, Quantity


@pytest.fixture
async def factory():
    """Create adapter factory."""
    factory = get_adapter_factory()
    yield factory
    await factory.cleanup()


@pytest.fixture
def feature_flags():
    """Create feature flag manager."""
    return FeatureFlagManager(environment="development")


class TestAdapterFactory:
    """Test adapter factory and routing."""
    
    @pytest.mark.asyncio
    async def test_factory_singleton(self):
        """Test factory is singleton."""
        factory1 = get_adapter_factory()
        factory2 = get_adapter_factory()
        assert factory1 is factory2
    
    @pytest.mark.asyncio
    async def test_get_paper_adapter(self, factory):
        """Test getting paper trading adapter."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            adapter = await get_execution_adapter()
            assert adapter.get_adapter_name() == "paper"
            assert await adapter.is_connected()
    
    @pytest.mark.asyncio
    async def test_adapter_caching(self, factory):
        """Test adapters are cached."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            adapter1 = await factory.get_adapter()
            adapter2 = await factory.get_adapter()
            assert adapter1 is adapter2
    
    @pytest.mark.asyncio
    async def test_feature_flag_switching(self, factory, feature_flags):
        """Test switching adapters via feature flags."""
        # Start with paper
        feature_flags.set("EXECUTION_IMPL", "paper")
        adapter1 = await factory.get_adapter()
        assert adapter1.get_adapter_name() == "paper"
        
        # Switch to v1 (mocked)
        with patch('src.infrastructure.exchange.adapter_factory.BinanceV1Adapter') as MockV1:
            mock_v1 = MagicMock()
            mock_v1.connect.return_value = asyncio.coroutine(lambda: True)()
            mock_v1.get_adapter_name.return_value = "binance_v1"
            mock_v1.is_connected.return_value = asyncio.coroutine(lambda: True)()
            MockV1.return_value = mock_v1
            
            feature_flags.set("EXECUTION_IMPL", "binance_v1")
            factory._current_adapter = None  # Force reload
            
            adapter2 = await factory.get_adapter()
            assert adapter2.get_adapter_name() == "binance_v1"
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, factory):
        """Test health monitoring integration."""
        adapter = await factory.get_adapter()
        health = await factory.get_health_status()
        
        assert "current_adapter" in health
        assert health["current_adapter"] == adapter.get_adapter_name()
        assert "adapters" in health
        assert "feature_flags" in health


class TestPaperAdapter:
    """Test paper trading adapter."""
    
    @pytest.fixture
    async def adapter(self):
        """Create paper adapter."""
        adapter = PaperTradingAdapter(initial_balance=Decimal("10000"))
        await adapter.connect()
        yield adapter
        await adapter.disconnect()
    
    @pytest.mark.asyncio
    async def test_connect_disconnect(self, adapter):
        """Test connection lifecycle."""
        assert await adapter.is_connected()
        
        await adapter.disconnect()
        assert not await adapter.is_connected()
        
        await adapter.connect()
        assert await adapter.is_connected()
    
    @pytest.mark.asyncio
    async def test_place_order(self, adapter):
        """Test order placement."""
        order = Order(
            id="test-order-1",
            symbol=Symbol("BTCUSDT"),
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            quantity=Quantity(Decimal("0.1")),
            price=None,
            status=OrderStatus.NEW,
            created_at=datetime.now()
        )
        
        result = await adapter.place_order(order)
        
        assert result.success
        assert result.order_id
        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == Decimal("0.1")
        assert result.average_price > 0
        assert result.commission > 0
    
    @pytest.mark.asyncio
    async def test_insufficient_balance(self, adapter):
        """Test order rejection on insufficient balance."""
        order = Order(
            id="test-order-2",
            symbol=Symbol("BTCUSDT"),
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            quantity=Quantity(Decimal("1000")),  # Large quantity
            price=None,
            status=OrderStatus.NEW,
            created_at=datetime.now()
        )
        
        result = await adapter.place_order(order)
        
        assert not result.success
        assert result.status == OrderStatus.REJECTED
        assert "Insufficient balance" in result.error_message
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, adapter):
        """Test order cancellation."""
        # Place order
        order = Order(
            id="test-order-3",
            symbol=Symbol("BTCUSDT"),
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            quantity=Quantity(Decimal("0.1")),
            price=Price(Decimal("40000")),
            status=OrderStatus.NEW,
            created_at=datetime.now()
        )
        
        result = await adapter.place_order(order)
        order_id = result.order_id
        
        # Cancel order
        cancelled = await adapter.cancel_order(order_id, "BTCUSDT")
        assert cancelled
        
        # Check status
        status = await adapter.get_order_status(order_id, "BTCUSDT")
        assert status.status == OrderStatus.CANCELED
    
    @pytest.mark.asyncio
    async def test_account_info(self, adapter):
        """Test account information retrieval."""
        info = await adapter.get_account_info()
        
        assert info.balances["USDT"] == Decimal("10000")
        assert info.equity == Decimal("10000") + info.balances.get("BNB", Decimal("0")) * Decimal("500")
        assert info.timestamp
    
    @pytest.mark.asyncio
    async def test_market_data(self, adapter):
        """Test market data retrieval."""
        data = await adapter.get_market_data("BTCUSDT")
        
        assert data.symbol == "BTCUSDT"
        assert data.bid > 0
        assert data.ask > 0
        assert data.last > 0
        assert data.bid < data.ask  # Spread
    
    @pytest.mark.asyncio
    async def test_symbol_info(self, adapter):
        """Test symbol information."""
        info = await adapter.get_symbol_info("BTCUSDT")
        
        assert info.symbol == "BTCUSDT"
        assert info.base_asset == "BTC"
        assert info.quote_asset == "USDT"
        assert info.min_quantity > 0
        assert info.max_quantity > info.min_quantity
    
    @pytest.mark.asyncio
    async def test_precision_map(self, adapter):
        """Test precision map."""
        precision_map = await adapter.get_precision_map()
        
        assert "BTCUSDT" in precision_map
        price_precision, qty_precision = precision_map["BTCUSDT"]
        assert price_precision > 0
        assert qty_precision > 0
    
    @pytest.mark.asyncio
    async def test_health_status(self, adapter):
        """Test health status reporting."""
        health = adapter.get_health_status()
        
        assert health["adapter"] == "paper"
        assert health["connected"]
        assert "total_trades" in health
        assert "total_pnl" in health
    
    @pytest.mark.asyncio
    async def test_reset(self, adapter):
        """Test paper trading reset."""
        # Place some orders
        order = Order(
            id="test-order-4",
            symbol=Symbol("BTCUSDT"),
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            quantity=Quantity(Decimal("0.1")),
            price=None,
            status=OrderStatus.NEW,
            created_at=datetime.now()
        )
        
        await adapter.place_order(order)
        assert adapter.total_trades > 0
        
        # Reset
        adapter.reset()
        
        assert adapter.total_trades == 0
        assert adapter.balances["USDT"] == adapter.initial_balance
        assert len(adapter.orders) == 0


class TestBinanceAdapters:
    """Test Binance v1 and v2 adapters (mocked)."""
    
    @pytest.mark.asyncio
    async def test_v1_connection(self):
        """Test v1 adapter connection."""
        with patch('aiohttp.ClientSession') as MockSession:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json.return_value = asyncio.coroutine(lambda: {})()
            
            mock_session.get.return_value.__aenter__.return_value = mock_response
            MockSession.return_value = mock_session
            
            from src.infrastructure.exchange.binance_v1_adapter import BinanceV1Adapter
            
            adapter = BinanceV1Adapter("test_key", "test_secret", testnet=True)
            connected = await adapter.connect()
            
            assert connected
            assert adapter.get_adapter_name() == "binance_v1"
    
    @pytest.mark.asyncio
    async def test_v2_improvements(self):
        """Test v2 adapter improvements."""
        from src.infrastructure.exchange.binance_v2_adapter import (
            BinanceV2Adapter, RetryConfig, CircuitBreaker, PrecisionMapper
        )
        
        # Test retry config
        retry = RetryConfig(initial_delay=1.0, exponential_base=2.0)
        assert retry.get_delay(0) >= 0.5  # With jitter
        assert retry.get_delay(1) >= 1.0
        assert retry.get_delay(10) == retry.max_delay
        
        # Test circuit breaker
        breaker = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise Exception("Test failure")
        
        # Should fail and open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                breaker.call(failing_func)
        
        assert breaker.state.value == "open"
        
        # Test precision mapper
        mapper = PrecisionMapper()
        mapper.update_cache("BTCUSDT", {
            "step_size": "0.00001",
            "tick_size": "0.01",
            "price_precision": 2,
            "quantity_precision": 5
        })
        
        # Format quantity
        qty = Decimal("1.234567")
        formatted = mapper.format_quantity(qty, "BTCUSDT")
        assert formatted == Decimal("1.23456")  # Rounded down
        
        # Format price
        price = Decimal("50123.456")
        formatted = mapper.format_price(price, "BTCUSDT")
        assert formatted == Decimal("50123.45")  # Rounded to tick


class TestMigration:
    """Test migration process."""
    
    @pytest.mark.asyncio
    async def test_migration_flow(self):
        """Test migration from v1 to v2."""
        from scripts.migrate_to_v2 import AdapterMigration
        
        # Create migration for testnet
        migration = AdapterMigration(Environment.TESTNET)
        
        # Check initial status
        status = migration.get_status()
        assert status["environment"] == "testnet"
        assert status["phase"] in ["not_started", "rolled_back"]
        
        # Would test actual migration with mocked adapters
        # await migration.start_migration()
        # assert migration.migration_state["phase"] == "testnet_deployed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])