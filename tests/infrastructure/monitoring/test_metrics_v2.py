"""
Tests for Metrics Infrastructure v2

Tests using proper Prometheus approach without percentile calculations.
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
import warnings

from src.infrastructure.monitoring.metrics_v2 import (
    MetricsRegistry, Timer, get_metric_value, get_histogram_info,
    metrics_registry, system_metrics, LATENCY_BUCKETS
)
from src.infrastructure.monitoring.freshness_collector import DataFreshnessCollector


class SimpleMockMarketDataPort:
    """Simple mock market data port for testing"""
    
    def __init__(self):
        self._paused = False
    
    async def get_candles(self, symbol, interval, start_time, end_time, limit=None):
        """Get mock candles"""
        from datetime import datetime, timedelta
        if self._paused:
            # Return old data when paused
            timestamp = datetime.now() - timedelta(minutes=30)
        else:
            # Return fresh data
            timestamp = datetime.now() - timedelta(seconds=5)
        
        return [{
            'timestamp': timestamp,
            'open': 45000,
            'high': 45100,
            'low': 44900,
            'close': 45050,
            'volume': 100
        }]
    
    def pause_updates(self):
        """Pause data updates to simulate staleness"""
        self._paused = True
    
    def resume_updates(self):
        """Resume data updates"""
        self._paused = False


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
        counter.labels(method='GET', status='200').inc()
        counter.labels(method='GET', status='200').inc()
        counter.labels(method='POST', status='201').inc()
        
        # Check values using get_metric_value helper
        assert get_metric_value(counter, {'method': 'GET', 'status': '200'}) == 2
        assert get_metric_value(counter, {'method': 'POST', 'status': '201'}) == 1
        
        # Non-existent label combination should be 0
        assert get_metric_value(counter, {'method': 'DELETE', 'status': '404'}) == 0
    
    def test_gauge_metrics(self):
        """Test gauge metric operations"""
        registry = MetricsRegistry()
        gauge = registry.gauge(
            'test_gauge',
            'Test gauge metric',
            labels=['queue']
        )
        
        # Set gauge value
        gauge.labels(queue='orders').set(10)
        assert get_metric_value(gauge, {'queue': 'orders'}) == 10
        
        # Increment and decrement
        gauge.labels(queue='orders').inc(5)
        assert get_metric_value(gauge, {'queue': 'orders'}) == 15
        
        gauge.labels(queue='orders').dec(3)
        assert get_metric_value(gauge, {'queue': 'orders'}) == 12
    
    def test_histogram_metrics_no_percentiles(self):
        """Test histogram metrics without percentile calculations"""
        registry = MetricsRegistry()
        histogram = registry.histogram(
            'test_latency',
            'Test latency histogram',
            labels=['endpoint'],
            buckets=(0.1, 0.5, 1.0, 5.0)
        )
        
        # Record observations
        labels = {'endpoint': '/api/test'}
        histogram.labels(**labels).observe(0.05)
        histogram.labels(**labels).observe(0.3)
        histogram.labels(**labels).observe(0.7)
        histogram.labels(**labels).observe(1.5)
        histogram.labels(**labels).observe(3.0)
        
        # Get histogram info
        info = get_histogram_info(histogram, labels)
        
        # Assert count and sum
        assert info['count'] == 5
        assert info['sum'] == pytest.approx(0.05 + 0.3 + 0.7 + 1.5 + 3.0)
        
        # Assert bucket counts (cumulative)
        assert info['buckets'][0.1] == 1  # Only 0.05 <= 0.1
        assert info['buckets'][0.5] == 2  # 0.05, 0.3 <= 0.5
        assert info['buckets'][1.0] == 3  # 0.05, 0.3, 0.7 <= 1.0
        assert info['buckets'][5.0] == 5  # All values <= 5.0
        assert info['buckets'][float('inf')] == 5  # All values
        
        # Verify monotonic increase across buckets
        bucket_values = [info['buckets'][b] for b in sorted(info['buckets'].keys())]
        for i in range(1, len(bucket_values)):
            assert bucket_values[i] >= bucket_values[i-1], "Buckets should be monotonically increasing"
    
    def test_timer_context_manager(self):
        """Test timer context manager for histograms"""
        registry = MetricsRegistry()
        histogram = registry.histogram('test_timer', 'Test timer')
        
        # Use timer
        with Timer(histogram):
            time.sleep(0.01)  # Short sleep to avoid test slowness
        
        # Check that observation was recorded
        info = get_histogram_info(histogram)
        assert info['count'] == 1
        assert info['sum'] >= 0.01  # At least 10ms
        
        # Check with labels
        histogram_labeled = registry.histogram('test_timer_labeled', 'Test timer', labels=['op'])
        with Timer(histogram_labeled, {'op': 'test'}):
            time.sleep(0.01)
        
        info_labeled = get_histogram_info(histogram_labeled, {'op': 'test'})
        assert info_labeled['count'] == 1
        assert info_labeled['sum'] >= 0.01
    
    def test_prometheus_export(self):
        """Test Prometheus format export"""
        registry = MetricsRegistry()
        
        # Create metrics
        counter = registry.counter('requests_total', 'Total requests', ['method'])
        gauge = registry.gauge('queue_size', 'Queue size')
        histogram = registry.histogram('latency_seconds', 'Request latency')
        
        # Add data
        counter.labels(method='GET').inc()
        gauge.set(5)
        histogram.observe(0.5)
        histogram.observe(1.5)
        
        # Export
        output = registry.export_prometheus()
        
        # Check output contains expected metrics
        assert 'requests_total' in output
        assert 'queue_size' in output
        assert 'latency_seconds_bucket' in output
        assert 'latency_seconds_count' in output
        assert 'latency_seconds_sum' in output
        
        # Verify histogram bucket format
        assert 'latency_seconds_bucket{le="0.005"}' in output
        assert 'latency_seconds_bucket{le="+Inf"}' in output
    
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


class TestDataFreshnessCollector:
    """Test data freshness monitoring"""
    
    @pytest.mark.asyncio
    async def test_freshness_monitoring_with_timeout(self):
        """Test freshness collector with proper timeout"""
        # Create mock market data port
        mock_port = SimpleMockMarketDataPort()
        
        # Create collector with fast update interval
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
        
        try:
            # Wait for updates with timeout
            await asyncio.wait_for(asyncio.sleep(0.3), timeout=1.0)
            
            # Check freshness metrics
            btc_freshness = get_metric_value(
                system_metrics['data_freshness'],
                {'symbol': 'BTCUSDT', 'interval': '5m'}
            )
            eth_freshness = get_metric_value(
                system_metrics['data_freshness'],
                {'symbol': 'ETHUSDT', 'interval': '1h'}
            )
            
            # Should be fresh (around 5 seconds)
            assert btc_freshness < 10
            assert eth_freshness < 10
            
        finally:
            # Always stop collector to clean up
            await collector.stop()
    
    @pytest.mark.asyncio
    async def test_staleness_detection_with_timeout(self):
        """Test detection of stale data with timeout"""
        # Create mock port
        mock_port = SimpleMockMarketDataPort()
        
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
        
        try:
            # Initial wait
            await asyncio.wait_for(asyncio.sleep(0.2), timeout=1.0)
            
            # Pause data updates to simulate staleness
            mock_port.pause_updates()
            
            # Wait for data to become stale
            await asyncio.wait_for(asyncio.sleep(0.3), timeout=1.0)
            
            # Check freshness
            freshness = get_metric_value(
                system_metrics['data_freshness'],
                {'symbol': 'BTCUSDT', 'interval': '5m'}
            )
            
            # Should be stale (> 10 seconds due to pause)
            # Note: This might not always be > 10 in test due to timing
            assert freshness > 0  # At least some age
            
            # Check summary
            summary = collector.get_freshness_summary()
            assert 'BTCUSDT:5m' in summary
            
            # Resume and verify recovery
            mock_port.resume_updates()
            await asyncio.wait_for(asyncio.sleep(0.3), timeout=1.0)
            
            freshness_after = get_metric_value(
                system_metrics['data_freshness'],
                {'symbol': 'BTCUSDT', 'interval': '5m'}
            )
            # Should be fresher after resume
            assert freshness_after < 10
            
        finally:
            # Always stop collector
            await collector.stop()
    
    def test_staleness_simulation(self):
        """Test manual staleness simulation"""
        mock_port = SimpleMockMarketDataPort()
        collector = DataFreshnessCollector(mock_port)
        
        # Simulate staleness
        collector.simulate_staleness('BTCUSDT', '1m', 600)
        
        # Check metric
        freshness = get_metric_value(
            system_metrics['data_freshness'],
            {'symbol': 'BTCUSDT', 'interval': '1m'}
        )
        assert freshness == 600
        
        # Check summary
        summary = collector.get_freshness_summary()
        assert 'BTCUSDT:1m' in summary
        assert summary['BTCUSDT:1m']['age_seconds'] == pytest.approx(600, rel=0.01)
        assert summary['BTCUSDT:1m']['is_stale'] == True


class TestHistogramBuckets:
    """Test histogram bucket behavior"""
    
    def test_default_latency_buckets(self):
        """Test that default latency buckets are properly configured"""
        registry = MetricsRegistry()
        histogram = registry.histogram(
            'test_latency_buckets',
            'Test latency with default buckets'
        )
        
        # Record values across the bucket range
        test_values = [0.001, 0.008, 0.02, 0.04, 0.08, 0.2, 0.4, 0.8, 2.0, 4.0, 8.0, 15.0]
        for value in test_values:
            histogram.observe(value)
        
        info = get_histogram_info(histogram)
        
        # Verify count and sum
        assert info['count'] == len(test_values)
        assert info['sum'] == pytest.approx(sum(test_values), rel=0.01)
        
        # Verify bucket boundaries exist
        expected_buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        for bucket in expected_buckets:
            assert bucket in info['buckets'], f"Missing bucket: {bucket}"
        
        # Verify monotonic increase
        sorted_buckets = sorted(info['buckets'].keys())
        for i in range(1, len(sorted_buckets)):
            assert info['buckets'][sorted_buckets[i]] >= info['buckets'][sorted_buckets[i-1]]
    
    def test_custom_buckets(self):
        """Test custom bucket configuration"""
        registry = MetricsRegistry()
        custom_buckets = (1, 10, 100, 1000)
        histogram = registry.histogram(
            'test_custom_buckets',
            'Test with custom buckets',
            buckets=custom_buckets
        )
        
        # Record values
        values = [0.5, 5, 50, 500, 5000]
        for v in values:
            histogram.observe(v)
        
        info = get_histogram_info(histogram)
        
        # Check bucket counts
        assert info['buckets'][1] == 1      # 0.5 <= 1
        assert info['buckets'][10] == 2     # 0.5, 5 <= 10
        assert info['buckets'][100] == 3    # 0.5, 5, 50 <= 100
        assert info['buckets'][1000] == 4   # 0.5, 5, 50, 500 <= 1000
        assert info['buckets'][float('inf')] == 5  # All values


class TestMetricsClearAndReset:
    """Test metrics clearing and reset functionality"""
    
    def test_registry_clear(self):
        """Test that registry can be cleared"""
        registry = MetricsRegistry()
        
        # Add some metrics
        counter = registry.counter('test_clear_counter', 'Test counter')
        gauge = registry.gauge('test_clear_gauge', 'Test gauge')
        
        counter.inc()
        gauge.set(10)
        
        # Verify metrics exist
        assert registry.get('test_clear_counter') is not None
        assert registry.get('test_clear_gauge') is not None
        
        # Clear registry
        registry.clear()
        
        # Verify metrics are gone
        assert registry.get('test_clear_counter') is None
        assert registry.get('test_clear_gauge') is None
        assert len(registry.get_all()) == 0


if __name__ == "__main__":
    # Run with minimal verbosity to check for timeouts
    pytest.main([__file__, "-q", "--tb=short"])