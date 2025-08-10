"""
Metrics Infrastructure

Provides Prometheus-compatible metrics for monitoring system performance.
"""
import time
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import threading


class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricValue:
    """Single metric value with labels"""
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class HistogramBucket:
    """Histogram bucket for latency tracking"""
    le: float  # Less than or equal to
    count: int = 0


class Metric:
    """Base metric class"""
    
    def __init__(
        self,
        name: str,
        description: str,
        metric_type: MetricType,
        labels: List[str] = None
    ):
        """
        Initialize metric
        
        Args:
            name: Metric name (e.g., 'http_requests_total')
            description: Human-readable description
            metric_type: Type of metric
            labels: List of label names
        """
        self.name = name
        self.description = description
        self.metric_type = metric_type
        self.labels = labels or []
        self._values: Dict[tuple, MetricValue] = {}
        self._lock = threading.Lock()
    
    def _get_label_key(self, labels: Dict[str, str]) -> tuple:
        """Get hashable key from labels"""
        if not self.labels:
            return ()
        return tuple(labels.get(label, "") for label in self.labels)
    
    def get_value(self, labels: Dict[str, str] = None) -> float:
        """Get metric value for given labels"""
        labels = labels or {}
        key = self._get_label_key(labels)
        with self._lock:
            return self._values.get(key, MetricValue(0)).value


class Counter(Metric):
    """Counter metric - only goes up"""
    
    def __init__(self, name: str, description: str, labels: List[str] = None):
        super().__init__(name, description, MetricType.COUNTER, labels)
    
    def inc(self, value: float = 1, labels: Dict[str, str] = None):
        """Increment counter"""
        if value < 0:
            raise ValueError("Counter can only increase")
        
        labels = labels or {}
        key = self._get_label_key(labels)
        
        with self._lock:
            if key not in self._values:
                self._values[key] = MetricValue(0, labels)
            self._values[key].value += value
            self._values[key].timestamp = time.time()
    
    def get_all(self) -> List[MetricValue]:
        """Get all counter values"""
        with self._lock:
            return list(self._values.values())


class Gauge(Metric):
    """Gauge metric - can go up or down"""
    
    def __init__(self, name: str, description: str, labels: List[str] = None):
        super().__init__(name, description, MetricType.GAUGE, labels)
    
    def set(self, value: float, labels: Dict[str, str] = None):
        """Set gauge value"""
        labels = labels or {}
        key = self._get_label_key(labels)
        
        with self._lock:
            self._values[key] = MetricValue(value, labels)
    
    def inc(self, value: float = 1, labels: Dict[str, str] = None):
        """Increment gauge"""
        labels = labels or {}
        key = self._get_label_key(labels)
        
        with self._lock:
            if key not in self._values:
                self._values[key] = MetricValue(0, labels)
            self._values[key].value += value
            self._values[key].timestamp = time.time()
    
    def dec(self, value: float = 1, labels: Dict[str, str] = None):
        """Decrement gauge"""
        self.inc(-value, labels)
    
    def get_all(self) -> List[MetricValue]:
        """Get all gauge values"""
        with self._lock:
            return list(self._values.values())


