"""
Tests for Metrics Infrastructure

Verifies metrics collection, instrumentation, and data freshness monitoring.
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.infrastructure.monitoring.metrics import (
    MetricsRegistry, Counter, Gauge, Histogram, Timer,
    metrics_registry, system_metrics
)
from src.infrastructure.monitoring.freshness_collector import (
    DataFreshnessCollector, MockMarketDataPort
)
from src.infrastructure.monitoring.instrumented_components import (
    InstrumentedMarketDataPort, InstrumentedIndicatorPort,
    InstrumentedBacktestPort, InstrumentedExecutionPort
)


class TestMetricsRegistry:
    """Test metrics registry functionality"""
    
    def test_counter_metrics(self):
        """Test counter metric operations"""
        registry = MetricsRegistry()
        counter = registry.counter(
            'test_counter',
            'Test counter metric',
            labels=['method', 'status']
        )
        
        # Increment counter
        counter.inc(labels={'method': 'GET', 'status': '200'})
        counter.inc(labels={'method': 'GET', 'status': '200'})
        counter.inc(labels={'method': 'POST', 'status': '201'})
        
        # Check values
        assert counter.get_value({'method': 'GET', 'status': '200'}) == 2
        assert counter.get_value({'method': 'POST', 'status': '201'}) == 1
        assert counter.get_value({'method': 'DELETE', 'status': '404'}) == 0
        
        # Test that counter can't decrease
        with pytest.raises(ValueError):
            counter.inc(-1)
    
    def test_gauge_metrics(self):
        """Test gauge metric operations"""
        registry = MetricsRegistry()
        gauge = registry.gauge(
            'test_gauge',
            'Test gauge metric',
            labels=['queue']
        )
        
        # Set gauge value
        gauge.set(10, labels={'queue': 'orders'})
        assert gauge.get_value({'queue': 'orders'}) == 10
        
        # Increment and decrement
        gauge.inc(5, labels={'queue': 'orders'})
        assert gauge.get_value({'queue': 'orders'}) == 15
        
        gauge.dec(3, labels={'queue': 'orders'})
        assert gauge.get_value({'queue': 'orders'}) == 12
    
    def test_histogram_metrics(self):
        """Test histogram metric operations"""
        registry = MetricsRegistry()
        histogram = registry.histogram(
            'test_latency',
            'Test latency histogram',
            labels=['endpoint'],
            buckets=[0.1, 0.5, 1.0, 5.0]
        )
        
        # Record observations
        labels = {'endpoint': '/api/test'}
        histogram.observe(0.05, labels)
        histogram.observe(0.3, labels)
        histogram.observe(0.7, labels)
        histogram.observe(1.5, labels)
        histogram.observe(3.0, labels)
        
        # Check summary
        summary = histogram.get_summary(labels)
        assert summary['count'] == 5
        assert summary['avg'] == pytest.approx((0.05 + 0.3 + 0.7 + 1.5 + 3.0) / 5)
        assert summary['p50'] == 0.7  # Median
        
        # Check buckets
        buckets = histogram.get_buckets(labels)
        assert buckets[0.1] == 1  # Only 0.05 <= 0.1
        assert buckets[0.5] == 2  # 0.05, 0.3 <= 0.5
        assert buckets[1.0] == 3  # 0.05, 0.3, 0.7 <= 1.0
        assert buckets[5.0] == 5  # All values <= 5.0
    
    def test_timer_context_manager(self):
        """Test timer context manager for histograms"""
        registry = MetricsRegistry()
        histogram = registry.histogram('test_timer', 'Test timer')
        
        # Use timer
        with Timer(histogram, {'operation': 'test'}):
            time.sleep(0.1)
        
        # Check that observation was recorded
        summary = histogram.get_summary({'operation': 'test'})
        assert summary['count'] == 1
        assert summary['avg'] >= 0.1  # At least 100ms
    
    def test_prometheus_export(self):
        """Test Prometheus format export"""
        registry = MetricsRegistry()
        
        # Create metrics
        counter = registry.counter('requests_total', 'Total requests', ['method'])
        gauge = registry.gauge('queue_size', 'Queue size')
        histogram = registry.histogram('latency_seconds', 'Request latency')
        
        # Add data
        counter.inc(labels={'method': 'GET'})
        gauge.set(5)
        histogram.observe(0.5)
        histogram.observe(1.5)
        
        # Export
        output = registry.export_prometheus()
        
        # Check output contains expected metrics
        assert '# HELP requests_total Total requests' in output
        assert '# TYPE requests_total counter' in output
        assert 'requests_total{method="GET"} 1' in output
        
        assert '# HELP queue_size Queue size' in output
        assert '# TYPE queue_size gauge' in output
        assert 'queue_size 5' in output
        
        assert '# HELP latency_seconds Request latency' in output
        assert '# TYPE latency_seconds histogram' in output
        assert 'latency_seconds_count 2' in output
        assert 'latency_seconds_sum 2' in output  # 0.5 + 1.5
    
    def test_system_metrics_exist(self):
        """Test that all expected system metrics exist"""
        expected_metrics = [
            'data_ingestion_latency_seconds',
            'data_ingestion_errors_total',
            'data_ingestion_requests_total',
            'indicator_calculation_latency_seconds',
            'indicator_calculation_errors_total',
            'backtest_duration_seconds',
            'backtest_trades_total',
            'live_order_latency_seconds',
            'live_order_errors_total',
            'live_orders_total',
            'queue_depth',
            'data_freshness_seconds',
            'system_up'
        ]
        
        for metric_name in expected_metrics:
            assert metrics_registry.get(metric_name) is not None, f"Missing metric: {metric_name}"


@pytest.mark.asyncio
class TestDataFreshnessCollector:
    """Test data freshness monitoring"""
    
    async def test_freshness_monitoring(self):
        """Test that freshness collector updates metrics"""
        # Create mock market data port
        mock_port = MockMarketDataPort()
        
        # Create collector
        collector = DataFreshnessCollector(
            market_data_port=mock_port,
            update_interval=0.1,  # Fast updates for testing
            staleness_threshold=60
        )
        
        # Add symbols to monitor
        collector.add_symbol('BTCUSDT', '5m')
        collector.add_symbol('ETHUSDT', '1h')
        
        # Start collector
        await collector.start()
        
        # Wait for updates
        await asyncio.sleep(0.3)
        
        # Check freshness metrics
        btc_freshness = system_metrics['data_freshness'].get_value(
            {'symbol': 'BTCUSDT', 'interval': '5m'}
        )
        eth_freshness = system_metrics['data_freshness'].get_value(
            {'symbol': 'ETHUSDT', 'interval': '1h'}
        )
        
        # Should be fresh (around 5 seconds)
        assert btc_freshness < 10
        assert eth_freshness < 10
        
        # Stop collector
        await collector.stop()
    
    async def test_staleness_detection(self):
        """Test detection of stale data"""
        # Create mock port
        mock_port = MockMarketDataPort()
        
        # Create collector with low staleness threshold
        collector = DataFreshnessCollector(
            market_data_port=mock_port,
            update_interval=0.1,
            staleness_threshold=10  # 10 seconds
        )
        
        # Add symbol
        collector.add_symbol('BTCUSDT', '5m')
        
        # Start collector
        await collector.start()
        await asyncio.sleep(0.2)
        
        # Pause data updates to simulate staleness
        mock_port.pause_updates()
        
        # Wait for data to become stale
        await asyncio.sleep(0.3)
        
        # Check freshness
        freshness = system_metrics['data_freshness'].get_value(
            {'symbol': 'BTCUSDT', 'interval': '5m'}
        )
        
        # Should be stale (> 10 seconds)
        assert freshness > 10
        
        # Check summary
        summary = collector.get_freshness_summary()
        assert 'BTCUSDT:5m' in summary
        assert summary['BTCUSDT:5m']['is_stale'] == True
        
        # Resume and verify recovery
        mock_port.resume_updates()
        await asyncio.sleep(0.3)
        
        freshness = system_metrics['data_freshness'].get_value(
            {'symbol': 'BTCUSDT', 'interval': '5m'}
        )
        assert freshness < 10  # Fresh again
        
        await collector.stop()
    
    async def test_staleness_simulation(self):
        """Test manual staleness simulation"""
        mock_port = MockMarketDataPort()
        collector = DataFreshnessCollector(mock_port)
        
        # Simulate staleness
        collector.simulate_staleness('BTCUSDT', '1m', 600)
        
        # Check metric
        freshness = system_metrics['data_freshness'].get_value(
            {'symbol': 'BTCUSDT', 'interval': '1m'}
        )
        assert freshness == 600
        
        # Check summary
        summary = collector.get_freshness_summary()
        assert 'BTCUSDT:1m' in summary
        assert summary['BTCUSDT:1m']['age_seconds'] == 600
        assert summary['BTCUSDT:1m']['is_stale'] == True


@pytest.mark.asyncio
class TestInstrumentedComponents:
    """Test instrumented component wrappers"""
    
    async def test_instrumented_market_data_port(self):
        """Test market data port instrumentation"""
        # Create mock port
        mock_port = AsyncMock()
        mock_port.get_candles.return_value = [
            {'timestamp': datetime.now(), 'close': 45000}
        ]
        
        # Wrap with instrumentation
        instrumented = InstrumentedMarketDataPort(mock_port)
        
        # Clear existing metrics
        metrics_registry.clear()
        # Re-register required metrics
        metrics_registry.histogram(
            'data_ingestion_latency_seconds',
            'Latency of data ingestion',
            labels=['source', 'symbol', 'interval']
        )
        metrics_registry.counter(
            'data_ingestion_requests_total',
            'Total requests',
            labels=['source', 'symbol', 'interval']
        )
        metrics_registry.gauge('queue_depth', 'Queue depth', labels=['queue_name'])
        
        # Make request
        result = await instrumented.get_candles(
            'BTCUSDT', '5m',
            datetime.now() - timedelta(hours=1),
            datetime.now()
        )
        
        # Check metrics were updated
        requests = metrics_registry.get('data_ingestion_requests_total')
        assert requests.get_value({
            'source': 'binance',
            'symbol': 'BTCUSDT',
            'interval': '5m'
        }) == 1
        
        # Check latency was recorded
        latency = metrics_registry.get('data_ingestion_latency_seconds')
        summary = latency.get_summary({
            'source': 'binance',
            'symbol': 'BTCUSDT',
            'interval': '5m'
        })
        assert summary['count'] == 1
        
        # Check queue depth
        queue = metrics_registry.get('queue_depth')
        assert queue.get_value({'queue_name': 'market_data_requests'}) == 1
    
    async def test_instrumented_indicator_port(self):
        """Test indicator port instrumentation"""
        # Create mock port
        mock_port = AsyncMock()
        mock_port.calculate.return_value = [50.0, 51.0, 52.0]
        
        # Wrap with instrumentation
        instrumented = InstrumentedIndicatorPort(mock_port)
        
        # Clear and re-register metrics
        metrics_registry.clear()
        metrics_registry.histogram(
            'indicator_calculation_latency_seconds',
            'Indicator latency',
            labels=['indicator', 'symbol', 'interval']
        )
        
        # Calculate indicator
        data = [{'close': 45000}, {'close': 45100}]
        result = await instrumented.calculate(
            'SMA',
            data,
            {'symbol': 'BTCUSDT', 'interval': '5m', 'period': 20}
        )
        
        # Check metrics
        latency = metrics_registry.get('indicator_calculation_latency_seconds')
        summary = latency.get_summary({
            'indicator': 'SMA',
            'symbol': 'BTCUSDT',
            'interval': '5m'
        })
        assert summary['count'] == 1
    
    async def test_instrumented_backtest_port(self):
        """Test backtest port instrumentation"""
        # Create mock port
        mock_port = AsyncMock()
        mock_port.run.return_value = {
            'metrics': {
                'winning_trades': 10,
                'losing_trades': 5,
                'sharpe': 1.5
            }
        }
        
        # Wrap with instrumentation
        instrumented = InstrumentedBacktestPort(mock_port)
        
        # Clear and re-register metrics
        metrics_registry.clear()
        metrics_registry.histogram(
            'backtest_duration_seconds',
            'Backtest duration',
            labels=['strategy', 'symbol', 'interval'],
            buckets=[1, 5, 10, 30, 60]
        )
        metrics_registry.counter(
            'backtest_trades_total',
            'Backtest trades',
            labels=['strategy', 'symbol', 'interval', 'result']
        )
        
        # Run backtest
        config = {
            'strategy': 'TestStrategy',
            'symbol': 'BTCUSDT',
            'timeframe': '5m'
        }
        result = await instrumented.run(config)
        
        # Check duration was recorded
        duration = metrics_registry.get('backtest_duration_seconds')
        summary = duration.get_summary({
            'strategy': 'TestStrategy',
            'symbol': 'BTCUSDT',
            'interval': '5m'
        })
        assert summary['count'] == 1
        
        # Check trades were counted
        trades = metrics_registry.get('backtest_trades_total')
        assert trades.get_value({
            'strategy': 'TestStrategy',
            'symbol': 'BTCUSDT',
            'interval': '5m',
            'result': 'win'
        }) == 10
        assert trades.get_value({
            'strategy': 'TestStrategy',
            'symbol': 'BTCUSDT',
            'interval': '5m',
            'result': 'loss'
        }) == 5
    
    async def test_instrumented_execution_port(self):
        """Test execution port instrumentation"""
        # Create mock port
        mock_port = AsyncMock()
        mock_port.submit_order.return_value = {
            'order_id': '12345',
            'status': 'filled'
        }
        
        # Wrap with instrumentation
        instrumented = InstrumentedExecutionPort(mock_port)
        
        # Clear and re-register metrics
        metrics_registry.clear()
        metrics_registry.histogram(
            'live_order_latency_seconds',
            'Order latency',
            labels=['exchange', 'symbol', 'order_type']
        )
        metrics_registry.counter(
            'live_orders_total',
            'Total orders',
            labels=['exchange', 'symbol', 'side', 'status']
        )
        metrics_registry.gauge('queue_depth', 'Queue depth', labels=['queue_name'])
        
        # Submit order
        order = {
            'exchange': 'binance',
            'symbol': 'BTCUSDT',
            'type': 'market',
            'side': 'buy',
            'quantity': 0.1
        }
        result = await instrumented.submit_order(order)
        
        # Check latency was recorded
        latency = metrics_registry.get('live_order_latency_seconds')
        summary = latency.get_summary({
            'exchange': 'binance',
            'symbol': 'BTCUSDT',
            'order_type': 'market'
        })
        assert summary['count'] == 1
        
        # Check order was counted
        orders = metrics_registry.get('live_orders_total')
        assert orders.get_value({
            'exchange': 'binance',
            'symbol': 'BTCUSDT',
            'side': 'buy',
            'status': 'filled'
        }) == 1
        
        # Check queue depth
        queue = metrics_registry.get('queue_depth')
        assert queue.get_value({'queue_name': 'order_queue'}) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])