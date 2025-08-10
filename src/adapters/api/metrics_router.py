"""
Metrics Router

Provides Prometheus-compatible metrics endpoints.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Response
from collections import defaultdict
import time
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and formats metrics in Prometheus format"""
    
    def __init__(self):
        # Counters
        self.request_count = defaultdict(int)
        self.error_count = defaultdict(int)
        
        # Histograms
        self.request_latency_buckets = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self.request_latency = defaultdict(lambda: defaultdict(int))
        self.request_latency_sum = defaultdict(float)
        self.request_latency_count = defaultdict(int)
        
        # Gauges
        self.queue_depth = defaultdict(int)
        self.data_freshness_seconds = defaultdict(float)
        self.active_connections = 0
        self.memory_usage_bytes = 0
        
        # Custom metrics
        self.custom_metrics = {}
    
    def increment_request(self, endpoint: str, method: str = "GET", status: int = 200):
        """Increment request counter"""
        labels = f'endpoint="{endpoint}",method="{method}",status="{status}"'
        self.request_count[labels] += 1
    
    def increment_error(self, module: str, error_type: str = "unknown"):
        """Increment error counter"""
        labels = f'module="{module}",type="{error_type}"'
        self.error_count[labels] += 1
    
    def observe_latency(self, endpoint: str, latency_seconds: float):
        """Record request latency in histogram"""
        labels = f'endpoint="{endpoint}"'
        
        # Update sum and count
        self.request_latency_sum[labels] += latency_seconds
        self.request_latency_count[labels] += 1
        
        # Update buckets
        for bucket in self.request_latency_buckets:
            if latency_seconds <= bucket:
                self.request_latency[labels][bucket] += 1
    
    def set_queue_depth(self, module: str, depth: int):
        """Set queue depth gauge"""
        self.queue_depth[module] = depth
    
    def set_data_freshness(self, module: str, freshness_seconds: float):
        """Set data freshness gauge"""
        self.data_freshness_seconds[module] = freshness_seconds
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a custom gauge metric"""
        label_str = ""
        if labels:
            label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
            label_str = "{" + ",".join(label_pairs) + "}"
        
        self.custom_metrics[f"{name}{label_str}"] = ("gauge", value)
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a custom counter metric"""
        label_str = ""
        if labels:
            label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
            label_str = "{" + ",".join(label_pairs) + "}"
        
        key = f"{name}{label_str}"
        if key not in self.custom_metrics:
            self.custom_metrics[key] = ("counter", 0)
        
        metric_type, current_value = self.custom_metrics[key]
        self.custom_metrics[key] = (metric_type, current_value + value)
    
    def format_prometheus(self) -> str:
        """Format all metrics in Prometheus text format"""
        lines = []
        
        # Request count counter
        lines.append("# HELP request_count Total number of requests")
        lines.append("# TYPE request_count counter")
        for labels, count in self.request_count.items():
            lines.append(f"request_count{{{labels}}} {count}")
        
        # Error count counter
        lines.append("\n# HELP error_count Total number of errors")
        lines.append("# TYPE error_count counter")
        for labels, count in self.error_count.items():
            lines.append(f"error_count{{{labels}}} {count}")
        
        # Request latency histogram
        lines.append("\n# HELP request_latency_seconds Request latency in seconds")
        lines.append("# TYPE request_latency_seconds histogram")
        for labels in self.request_latency_count.keys():
            # Buckets
            cumulative = 0
            for bucket in self.request_latency_buckets:
                cumulative += self.request_latency[labels].get(bucket, 0)
                lines.append(f'request_latency_seconds_bucket{{le="{bucket}",{labels}}} {cumulative}')
            lines.append(f'request_latency_seconds_bucket{{le="+Inf",{labels}}} {self.request_latency_count[labels]}')
            
            # Sum and count
            lines.append(f"request_latency_seconds_sum{{{labels}}} {self.request_latency_sum[labels]}")
            lines.append(f"request_latency_seconds_count{{{labels}}} {self.request_latency_count[labels]}")
        
        # Queue depth gauge
        lines.append("\n# HELP queue_depth Current queue depth per module")
        lines.append("# TYPE queue_depth gauge")
        for module, depth in self.queue_depth.items():
            lines.append(f'queue_depth{{module="{module}"}} {depth}')
        
        # Data freshness gauge
        lines.append("\n# HELP data_freshness_seconds Data freshness in seconds")
        lines.append("# TYPE data_freshness_seconds gauge")
        for module, freshness in self.data_freshness_seconds.items():
            lines.append(f'data_freshness_seconds{{module="{module}"}} {freshness}')
        
        # Active connections gauge
        lines.append("\n# HELP active_connections Number of active connections")
        lines.append("# TYPE active_connections gauge")
        lines.append(f"active_connections {self.active_connections}")
        
        # Memory usage gauge
        lines.append("\n# HELP memory_usage_bytes Memory usage in bytes")
        lines.append("# TYPE memory_usage_bytes gauge")
        lines.append(f"memory_usage_bytes {self.memory_usage_bytes}")
        
        # Custom metrics
        for metric_name, (metric_type, value) in self.custom_metrics.items():
            base_name = metric_name.split("{")[0] if "{" in metric_name else metric_name
            if base_name not in [line for line in lines if line.startswith("# HELP")]:
                lines.append(f"\n# HELP {base_name} Custom {metric_type} metric")
                lines.append(f"# TYPE {base_name} {metric_type}")
            lines.append(f"{metric_name} {value}")
        
        return "\n".join(lines) + "\n"


