"""
Unit tests for domain ports

Tests that verify port interfaces can be implemented
and that fake adapters work correctly with method signatures.
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, AsyncIterator
import pandas as pd
import pytest

from src.domain.shared.ports import (
    MarketDataPort,
    IndicatorPort,
    StrategyRegistryPort,
    StrategyStatus,
    BacktestPort,
    ExecutionPort,
    RiskPort,
    RiskAction,
    TelemetryPort
)


# Fake Adapters for Testing

class FakeMarketDataAdapter(MarketDataPort):
    """Fake implementation of MarketDataPort for testing"""
    
    async def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return fake kline data"""
        return [
            {
                "timestamp": start_time,
                "open": Decimal("50000"),
                "high": Decimal("51000"),
                "low": Decimal("49000"),
                "close": Decimal("50500"),
                "volume": Decimal("100")
            }
        ]
    
    async def stream_ticks(
        self,
        symbol: str,
        interval: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream fake tick data"""
        for i in range(3):
            yield {
                "symbol": symbol,
                "price": Decimal("50000") + Decimal(i * 100),
                "timestamp": datetime.now()
            }
    
    async def latest_freshness(
        self,
        symbol: str,
        interval: str
    ) -> timedelta:
        """Return fake freshness"""
        return timedelta(seconds=5)
    
    async def get_current_price(
        self,
        symbol: str
    ) -> Decimal:
        """Return fake current price"""
        return Decimal("50000")


class FakeIndicatorAdapter(IndicatorPort):
    """Fake implementation of IndicatorPort for testing"""
    
    def atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """Return fake ATR series"""
        return pd.Series([100.0] * len(close))
    
    def macd(
        self,
        close: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, pd.Series]:
        """Return fake MACD data"""
        length = len(close)
        return {
            'macd': pd.Series([0.5] * length),
            'signal': pd.Series([0.3] * length),
            'histogram': pd.Series([0.2] * length)
        }
    
    def rsi(
        self,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """Return fake RSI series"""
        return pd.Series([50.0] * len(close))
    
    async def compute_batch(
        self,
        symbol: str,
        interval: str,
        since: datetime,
        indicators: List[str]
    ) -> Dict[str, pd.Series]:
        """Compute fake batch indicators"""
        return {
            ind: pd.Series([50.0] * 100)
            for ind in indicators
        }
    
    def sma(
        self,
        close: pd.Series,
        period: int
    ) -> pd.Series:
        """Return fake SMA series"""
        return pd.Series([50000.0] * len(close))
    
    def ema(
        self,
        close: pd.Series,
        period: int
    ) -> pd.Series:
        """Return fake EMA series"""
        return pd.Series([50000.0] * len(close))
    
    def bollinger_bands(
        self,
        close: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, pd.Series]:
        """Return fake Bollinger Bands"""
        length = len(close)
        return {
            'upper': pd.Series([51000.0] * length),
            'middle': pd.Series([50000.0] * length),
            'lower': pd.Series([49000.0] * length)
        }


class FakeStrategyRegistryAdapter(StrategyRegistryPort):
    """Fake implementation of StrategyRegistryPort for testing"""
    
    def __init__(self):
        self.strategies = {}
    
    async def list(self) -> List[Dict[str, Any]]:
        """List fake strategies"""
        return list(self.strategies.values())
    
    async def get(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Get fake strategy"""
        return self.strategies.get(strategy_id)
    
    async def publish(self, config: Dict[str, Any]) -> str:
        """Publish fake strategy"""
        strategy_id = f"strategy_{len(self.strategies) + 1}"
        self.strategies[strategy_id] = {**config, "id": strategy_id}
        return strategy_id
    
    async def set_status(
        self,
        strategy_id: str,
        status: StrategyStatus
    ) -> bool:
        """Set fake strategy status"""
        if strategy_id in self.strategies:
            self.strategies[strategy_id]["status"] = status.value
            return True
        return False
    
    async def update_config(
        self,
        strategy_id: str,
        config: Dict[str, Any]
    ) -> bool:
        """Update fake strategy config"""
        if strategy_id in self.strategies:
            self.strategies[strategy_id].update(config)
            return True
        return False
    
    async def delete(self, strategy_id: str) -> bool:
        """Delete fake strategy"""
        if strategy_id in self.strategies:
            del self.strategies[strategy_id]
            return True
        return False


class FakeBacktestAdapter(BacktestPort):
    """Fake implementation of BacktestPort for testing"""
    
    async def run(self, input_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run fake backtest"""
        return {
            "metrics": {
                "total_return": 10.5,
                "annualized_return": 25.0,
                "max_drawdown": 5.0,
                "sharpe_ratio": 1.5,
                "total_trades": 100,
                "winning_trades": 60,
                "losing_trades": 40,
                "win_rate": 60.0,
                "avg_win": 2.0,
                "avg_loss": 1.0,
                "profit_factor": 1.5,
                "expectancy": 0.5,
                "final_equity": 11050.0,
                "peak_equity": 11500.0,
                "total_commission": 100.0,
                "total_slippage": 50.0,
                "time_in_market": 80.0
            },
            "metrics_json": "{}",
            "equity_csv": "timestamp,equity\n",
            "trades_csv": "id,symbol,side\n",
            "html_report": "<html></html>",
            "trades": [],
            "equity_curve": [],
            "drawdown_curve": [],
            "data_points": 1000,
            "warnings": []
        }
    
    async def validate_config(
        self,
        config: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate fake config"""
        if "symbol" not in config:
            return False, "Symbol is required"
        return True, None
    
    async def estimate_duration(
        self,
        config: Dict[str, Any]
    ) -> float:
        """Estimate fake duration"""
        return 10.0
    
    async def get_available_data_range(
        self,
        symbol: str,
        interval: str
    ) -> tuple[datetime, datetime]:
        """Get fake data range"""
        end = datetime.now()
        start = end - timedelta(days=365)
        return start, end


class FakeExecutionAdapter(ExecutionPort):
    """Fake implementation of ExecutionPort for testing"""
    
    def __init__(self):
        self.orders = {}
        self.positions = {}
    
    async def submit(self, order: Dict[str, Any]) -> str:
        """Submit fake order"""
        order_id = f"order_{len(self.orders) + 1}"
        self.orders[order_id] = {**order, "id": order_id, "status": "pending"}
        return order_id
    
    async def cancel(self, order_id: str) -> bool:
        """Cancel fake order"""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "cancelled"
            return True
        return False
    
    async def positions(self) -> List[Dict[str, Any]]:
        """Get fake positions"""
        return list(self.positions.values())
    
    async def orders(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get fake orders"""
        orders = list(self.orders.values())
        if status:
            orders = [o for o in orders if o.get("status") == status]
        return orders
    
    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get fake order"""
        return self.orders.get(order_id)
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get fake position"""
        return self.positions.get(symbol)
    
    async def modify_order(
        self,
        order_id: str,
        modifications: Dict[str, Any]
    ) -> bool:
        """Modify fake order"""
        if order_id in self.orders:
            self.orders[order_id].update(modifications)
            return True
        return False
    
    async def get_account_balance(self) -> Dict[str, Decimal]:
        """Get fake balance"""
        return {
            "available": Decimal("10000"),
            "locked": Decimal("1000"),
            "total": Decimal("11000")
        }


class FakeRiskAdapter(RiskPort):
    """Fake implementation of RiskPort for testing"""
    
    async def validate_trade(
        self,
        order: Dict[str, Any],
        portfolio_state: Dict[str, Any]
    ) -> tuple[RiskAction, str, Optional[Dict[str, Any]]]:
        """Validate fake trade"""
        # Simple validation: block if order quantity > 1000
        if order.get("quantity", 0) > 1000:
            return RiskAction.BLOCK, "Order size too large", None
        elif order.get("quantity", 0) > 500:
            return RiskAction.ADJUST, "Order size adjusted", {"quantity": 500}
        return RiskAction.ALLOW, "Trade allowed", None
    
    async def calculate_position_size(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Optional[Decimal],
        portfolio_value: Decimal,
        risk_per_trade: Decimal
    ) -> Decimal:
        """Calculate fake position size"""
        return Decimal("100")
    
    async def check_exposure_limits(
        self,
        portfolio_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check fake exposure limits"""
        return {
            "total_exposure": Decimal("5000"),
            "limit": Decimal("10000"),
            "within_limits": True
        }
    
    async def calculate_var(
        self,
        positions: List[Dict[str, Any]],
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ) -> Decimal:
        """Calculate fake VaR"""
        return Decimal("500")
    
    async def get_risk_metrics(
        self,
        portfolio_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get fake risk metrics"""
        return {
            "total_exposure": Decimal("5000"),
            "leverage": Decimal("2"),
            "max_drawdown": Decimal("10"),
            "sharpe_ratio": Decimal("1.5"),
            "risk_score": 5
        }
    
    async def validate_stop_loss(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        position_side: str
    ) -> tuple[bool, Optional[str]]:
        """Validate fake stop loss"""
        if position_side == "long" and stop_loss >= entry_price:
            return False, "Stop loss must be below entry for long position"
        if position_side == "short" and stop_loss <= entry_price:
            return False, "Stop loss must be above entry for short position"
        return True, None


class FakeTelemetryAdapter(TelemetryPort):
    """Fake implementation of TelemetryPort for testing"""
    
    def __init__(self):
        self.metrics = []
        self.events = []
        self.spans = {}
    
    def emit_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Emit fake metric"""
        self.metrics.append({
            "name": name,
            "value": value,
            "labels": labels or {},
            "timestamp": timestamp or datetime.now()
        })
    
    def emit_event(
        self,
        name: str,
        payload: Dict[str, Any],
        severity: str = "info",
        timestamp: Optional[datetime] = None
    ) -> None:
        """Emit fake event"""
        self.events.append({
            "name": name,
            "payload": payload,
            "severity": severity,
            "timestamp": timestamp or datetime.now()
        })
    
    def emit_trace(
        self,
        span_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None
    ) -> str:
        """Start fake trace span"""
        span_id = f"span_{len(self.spans) + 1}"
        self.spans[span_id] = {
            "name": span_name,
            "attributes": attributes or {},
            "parent": parent_span_id,
            "status": "running"
        }
        return span_id
    
    def end_trace(
        self,
        span_id: str,
        status: str = "ok",
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """End fake trace span"""
        if span_id in self.spans:
            self.spans[span_id]["status"] = status
            if attributes:
                self.spans[span_id]["attributes"].update(attributes)
    
    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment fake counter"""
        self.emit_metric(name, value, labels)
    
    def record_histogram(
        self,
        name: str,
        value: float,
        buckets: Optional[list[float]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record fake histogram"""
        self.emit_metric(f"{name}_histogram", value, labels)
    
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set fake gauge"""
        self.emit_metric(f"{name}_gauge", value, labels)


# Test Cases

class TestMarketDataPort:
    """Test MarketDataPort interface"""
    
    @pytest.mark.asyncio
    async def test_fetch_klines(self):
        """Test fetching klines"""
        adapter = FakeMarketDataAdapter()
        klines = await adapter.fetch_klines(
            symbol="BTCUSDT",
            interval="1h",
            start_time=datetime.now() - timedelta(days=1)
        )
        assert len(klines) > 0
        assert "open" in klines[0]
        assert "close" in klines[0]
    
    @pytest.mark.asyncio
    async def test_stream_ticks(self):
        """Test streaming ticks"""
        adapter = FakeMarketDataAdapter()
        ticks = []
        async for tick in adapter.stream_ticks("BTCUSDT", "1s"):
            ticks.append(tick)
        assert len(ticks) == 3
        assert "price" in ticks[0]
    
    @pytest.mark.asyncio
    async def test_latest_freshness(self):
        """Test data freshness"""
        adapter = FakeMarketDataAdapter()
        freshness = await adapter.latest_freshness("BTCUSDT", "1h")
        assert isinstance(freshness, timedelta)
    
    @pytest.mark.asyncio
    async def test_get_current_price(self):
        """Test getting current price"""
        adapter = FakeMarketDataAdapter()
        price = await adapter.get_current_price("BTCUSDT")
        assert isinstance(price, Decimal)
        assert price > 0


class TestIndicatorPort:
    """Test IndicatorPort interface"""
    
    def test_atr(self):
        """Test ATR calculation"""
        adapter = FakeIndicatorAdapter()
        data = pd.Series([50000] * 100)
        atr = adapter.atr(data, data, data)
        assert len(atr) == len(data)
    
    def test_macd(self):
        """Test MACD calculation"""
        adapter = FakeIndicatorAdapter()
        data = pd.Series([50000] * 100)
        macd = adapter.macd(data)
        assert "macd" in macd
        assert "signal" in macd
        assert "histogram" in macd
    
    def test_rsi(self):
        """Test RSI calculation"""
        adapter = FakeIndicatorAdapter()
        data = pd.Series([50000] * 100)
        rsi = adapter.rsi(data)
        assert len(rsi) == len(data)
    
    @pytest.mark.asyncio
    async def test_compute_batch(self):
        """Test batch indicator computation"""
        adapter = FakeIndicatorAdapter()
        indicators = await adapter.compute_batch(
            symbol="BTCUSDT",
            interval="1h",
            since=datetime.now() - timedelta(days=1),
            indicators=["rsi", "macd", "sma"]
        )
        assert len(indicators) == 3
        assert "rsi" in indicators


class TestStrategyRegistryPort:
    """Test StrategyRegistryPort interface"""
    
    @pytest.mark.asyncio
    async def test_publish_and_get(self):
        """Test publishing and getting strategy"""
        adapter = FakeStrategyRegistryAdapter()
        
        config = {"name": "TestStrategy", "params": {}}
        strategy_id = await adapter.publish(config)
        assert strategy_id is not None
        
        strategy = await adapter.get(strategy_id)
        assert strategy is not None
        assert strategy["name"] == "TestStrategy"
    
    @pytest.mark.asyncio
    async def test_set_status(self):
        """Test setting strategy status"""
        adapter = FakeStrategyRegistryAdapter()
        
        strategy_id = await adapter.publish({"name": "Test"})
        success = await adapter.set_status(strategy_id, StrategyStatus.RUNNING)
        assert success
        
        strategy = await adapter.get(strategy_id)
        assert strategy["status"] == "running"
    
    @pytest.mark.asyncio
    async def test_list_strategies(self):
        """Test listing strategies"""
        adapter = FakeStrategyRegistryAdapter()
        
        await adapter.publish({"name": "Strategy1"})
        await adapter.publish({"name": "Strategy2"})
        
        strategies = await adapter.list()
        assert len(strategies) == 2


class TestBacktestPort:
    """Test BacktestPort interface"""
    
    @pytest.mark.asyncio
    async def test_run_backtest(self):
        """Test running backtest"""
        adapter = FakeBacktestAdapter()
        
        config = {
            "symbol": "BTCUSDT",
            "strategy": "SMA",
            "start_date": datetime.now() - timedelta(days=30),
            "end_date": datetime.now()
        }
        
        result = await adapter.run(config)
        assert "metrics" in result
        assert "metrics_json" in result
        assert result["metrics"]["total_trades"] == 100
    
    @pytest.mark.asyncio
    async def test_validate_config(self):
        """Test config validation"""
        adapter = FakeBacktestAdapter()
        
        valid, error = await adapter.validate_config({"symbol": "BTCUSDT"})
        assert valid
        assert error is None
        
        valid, error = await adapter.validate_config({})
        assert not valid
        assert error is not None


class TestExecutionPort:
    """Test ExecutionPort interface"""
    
    @pytest.mark.asyncio
    async def test_submit_order(self):
        """Test order submission"""
        adapter = FakeExecutionAdapter()
        
        order = {
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": 100,
            "type": "market"
        }
        
        order_id = await adapter.submit(order)
        assert order_id is not None
        
        retrieved = await adapter.get_order(order_id)
        assert retrieved is not None
        assert retrieved["symbol"] == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_cancel_order(self):
        """Test order cancellation"""
        adapter = FakeExecutionAdapter()
        
        order_id = await adapter.submit({"symbol": "BTCUSDT"})
        success = await adapter.cancel(order_id)
        assert success
        
        order = await adapter.get_order(order_id)
        assert order["status"] == "cancelled"


class TestRiskPort:
    """Test RiskPort interface"""
    
    @pytest.mark.asyncio
    async def test_validate_trade(self):
        """Test trade validation"""
        adapter = FakeRiskAdapter()
        
        # Test allow
        action, reason, adj = await adapter.validate_trade(
            {"quantity": 100},
            {}
        )
        assert action == RiskAction.ALLOW
        
        # Test adjust
        action, reason, adj = await adapter.validate_trade(
            {"quantity": 600},
            {}
        )
        assert action == RiskAction.ADJUST
        assert adj is not None
        
        # Test block
        action, reason, adj = await adapter.validate_trade(
            {"quantity": 1500},
            {}
        )
        assert action == RiskAction.BLOCK
    
    @pytest.mark.asyncio
    async def test_validate_stop_loss(self):
        """Test stop loss validation"""
        adapter = FakeRiskAdapter()
        
        valid, error = await adapter.validate_stop_loss(
            "BTCUSDT",
            Decimal("50000"),
            Decimal("49000"),
            "long"
        )
        assert valid
        
        valid, error = await adapter.validate_stop_loss(
            "BTCUSDT",
            Decimal("50000"),
            Decimal("51000"),
            "long"
        )
        assert not valid


class TestTelemetryPort:
    """Test TelemetryPort interface"""
    
    def test_emit_metric(self):
        """Test metric emission"""
        adapter = FakeTelemetryAdapter()
        
        adapter.emit_metric("test.metric", 100, {"label": "value"})
        assert len(adapter.metrics) == 1
        assert adapter.metrics[0]["name"] == "test.metric"
    
    def test_emit_trace(self):
        """Test trace emission"""
        adapter = FakeTelemetryAdapter()
        
        span_id = adapter.emit_trace("test.span", {"attr": "value"})
        assert span_id in adapter.spans
        
        adapter.end_trace(span_id, "ok")
        assert adapter.spans[span_id]["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])