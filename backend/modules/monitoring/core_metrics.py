"""
Metrics Infrastructure v2 - Using prometheus_client

Proper Prometheus implementation without in-process percentile calculations.
"""
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, generate_latest
from typing import Dict, List, Optional, Any
import time


# Default buckets for different metric types
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf"))
DURATION_BUCKETS = (1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600, float("inf"))
SIZE_BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000, 10000, float("inf"))


class MetricsRegistry:
    """Wrapper around prometheus_client CollectorRegistry"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        self._metrics: Dict[str, Any] = {}
    
    def counter(self, name: str, description: str, labels: List[str] = None) -> Counter:
        """Create and register a counter"""
        labels = labels or []
        metric = Counter(name, description, labels, registry=self.registry)
        self._metrics[name] = metric
        return metric
    
    def gauge(self, name: str, description: str, labels: List[str] = None) -> Gauge:
        """Create and register a gauge"""
        labels = labels or []
        metric = Gauge(name, description, labels, registry=self.registry)
        self._metrics[name] = metric
        return metric
    
    def histogram(
        self,
        name: str,
        description: str,
        labels: List[str] = None,
        buckets: tuple = LATENCY_BUCKETS
    ) -> Histogram:
        """Create and register a histogram"""
        labels = labels or []
        # Ensure buckets don't include inf - prometheus_client adds it automatically
        clean_buckets = tuple(b for b in buckets if b != float("inf"))
        metric = Histogram(name, description, labels, buckets=clean_buckets, registry=self.registry)
        self._metrics[name] = metric
        return metric
    
    def get(self, name: str) -> Optional[Any]:
        """Get metric by name"""
        return self._metrics.get(name)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all metrics"""
        return dict(self._metrics)
    
    def clear(self):
        """Clear all metrics (for testing)"""
        # Create new registry to clear all metrics
        self.registry = CollectorRegistry()
        self._metrics.clear()
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        return generate_latest(self.registry).decode('utf-8')


# Global registry instance
metrics_registry = MetricsRegistry()

# System-wide metrics with proper Prometheus implementation
system_metrics = {
    # Data ingestion metrics
    'data_ingestion_latency': metrics_registry.histogram(
        'data_ingestion_latency_seconds',
        'Latency of data ingestion operations',
        labels=['source', 'symbol', 'interval'],
        buckets=LATENCY_BUCKETS
    ),
    'data_ingestion_errors': metrics_registry.counter(
        'data_ingestion_errors_total',
        'Total number of data ingestion errors',
        labels=['source', 'symbol', 'interval', 'error_type']
    ),
    'data_ingestion_requests': metrics_registry.counter(
        'data_ingestion_requests_total',
        'Total number of data ingestion requests',
        labels=['source', 'symbol', 'interval']
    ),
    
    # Indicator calculation metrics
    'indicator_calc_latency': metrics_registry.histogram(
        'indicator_calculation_latency_seconds',
        'Latency of indicator calculations',
        labels=['indicator', 'symbol', 'interval'],
        buckets=LATENCY_BUCKETS
    ),
    'indicator_calc_errors': metrics_registry.counter(
        'indicator_calculation_errors_total',
        'Total number of indicator calculation errors',
        labels=['indicator', 'symbol', 'interval']
    ),
    
    # Backtest metrics
    'backtest_duration': metrics_registry.histogram(
        'backtest_duration_seconds',
        'Duration of backtest runs',
        labels=['strategy', 'symbol', 'interval'],
        buckets=DURATION_BUCKETS
    ),
    'backtest_trades': metrics_registry.counter(
        'backtest_trades_total',
        'Total number of trades in backtests',
        labels=['strategy', 'symbol', 'interval', 'result']
    ),
    
    # Live trading metrics
    'live_order_latency': metrics_registry.histogram(
        'live_order_latency_seconds',
        'Latency of live order submissions',
        labels=['exchange', 'symbol', 'order_type'],
        buckets=LATENCY_BUCKETS
    ),
    'live_order_errors': metrics_registry.counter(
        'live_order_errors_total',
        'Total number of live order errors',
        labels=['exchange', 'symbol', 'error_type']
    ),
    'live_orders': metrics_registry.counter(
        'live_orders_total',
        'Total number of live orders',
        labels=['exchange', 'symbol', 'side', 'status']
    ),
    
    # Queue depth metrics
    'queue_depth': metrics_registry.gauge(
        'queue_depth',
        'Current queue depth',
        labels=['queue_name']
    ),
    
    # Data freshness metrics
    'data_freshness': metrics_registry.gauge(
        'data_freshness_seconds',
        'Age of latest data in seconds',
        labels=['symbol', 'interval']
    ),
    
    # System health
    'system_up': metrics_registry.gauge(
        'system_up',
        'System availability (1=up, 0=down)',
        labels=['component']
    )
}


