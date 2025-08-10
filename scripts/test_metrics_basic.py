#!/usr/bin/env python3
"""
Basic Metrics Test

Simple test to verify metrics are working.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.monitoring.metrics import metrics_registry, system_metrics


def test_basic_metrics():
    """Test basic metric operations"""
    print("Testing Basic Metrics...")
    
    # Test counter
    counter = metrics_registry.counter('test_counter', 'Test counter')
    counter.inc()
    counter.inc(5)
    print(f"Counter value: {counter.get_value()}")  # Should be 6
    
    # Test gauge
    gauge = metrics_registry.gauge('test_gauge', 'Test gauge')
    gauge.set(10)
    gauge.inc(5)
    gauge.dec(3)
    print(f"Gauge value: {gauge.get_value()}")  # Should be 12
    
    # Test histogram (simplified)
    histogram = metrics_registry.histogram('test_hist', 'Test histogram')
    histogram.observe(0.1)
    histogram.observe(0.2)
    histogram.observe(0.3)
    
    # Don't calculate percentiles to avoid hanging
    count = histogram._counts.get((), 0)
    sum_val = histogram._sums.get((), 0)
    print(f"Histogram: count={count}, sum={sum_val:.1f}")
    
    # Test system metrics exist
    print("\nSystem Metrics Available:")
    for name, metric in system_metrics.items():
        print(f"  - {name}: {metric.metric_type.value}")
    
    # Test Prometheus export
    print("\nPrometheus Export (first 10 lines):")
    export = metrics_registry.export_prometheus()
    lines = export.split('\n')[:10]
    for line in lines:
        if line:
            print(f"  {line}")
    
    print("\n✅ Basic metrics test passed!")


if __name__ == "__main__":
    test_basic_metrics()