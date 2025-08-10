"""
End-to-end tests using replay adapter for deterministic testing.

These tests ensure that the trading system produces identical results
when run with the same recorded market data.
"""

import pytest
import asyncio
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta
from decimal import Decimal
import tempfile

from src.domain.ports.market_data_port import MarketDataConfig, TimeFrame
from src.infrastructure.market_data.replay_adapter import ReplayAdapter
from src.infrastructure.config.feature_flags import FeatureFlagManager
from src.infrastructure.exchange.adapter_factory import get_adapter_factory
from src.infrastructure.strategy.strategy_registry import StrategyRegistry
from src.application.services.trading_service import TradingService
from src.infrastructure.monitoring.metrics_collector import MetricsCollector


class DeterministicTestFramework:
    """
    Framework for running deterministic e2e tests with replay data.
    
    Ensures identical metrics across multiple runs.
    """
    
    def __init__(self, replay_data_path: str = "data/replay/test"):
        self.replay_data_path = Path(replay_data_path)
        self.replay_adapter = ReplayAdapter(str(self.replay_data_path))
        self.metrics_collector = MetricsCollector()
        self.results: List[Dict[str, Any]] = []
    
    async def setup(self, symbols: List[str], timeframes: List[TimeFrame]):
        """Setup test environment."""
        # Configure replay adapter for deterministic mode
        config = MarketDataConfig(
            symbols=symbols,
            timeframes=timeframes,
            deterministic=True,  # Critical for determinism
            replay_speed=0  # As fast as possible
        )
        
        # Connect replay adapter
        connected = await self.replay_adapter.connect(config)
        if not connected:
            raise RuntimeError("Failed to connect replay adapter")
        
        # Configure feature flags for paper trading
        self.feature_flags = FeatureFlagManager(environment="test")
        self.feature_flags.set("EXECUTION_IMPL", "paper")
        
        # Get execution adapter
        self.factory = get_adapter_factory()
        self.execution_adapter = await self.factory.get_adapter()
        
        # Initialize strategy registry
        self.strategy_registry = StrategyRegistry()
        
        # Create trading service
        self.trading_service = TradingService(
            market_data_port=self.replay_adapter,
            execution_adapter=self.execution_adapter,
            strategy_registry=self.strategy_registry,
            metrics_collector=self.metrics_collector
        )
    
    async def run_test(
        self,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        test_duration: timedelta
    ) -> Dict[str, Any]:
        """
        Run a single test with recorded data.
        
        Args:
            strategy_name: Strategy to test
            strategy_params: Strategy parameters
            test_duration: Test duration
            
        Returns:
            Test results and metrics
        """
        # Reset metrics
        self.metrics_collector.reset()
        
        # Configure strategy
        strategy = self.strategy_registry.get_strategy(strategy_name)
        strategy.configure(**strategy_params)
        
        # Activate strategy
        self.trading_service.activate_strategy(strategy_name)
        
        # Get start and end time from replay data
        start_time = self.replay_adapter.replay_state.start_time
        end_time = min(
            start_time + test_duration,
            self.replay_adapter.replay_state.end_time
        )
        
        # Run simulation
        current_time = start_time
        tick_count = 0
        
        while current_time < end_time:
            # Advance replay to current time
            self.replay_adapter.advance_to_time(current_time)
            
            # Process tick data
            symbols = self.replay_adapter.config.symbols
            for symbol in symbols:
                tick = await self.replay_adapter.get_tick(symbol)
                if tick:
                    # Feed to trading service
                    await self.trading_service.process_tick(tick)
                    tick_count += 1
            
            # Process kline data
            for symbol in symbols:
                for timeframe in self.replay_adapter.config.timeframes:
                    kline = await self.replay_adapter.get_kline(symbol, timeframe)
                    if kline:
                        await self.trading_service.process_kline(kline)
            
            # Advance time
            current_time += timedelta(seconds=1)
            
            # Allow async operations to complete
            await asyncio.sleep(0)
        
        # Deactivate strategy
        self.trading_service.deactivate_strategy(strategy_name)
        
        # Collect metrics
        metrics = await self._collect_metrics()
        
        # Create result
        result = {
            "test_id": self._generate_test_id(strategy_name, strategy_params),
            "strategy": strategy_name,
            "params": strategy_params,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "tick_count": tick_count,
            "metrics": metrics,
            "metrics_hash": self._hash_metrics(metrics)
        }
        
        self.results.append(result)
        
        return result
    
    async def run_multiple_iterations(
        self,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        test_duration: timedelta,
        iterations: int = 3
    ) -> bool:
        """
        Run test multiple times to verify determinism.
        
        Args:
            strategy_name: Strategy to test
            strategy_params: Strategy parameters
            test_duration: Test duration
            iterations: Number of iterations
            
        Returns:
            True if all iterations produce identical results
        """
        hashes = []
        
        for i in range(iterations):
            # Reset everything
            await self.teardown()
            await self.setup(
                symbols=["BTCUSDT", "ETHUSDT"],
                timeframes=[TimeFrame.M1, TimeFrame.M5]
            )
            
            # Run test
            result = await self.run_test(
                strategy_name,
                strategy_params,
                test_duration
            )
            
            hashes.append(result["metrics_hash"])
            
            print(f"Iteration {i+1}: hash={result['metrics_hash']}")
        
        # Check if all hashes are identical
        deterministic = len(set(hashes)) == 1
        
        if deterministic:
            print(f"✓ Test is deterministic: all {iterations} iterations produced identical results")
        else:
            print(f"✗ Test is NOT deterministic: got {len(set(hashes))} different results")
            print(f"  Hashes: {hashes}")
        
        return deterministic
    
    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive metrics."""
        metrics = {
            # Performance metrics
            "total_pnl": float(self.metrics_collector.get_metric("total_pnl")),
            "win_rate": float(self.metrics_collector.get_metric("win_rate")),
            "sharpe_ratio": float(self.metrics_collector.get_metric("sharpe_ratio")),
            "max_drawdown": float(self.metrics_collector.get_metric("max_drawdown")),
            
            # Trade metrics
            "total_trades": int(self.metrics_collector.get_metric("total_trades")),
            "winning_trades": int(self.metrics_collector.get_metric("winning_trades")),
            "losing_trades": int(self.metrics_collector.get_metric("losing_trades")),
            "average_win": float(self.metrics_collector.get_metric("average_win")),
            "average_loss": float(self.metrics_collector.get_metric("average_loss")),
            
            # Risk metrics
            "max_exposure": float(self.metrics_collector.get_metric("max_exposure")),
            "average_exposure": float(self.metrics_collector.get_metric("average_exposure")),
            "risk_adjusted_return": float(self.metrics_collector.get_metric("risk_adjusted_return")),
            
            # Execution metrics
            "average_fill_time": float(self.metrics_collector.get_metric("average_fill_time")),
            "slippage": float(self.metrics_collector.get_metric("slippage")),
            "commission_paid": float(self.metrics_collector.get_metric("commission_paid")),
            
            # Account metrics
            "final_balance": float(self.execution_adapter.get_account_info().await.equity),
            "peak_balance": float(self.metrics_collector.get_metric("peak_balance")),
            "lowest_balance": float(self.metrics_collector.get_metric("lowest_balance"))
        }
        
        return metrics
    
    def _hash_metrics(self, metrics: Dict[str, Any]) -> str:
        """Create deterministic hash of metrics."""
        # Sort keys for consistent ordering
        sorted_metrics = json.dumps(metrics, sort_keys=True)
        
        # Create hash
        return hashlib.sha256(sorted_metrics.encode()).hexdigest()[:16]
    
    def _generate_test_id(self, strategy: str, params: Dict[str, Any]) -> str:
        """Generate unique test ID."""
        params_str = json.dumps(params, sort_keys=True)
        return f"{strategy}_{hashlib.md5(params_str.encode()).hexdigest()[:8]}"
    
    async def save_results(self, output_path: str = "test_results"):
        """Save test results to file."""
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = output_dir / f"replay_test_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"Results saved to {results_file}")
        
        # Save metrics.json for comparison
        if self.results:
            latest_metrics = self.results[-1]["metrics"]
            metrics_file = output_dir / "metrics.json"
            
            with open(metrics_file, 'w') as f:
                json.dump(latest_metrics, f, indent=2)
            
            print(f"Metrics saved to {metrics_file}")
    
    async def teardown(self):
        """Cleanup test environment."""
        await self.replay_adapter.disconnect()
        await self.factory.cleanup()


@pytest.mark.e2e
class TestDeterministicReplay:
    """E2E tests using replay data."""
    
    @pytest.fixture
    async def framework(self):
        """Create test framework."""
        framework = DeterministicTestFramework()
        yield framework
        await framework.teardown()
    
    @pytest.mark.asyncio
    async def test_sma_strategy_determinism(self, framework):
        """Test SMA strategy produces deterministic results."""
        await framework.setup(
            symbols=["BTCUSDT"],
            timeframes=[TimeFrame.M5]
        )
        
        # Test parameters
        strategy_params = {
            "fast_period": 10,
            "slow_period": 20,
            "position_size": 0.1
        }
        
        # Run multiple iterations
        deterministic = await framework.run_multiple_iterations(
            "SMAStrategy",
            strategy_params,
            timedelta(hours=1),
            iterations=3
        )
        
        assert deterministic, "SMA strategy should produce deterministic results"
        
        # Save results
        await framework.save_results()
    
    @pytest.mark.asyncio
    async def test_rsi_strategy_determinism(self, framework):
        """Test RSI strategy produces deterministic results."""
        await framework.setup(
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=[TimeFrame.M15]
        )
        
        # Test parameters
        strategy_params = {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "position_size": 0.05
        }
        
        # Run multiple iterations
        deterministic = await framework.run_multiple_iterations(
            "RSIStrategy",
            strategy_params,
            timedelta(hours=2),
            iterations=3
        )
        
        assert deterministic, "RSI strategy should produce deterministic results"
    
    @pytest.mark.asyncio
    async def test_identical_metrics_across_runs(self, framework):
        """Test that metrics.json is identical across runs."""
        await framework.setup(
            symbols=["BTCUSDT"],
            timeframes=[TimeFrame.M1]
        )
        
        strategy_params = {
            "threshold": 0.01,
            "position_size": 0.2
        }
        
        # Run first test
        result1 = await framework.run_test(
            "MomentumStrategy",
            strategy_params,
            timedelta(minutes=30)
        )
        
        metrics1 = result1["metrics"]
        
        # Reset and run again
        await framework.teardown()
        await framework.setup(
            symbols=["BTCUSDT"],
            timeframes=[TimeFrame.M1]
        )
        
        result2 = await framework.run_test(
            "MomentumStrategy",
            strategy_params,
            timedelta(minutes=30)
        )
        
        metrics2 = result2["metrics"]
        
        # Compare metrics
        assert metrics1 == metrics2, "Metrics should be identical across runs"
        
        # Verify specific values
        assert metrics1["total_trades"] == metrics2["total_trades"]
        assert metrics1["total_pnl"] == metrics2["total_pnl"]
        assert metrics1["sharpe_ratio"] == metrics2["sharpe_ratio"]
        assert metrics1["max_drawdown"] == metrics2["max_drawdown"]
        
        print(f"✓ Metrics are identical: hash={result1['metrics_hash']}")
    
    @pytest.mark.asyncio
    async def test_replay_speed_modes(self, framework):
        """Test different replay speed modes."""
        # Test deterministic mode (speed=0)
        await framework.setup(
            symbols=["BTCUSDT"],
            timeframes=[TimeFrame.M5]
        )
        
        assert framework.replay_adapter.config.deterministic
        assert framework.replay_adapter.config.replay_speed == 0
        
        # Test should complete quickly
        start = datetime.now()
        
        await framework.run_test(
            "SimpleStrategy",
            {"threshold": 0.005},
            timedelta(hours=1)
        )
        
        elapsed = (datetime.now() - start).total_seconds()
        
        # Should complete in seconds, not real-time
        assert elapsed < 10, f"Deterministic mode should be fast, took {elapsed}s"
    
    @pytest.mark.asyncio
    async def test_multi_symbol_determinism(self, framework):
        """Test determinism with multiple symbols."""
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        
        await framework.setup(
            symbols=symbols,
            timeframes=[TimeFrame.M1, TimeFrame.M5, TimeFrame.M15]
        )
        
        strategy_params = {
            "symbols": symbols,
            "correlation_threshold": 0.7,
            "position_size": 0.03
        }
        
        deterministic = await framework.run_multiple_iterations(
            "MultiSymbolStrategy",
            strategy_params,
            timedelta(hours=1),
            iterations=2
        )
        
        assert deterministic, "Multi-symbol strategy should be deterministic"


@pytest.mark.e2e
class TestReplayDataValidation:
    """Validate replay data integrity."""
    
    @pytest.mark.asyncio
    async def test_data_consistency(self):
        """Test that replay data is consistent."""
        adapter = ReplayAdapter("data/replay/test")
        
        config = MarketDataConfig(
            symbols=["BTCUSDT"],
            timeframes=[TimeFrame.M1],
            deterministic=True
        )
        
        await adapter.connect(config)
        
        # Collect all ticks
        ticks = []
        async for tick in adapter.stream_ticks(["BTCUSDT"]):
            ticks.append(tick)
            if len(ticks) >= 100:
                break
        
        # Verify chronological order
        for i in range(1, len(ticks)):
            assert ticks[i].timestamp >= ticks[i-1].timestamp, \
                "Ticks should be in chronological order"
        
        # Verify price consistency
        for tick in ticks:
            assert tick.bid <= tick.ask, "Bid should be <= ask"
            assert tick.bid > 0 and tick.ask > 0, "Prices should be positive"
        
        await adapter.disconnect()
    
    @pytest.mark.asyncio
    async def test_kline_ohlc_validity(self):
        """Test that kline OHLC data is valid."""
        adapter = ReplayAdapter("data/replay/test")
        
        config = MarketDataConfig(
            symbols=["BTCUSDT"],
            timeframes=[TimeFrame.M5],
            deterministic=True
        )
        
        await adapter.connect(config)
        
        # Get klines
        klines = await adapter.get_klines("BTCUSDT", TimeFrame.M5, limit=50)
        
        for kline in klines:
            # OHLC validity
            assert kline.low <= kline.open <= kline.high
            assert kline.low <= kline.close <= kline.high
            assert kline.low <= kline.high
            
            # Volume and trades
            assert kline.volume >= 0
            assert kline.trades >= 0
        
        await adapter.disconnect()


if __name__ == "__main__":
    # Run deterministic tests
    asyncio.run(main())


async def main():
    """Run e2e tests manually."""
    framework = DeterministicTestFramework()
    
    try:
        # Setup
        await framework.setup(
            symbols=["BTCUSDT"],
            timeframes=[TimeFrame.M5]
        )
        
        # Run test
        print("Running deterministic replay test...")
        
        deterministic = await framework.run_multiple_iterations(
            "SMAStrategy",
            {"fast_period": 10, "slow_period": 20},
            timedelta(minutes=30),
            iterations=3
        )
        
        if deterministic:
            print("✓ Test passed: Results are deterministic")
        else:
            print("✗ Test failed: Results are not deterministic")
        
        # Save results
        await framework.save_results()
        
    finally:
        await framework.teardown()