class Timer:
    """Context manager for timing operations with Histogram"""
    
    def __init__(self, histogram: Histogram, labels: Dict[str, str] = None):
        """
        Initialize timer
        
        Args:
            histogram: Prometheus Histogram metric
            labels: Label values for this observation
        """
        self.histogram = histogram
        self.labels = labels or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            # Use labels() to get the correct metric instance, then observe
            if self.labels:
                self.histogram.labels(**self.labels).observe(duration)
            else:
                self.histogram.observe(duration)


def get_metric_value(metric: Any, labels: Dict[str, str] = None) -> float:
    """
    Helper to get current value of a metric
    
    Args:
        metric: Prometheus metric object
        labels: Label values to filter by
        
    Returns:
        Current value (for gauges/counters) or count (for histograms)
    """
    try:
        # Use collect() to get the current value
        for family in metric.collect():
            for sample in family.samples:
                # For labeled metrics, check if labels match
                if labels:
                    # Check if all required labels match
                    matches = all(
                        sample.labels.get(k) == str(v) 
                        for k, v in labels.items()
                    )
                    if matches and not sample.name.endswith('_total'):
                        return sample.value
                    elif matches and sample.name.endswith('_total'):
                        # For counters
                        return sample.value
                else:
                    # For unlabeled metrics, return first value
                    if not sample.labels or (len(sample.labels) == 0):
                        return sample.value
    except Exception:
        pass
    
    # Alternative method for direct access
    try:
        if labels:
            return metric.labels(**labels)._value.get()
        else:
            if hasattr(metric, '_value'):
                return metric._value.get()
    except Exception:
        pass
    
    return 0.0


def get_histogram_info(histogram: Histogram, labels: Dict[str, str] = None) -> Dict[str, float]:
    """
    Get histogram information without percentiles
    
    Args:
        histogram: Prometheus Histogram metric
        labels: Label values to filter by
        
    Returns:
        Dictionary with count, sum, and bucket counts
    """
    if labels:
        h = histogram.labels(**labels)
    else:
        h = histogram
    
    # Access the internal metrics correctly for prometheus_client
    # The histogram has _count, _sum, and _buckets attributes
    # but they're accessed differently
    info = {
        'count': 0.0,
        'sum': 0.0,
        'buckets': {}
    }
    
    # Try to get the samples from the metric
    try:
        # Collect samples from the metric
        for metric in histogram.collect():
            for sample in metric.samples:
                # Build label string for matching
                if labels:
                    label_str = ','.join(f'{k}="{v}"' for k, v in labels.items())
                    # Check if this sample matches our labels
                    sample_labels = ','.join(f'{k}="{v}"' for k, v in sample.labels.items() if k != 'le')
                    if label_str != sample_labels and labels:
                        continue
                
                # Extract metric data based on sample name
                if sample.name.endswith('_count'):
                    info['count'] = sample.value
                elif sample.name.endswith('_sum'):
                    info['sum'] = sample.value
                elif sample.name.endswith('_bucket'):
                    # Extract bucket upper bound from labels
                    le = sample.labels.get('le', '+Inf')
                    if le == '+Inf':
                        info['buckets'][float('inf')] = sample.value
                    else:
                        info['buckets'][float(le)] = sample.value
    except Exception:
        # Fallback for simpler access
        pass
    
    return info