# Global metrics collector instance
metrics_collector = MetricsCollector()


# Middleware for automatic request tracking
class MetricsMiddleware:
    """Middleware to automatically track request metrics"""
    
    def __init__(self):
        self.collector = metrics_collector
    
    async def __call__(self, request, call_next):
        """Track request metrics"""
        start_time = time.time()
        
        # Track active connections
        self.collector.active_connections += 1
        
        try:
            response = await call_next(request)
            
            # Record metrics
            latency = time.time() - start_time
            endpoint = str(request.url.path)
            method = request.method
            status = response.status_code
            
            self.collector.increment_request(endpoint, method, status)
            self.collector.observe_latency(endpoint, latency)
            
            # Increment error counter for 5xx responses
            if status >= 500:
                self.collector.increment_error("http", f"status_{status}")
            
            return response
            
        except Exception as e:
            # Record error
            latency = time.time() - start_time
            endpoint = str(request.url.path)
            method = request.method
            
            self.collector.increment_request(endpoint, method, 500)
            self.collector.observe_latency(endpoint, latency)
            self.collector.increment_error("http", "exception")
            
            raise
        
        finally:
            self.collector.active_connections -= 1


# Simulate some metrics for demonstration
def initialize_demo_metrics():
    """Initialize demo metrics for testing"""
    # Simulate some requests
    metrics_collector.increment_request("/api/orders", "POST", 200)
    metrics_collector.increment_request("/api/orders", "POST", 200)
    metrics_collector.increment_request("/api/orders", "GET", 200)
    metrics_collector.increment_request("/api/positions", "GET", 200)
    metrics_collector.increment_request("/api/positions", "GET", 404)
    
    # Simulate some latencies
    metrics_collector.observe_latency("/api/orders", 0.045)
    metrics_collector.observe_latency("/api/orders", 0.032)
    metrics_collector.observe_latency("/api/orders", 0.089)
    metrics_collector.observe_latency("/api/positions", 0.012)
    metrics_collector.observe_latency("/api/positions", 0.015)
    
    # Set some queue depths
    metrics_collector.set_queue_depth("execution", 5)
    metrics_collector.set_queue_depth("backtest", 2)
    metrics_collector.set_queue_depth("market_data", 0)
    
    # Set data freshness
    metrics_collector.set_data_freshness("market_data", 1.5)
    metrics_collector.set_data_freshness("strategy", 0.5)
    
    # Set some custom metrics
    metrics_collector.set_gauge("portfolio_value_usd", 50000.0, {"account": "main"})
    metrics_collector.set_gauge("open_positions", 3, {"account": "main"})
    metrics_collector.increment_counter("trades_executed", 10, {"strategy": "ema_cross"})
    
    # Simulate some errors
    metrics_collector.increment_error("execution", "timeout")
    metrics_collector.increment_error("market_data", "connection_lost")


# Initialize demo metrics on module load
initialize_demo_metrics()


# Create router
router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=Response)
async def get_metrics() -> Response:
    """
    Get Prometheus-formatted metrics
    
    Returns metrics in Prometheus text format (text/plain)
    """
    metrics_text = metrics_collector.format_prometheus()
    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@router.get("/metrics/json")
async def get_metrics_json() -> Dict[str, Any]:
    """
    Get metrics in JSON format (for debugging)
    
    Returns all metrics as structured JSON
    """
    return {
        "counters": {
            "request_count": dict(metrics_collector.request_count),
            "error_count": dict(metrics_collector.error_count)
        },
        "histograms": {
            "request_latency": {
                "buckets": dict(metrics_collector.request_latency),
                "sum": dict(metrics_collector.request_latency_sum),
                "count": dict(metrics_collector.request_latency_count)
            }
        },
        "gauges": {
            "queue_depth": dict(metrics_collector.queue_depth),
            "data_freshness_seconds": dict(metrics_collector.data_freshness_seconds),
            "active_connections": metrics_collector.active_connections,
            "memory_usage_bytes": metrics_collector.memory_usage_bytes
        },
        "custom": {
            name: {"type": metric_type, "value": value}
            for name, (metric_type, value) in metrics_collector.custom_metrics.items()
        }
    }


@router.post("/metrics/increment/{metric_name}")
async def increment_metric(
    metric_name: str,
    value: int = 1,
    module: Optional[str] = None
) -> Dict[str, str]:
    """
    Increment a counter metric (for testing)
    
    Args:
        metric_name: Name of the metric to increment
        value: Amount to increment by
        module: Optional module label
    """
    labels = {"module": module} if module else None
    metrics_collector.increment_counter(metric_name, value, labels)
    return {"status": "incremented", "metric": metric_name, "value": str(value)}


@router.post("/metrics/gauge/{metric_name}")
async def set_gauge_metric(
    metric_name: str,
    value: float,
    module: Optional[str] = None
) -> Dict[str, Any]:
    """
    Set a gauge metric value (for testing)
    
    Args:
        metric_name: Name of the metric
        value: Value to set
        module: Optional module label
    """
    labels = {"module": module} if module else None
    metrics_collector.set_gauge(metric_name, value, labels)
    return {"status": "set", "metric": metric_name, "value": str(value)}