class Histogram(Metric):
    """Histogram metric for latency tracking"""
    
    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    
    def __init__(
        self,
        name: str,
        description: str,
        labels: List[str] = None,
        buckets: List[float] = None
    ):
        super().__init__(name, description, MetricType.HISTOGRAM, labels)
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._observations: Dict[tuple, List[float]] = defaultdict(list)
        self._bucket_counts: Dict[tuple, Dict[float, int]] = defaultdict(
            lambda: {b: 0 for b in self.buckets + [float('inf')]}
        )
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._counts: Dict[tuple, int] = defaultdict(int)
    
    def observe(self, value: float, labels: Dict[str, str] = None):
        """Record an observation"""
        labels = labels or {}
        key = self._get_label_key(labels)
        
        with self._lock:
            self._observations[key].append(value)
            self._sums[key] += value
            self._counts[key] += 1
            
            # Update buckets
            for bucket in self.buckets + [float('inf')]:
                if value <= bucket:
                    self._bucket_counts[key][bucket] += 1
    
    def get_percentile(self, percentile: float, labels: Dict[str, str] = None) -> float:
        """Get percentile value"""
        labels = labels or {}
        key = self._get_label_key(labels)
        
        with self._lock:
            observations = sorted(self._observations.get(key, []))
            if not observations:
                return 0
            
            index = int(len(observations) * percentile / 100)
            return observations[min(index, len(observations) - 1)]
    
    def get_summary(self, labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get histogram summary"""
        labels = labels or {}
        key = self._get_label_key(labels)
        
        with self._lock:
            count = self._counts.get(key, 0)
            if count == 0:
                return {
                    'count': 0,
                    'sum': 0,
                    'avg': 0,
                    'p50': 0,
                    'p95': 0,
                    'p99': 0
                }
            
            return {
                'count': count,
                'sum': self._sums.get(key, 0),
                'avg': self._sums.get(key, 0) / count,
                'p50': self.get_percentile(50, labels),
                'p95': self.get_percentile(95, labels),
                'p99': self.get_percentile(99, labels)
            }
    
    def get_buckets(self, labels: Dict[str, str] = None) -> Dict[float, int]:
        """Get bucket counts"""
        labels = labels or {}
        key = self._get_label_key(labels)
        
        with self._lock:
            return dict(self._bucket_counts.get(key, {}))


class Timer:
    """Context manager for timing operations"""
    
    def __init__(self, histogram: Histogram, labels: Dict[str, str] = None):
        self.histogram = histogram
        self.labels = labels or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.histogram.observe(duration, self.labels)


class MetricsRegistry:
    """Central registry for all metrics"""
    
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()
    
    def register(self, metric: Metric) -> Metric:
        """Register a metric"""
        with self._lock:
            if metric.name in self._metrics:
                raise ValueError(f"Metric {metric.name} already registered")
            self._metrics[metric.name] = metric
            return metric
    
    def counter(self, name: str, description: str, labels: List[str] = None) -> Counter:
        """Create and register a counter"""
        return self.register(Counter(name, description, labels))
    
    def gauge(self, name: str, description: str, labels: List[str] = None) -> Gauge:
        """Create and register a gauge"""
        return self.register(Gauge(name, description, labels))
    
    def histogram(
        self,
        name: str,
        description: str,
        labels: List[str] = None,
        buckets: List[float] = None
    ) -> Histogram:
        """Create and register a histogram"""
        return self.register(Histogram(name, description, labels, buckets))
    
    def get(self, name: str) -> Optional[Metric]:
        """Get metric by name"""
        return self._metrics.get(name)
    
    def get_all(self) -> Dict[str, Metric]:
        """Get all metrics"""
        with self._lock:
            return dict(self._metrics)
    
    def clear(self):
        """Clear all metrics (for testing)"""
        with self._lock:
            self._metrics.clear()
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        with self._lock:
            for metric in self._metrics.values():
                # Add HELP and TYPE lines
                lines.append(f"# HELP {metric.name} {metric.description}")
                lines.append(f"# TYPE {metric.name} {metric.metric_type.value}")
                
                if isinstance(metric, (Counter, Gauge)):
                    for value in metric.get_all():
                        label_str = ""
                        if value.labels:
                            label_parts = [f'{k}="{v}"' for k, v in value.labels.items()]
                            label_str = "{" + ",".join(label_parts) + "}"
                        lines.append(f"{metric.name}{label_str} {value.value}")
                
                elif isinstance(metric, Histogram):
                    # Export all label combinations
                    label_keys = set()
                    for key in metric._bucket_counts.keys():
                        label_keys.add(key)
                    
                    for key in label_keys:
                        # Reconstruct labels from key
                        labels = {}
                        if metric.labels and key:
                            labels = dict(zip(metric.labels, key))
                        
                        label_str = ""
                        if labels:
                            label_parts = [f'{k}="{v}"' for k, v in labels.items()]
                            label_str = "{" + ",".join(label_parts) + "}"
                        
                        # Export buckets
                        buckets = metric.get_buckets(labels)
                        for bucket_val, count in buckets.items():
                            if bucket_val == float('inf'):
                                bucket_label = f'{label_str}{{le="+Inf"}}'
                            else:
                                bucket_label = f'{label_str}{{le="{bucket_val}"}}'
                            
                            # Remove extra braces if no labels
                            bucket_label = bucket_label.replace("{}", "")
                            lines.append(f"{metric.name}_bucket{bucket_label} {count}")
                        
                        # Export sum and count
                        summary = metric.get_summary(labels)
                        lines.append(f"{metric.name}_sum{label_str} {summary['sum']}")
                        lines.append(f"{metric.name}_count{label_str} {summary['count']}")
        
        return "\n".join(lines) + "\n"


# Global registry instance
metrics_registry = MetricsRegistry()

# System-wide metrics
system_metrics = {
    # Data ingestion metrics
    'data_ingestion_latency': metrics_registry.histogram(
        'data_ingestion_latency_seconds',
        'Latency of data ingestion operations',
        labels=['source', 'symbol', 'interval']
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
        labels=['indicator', 'symbol', 'interval']
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
        buckets=[1, 5, 10, 30, 60, 120, 300, 600]
    ),
    'backtest_trades': metrics_registry.counter(
        'backtest_trades_total',
        'Total number of trades in backtests',
        labels=['strategy', 'symbol', 'result']
    ),
    
    # Live trading metrics
    'live_order_latency': metrics_registry.histogram(
        'live_order_latency_seconds',
        'Latency of live order submissions',
        labels=['exchange', 'symbol', 'order_type']
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