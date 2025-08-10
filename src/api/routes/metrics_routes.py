"""
Metrics API Routes

Exposes Prometheus-compatible metrics endpoint.
"""
from fastapi import APIRouter, Response
from typing import Optional

from src.infrastructure.monitoring.metrics import metrics_registry, system_metrics
from src.infrastructure.monitoring.freshness_collector import DataFreshnessCollector

router = APIRouter(prefix="/metrics", tags=["monitoring"])

# Global freshness collector instance (initialized by app startup)
freshness_collector: Optional[DataFreshnessCollector] = None


@router.get("", response_class=Response)
async def get_metrics():
    """
    Get Prometheus-formatted metrics
    
    Returns all system metrics in Prometheus text format.
    """
    # Export metrics in Prometheus format
    metrics_text = metrics_registry.export_prometheus()
    
    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4"
    )


@router.get("/health")
async def get_health():
    """
    Get system health metrics
    
    Returns a summary of system health indicators.
    """
    # Check component health
    components = ['data_ingestion', 'indicator_calc', 'backtest', 'live_trading']
    health_status = {}
    
    for component in components:
        # Check if component is up (simplified - in production would check actual status)
        is_up = system_metrics['system_up'].get_value({'component': component})
        health_status[component] = {
            'status': 'up' if is_up == 1 else 'down',
            'value': is_up
        }
    
    # Get data freshness summary
    freshness_summary = {}
    if freshness_collector:
        freshness_summary = freshness_collector.get_freshness_summary()
    
    # Get queue depths
    queue_status = {
        'market_data_requests': system_metrics['queue_depth'].get_value(
            {'queue_name': 'market_data_requests'}
        ),
        'order_queue': system_metrics['queue_depth'].get_value(
            {'queue_name': 'order_queue'}
        )
    }
    
    # Get error rates
    error_rates = {
        'data_ingestion': _get_error_rate('data_ingestion'),
        'indicator_calc': _get_error_rate('indicator_calc'),
        'live_orders': _get_error_rate('live_orders')
    }
    
    return {
        'status': 'healthy' if all(h['status'] == 'up' for h in health_status.values()) else 'degraded',
        'components': health_status,
        'data_freshness': freshness_summary,
        'queue_depths': queue_status,
        'error_rates': error_rates
    }


@router.get("/freshness")
async def get_data_freshness():
    """
    Get detailed data freshness metrics
    
    Returns the age of data for all monitored symbols.
    """
    if not freshness_collector:
        return {
            'error': 'Freshness collector not initialized',
            'symbols': {}
        }
    
    return {
        'summary': freshness_collector.get_freshness_summary(),
        'staleness_threshold': freshness_collector.staleness_threshold,
        'update_interval': freshness_collector.update_interval
    }


@router.post("/freshness/simulate")
async def simulate_staleness(
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    age_seconds: float = 600
):
    """
    Simulate data staleness for testing
    
    Args:
        symbol: Trading symbol
        interval: Time interval
        age_seconds: Simulated age in seconds
    """
    if not freshness_collector:
        return {
            'error': 'Freshness collector not initialized'
        }
    
    freshness_collector.simulate_staleness(symbol, interval, age_seconds)
    
    return {
        'status': 'simulated',
        'symbol': symbol,
        'interval': interval,
        'age_seconds': age_seconds
    }


@router.get("/latency/{component}")
async def get_latency_metrics(component: str):
    """
    Get latency metrics for a specific component
    
    Args:
        component: Component name (data_ingestion, indicator_calc, backtest, live_order)
    """
    histogram_map = {
        'data_ingestion': 'data_ingestion_latency',
        'indicator_calc': 'indicator_calc_latency',
        'backtest': 'backtest_duration',
        'live_order': 'live_order_latency'
    }
    
    metric_name = histogram_map.get(component)
    if not metric_name:
        return {'error': f'Unknown component: {component}'}
    
    histogram = system_metrics.get(metric_name)
    if not histogram:
        return {'error': f'Metric not found: {metric_name}'}
    
    # Get summary for all label combinations
    summaries = {}
    
    # Get unique label combinations from the histogram
    for key in histogram._observations.keys():
        if histogram.labels and key:
            labels = dict(zip(histogram.labels, key))
        else:
            labels = {}
        
        label_str = '_'.join(f"{k}={v}" for k, v in labels.items()) or 'default'
        summaries[label_str] = histogram.get_summary(labels)
    
    return {
        'component': component,
        'metric': metric_name,
        'summaries': summaries
    }


@router.get("/counters")
async def get_counter_metrics():
    """
    Get all counter metrics
    
    Returns current values for all counter metrics.
    """
    counters = {}
    
    counter_names = [
        'data_ingestion_requests',
        'data_ingestion_errors',
        'indicator_calc_errors',
        'backtest_trades',
        'live_orders',
        'live_order_errors'
    ]
    
    for name in counter_names:
        metric = system_metrics.get(name)
        if metric:
            values = {}
            for value in metric.get_all():
                label_str = '_'.join(f"{k}={v}" for k, v in value.labels.items()) or 'total'
                values[label_str] = value.value
            counters[name] = values
    
    return counters


def _get_error_rate(component: str) -> float:
    """Calculate error rate for a component"""
    error_map = {
        'data_ingestion': ('data_ingestion_errors', 'data_ingestion_requests'),
        'indicator_calc': ('indicator_calc_errors', 'indicator_calc_latency'),
        'live_orders': ('live_order_errors', 'live_orders')
    }
    
    if component not in error_map:
        return 0.0
    
    error_metric_name, total_metric_name = error_map[component]
    
    error_metric = system_metrics.get(error_metric_name)
    total_metric = system_metrics.get(total_metric_name)
    
    if not error_metric or not total_metric:
        return 0.0
    
    # Sum all error counts
    total_errors = sum(v.value for v in error_metric.get_all())
    
    # Sum all request counts
    if isinstance(total_metric, type(error_metric)):  # Both are counters
        total_requests = sum(v.value for v in total_metric.get_all())
    else:
        # For histograms, get count from summary
        total_requests = sum(
            total_metric.get_summary(dict(zip(total_metric.labels, key)))['count']
            for key in total_metric._observations.keys()
        )
    
    if total_requests == 0:
        return 0.0
    
    return (total_errors / total_requests) * 100