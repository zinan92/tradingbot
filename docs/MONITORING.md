# Monitoring & Observability

## Overview

The trading system includes comprehensive metrics instrumentation for monitoring data ingestion, indicator calculation, backtesting, and live trading operations. All metrics are exposed in Prometheus format for integration with monitoring stacks.

## Architecture

### Core Components

1. **MetricsRegistry** (`src/infrastructure/monitoring/metrics.py`)
   - Central registry for all metrics
   - Supports Counter, Gauge, Histogram, and Summary types
   - Exports metrics in Prometheus format

2. **DataFreshnessCollector** (`src/infrastructure/monitoring/freshness_collector.py`)
   - Background service monitoring data staleness
   - Tracks age of latest data per symbol/interval
   - Alerts when data exceeds staleness threshold

3. **Instrumented Components** (`src/infrastructure/monitoring/instrumented_components.py`)
   - Wrapper classes adding metrics to core ports
   - Transparent instrumentation without modifying business logic
   - Tracks latency, errors, and throughput

## Metrics Categories

### Data Ingestion
- **data_ingestion_latency_seconds** (Histogram)
  - Latency of data fetch operations
  - Labels: source, symbol, interval
  - Buckets: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0

- **data_ingestion_requests_total** (Counter)
  - Total number of data requests
  - Labels: source, symbol, interval

- **data_ingestion_errors_total** (Counter)
  - Total number of ingestion errors
  - Labels: source, symbol, interval, error_type

### Indicator Calculation
- **indicator_calculation_latency_seconds** (Histogram)
  - Time to calculate indicators
  - Labels: indicator, symbol, interval

- **indicator_calculation_errors_total** (Counter)
  - Indicator calculation failures
  - Labels: indicator, symbol, interval, error_type

### Backtesting
- **backtest_duration_seconds** (Histogram)
  - Total backtest execution time
  - Labels: strategy, symbol, interval
  - Buckets: 1, 5, 10, 30, 60, 120, 300, 600

- **backtest_trades_total** (Counter)
  - Number of trades in backtests
  - Labels: strategy, symbol, interval, result (win/loss)

### Live Trading
- **live_order_latency_seconds** (Histogram)
  - Order submission latency
  - Labels: exchange, symbol, order_type

- **live_order_errors_total** (Counter)
  - Order submission failures
  - Labels: exchange, symbol, error_type

- **live_orders_total** (Counter)
  - Total orders submitted
  - Labels: exchange, symbol, side, status

### System Health
- **queue_depth** (Gauge)
  - Current queue sizes
  - Labels: queue_name (market_data_requests, order_queue)

- **data_freshness_seconds** (Gauge)
  - Age of latest data in seconds
  - Labels: symbol, interval
  - Critical for detecting stale data

- **system_up** (Gauge)
  - Component availability (1=up, 0=down)
  - Labels: component

## API Endpoints

### /metrics
Returns all metrics in Prometheus text format:
```
GET /metrics

# HELP data_ingestion_latency_seconds Latency of data ingestion operations
# TYPE data_ingestion_latency_seconds histogram
data_ingestion_latency_seconds_bucket{source="binance",symbol="BTCUSDT",interval="5m",le="0.005"} 0
data_ingestion_latency_seconds_bucket{source="binance",symbol="BTCUSDT",interval="5m",le="0.01"} 2
...
```

### /metrics/health
Returns system health summary:
```json
{
  "status": "healthy",
  "components": {
    "data_ingestion": {"status": "up", "value": 1},
    "indicator_calc": {"status": "up", "value": 1},
    "backtest": {"status": "up", "value": 1},
    "live_trading": {"status": "up", "value": 1}
  },
  "data_freshness": {
    "BTCUSDT:5m": {
      "age_seconds": 15.2,
      "is_stale": false,
      "last_update": "2025-08-10T12:00:00"
    }
  },
  "queue_depths": {
    "market_data_requests": 5,
    "order_queue": 2
  },
  "error_rates": {
    "data_ingestion": 0.5,
    "indicator_calc": 0.0,
    "live_orders": 1.2
  }
}
```

### /metrics/freshness
Detailed data freshness information:
```json
{
  "summary": {
    "BTCUSDT:5m": {
      "age_seconds": 15.2,
      "is_stale": false,
      "last_update": "2025-08-10T12:00:00"
    }
  },
  "staleness_threshold": 300,
  "update_interval": 10
}
```

### /metrics/latency/{component}
Component-specific latency metrics:
```json
{
  "component": "data_ingestion",
  "metric": "data_ingestion_latency_seconds",
  "summaries": {
    "source=binance_symbol=BTCUSDT_interval=5m": {
      "count": 1000,
      "sum": 125.5,
      "avg": 0.1255,
      "p50": 0.110,
      "p95": 0.250,
      "p99": 0.450
    }
  }
}
```

## Usage Examples

### 1. Instrumenting a Component

```python
from src.infrastructure.monitoring.instrumented_components import InstrumentedMarketDataPort

# Wrap existing port
original_port = BinanceMarketDataPort()
instrumented_port = InstrumentedMarketDataPort(original_port)

# Use normally - metrics collected automatically
candles = await instrumented_port.get_candles(
    symbol='BTCUSDT',
    interval='5m',
    start_time=start,
    end_time=end
)
```

### 2. Starting Freshness Monitoring

```python
from src.infrastructure.monitoring.freshness_collector import DataFreshnessCollector

# Create collector
collector = DataFreshnessCollector(
    market_data_port=market_data_port,
    update_interval=10,  # Check every 10 seconds
    staleness_threshold=300  # Data stale after 5 minutes
)

# Add symbols to monitor
collector.add_symbol('BTCUSDT', '5m')
collector.add_symbol('ETHUSDT', '1h')

# Start monitoring
await collector.start()
```

### 3. Custom Metric Recording

```python
from src.infrastructure.monitoring.metrics import system_metrics, Timer

# Record custom latency
with Timer(system_metrics['backtest_duration'], {'strategy': 'MyStrategy'}):
    result = await run_backtest()

# Increment counter
system_metrics['backtest_trades'].inc(
    value=10,
    labels={'strategy': 'MyStrategy', 'result': 'win'}
)

# Update gauge
system_metrics['queue_depth'].set(
    value=25,
    labels={'queue_name': 'order_queue'}
)
```

## Prometheus Configuration

Add to `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'trading_system'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 15s
    metrics_path: '/metrics'
```

## Grafana Dashboards

### Key Panels

1. **Data Freshness Heatmap**
   - Shows age of data across all symbols
   - Red indicates stale data requiring attention

2. **Latency Percentiles**
   - P50, P95, P99 for each component
   - Helps identify performance degradation

3. **Error Rate**
   - Percentage of failed operations
   - Separate panels for ingestion, calculation, trading

4. **Queue Depth**
   - Real-time queue sizes
   - Alerts when queues back up

5. **Trading Activity**
   - Orders per minute
   - Win/loss ratio
   - Fill rate

## Alerting Rules

### Critical Alerts

```yaml
groups:
  - name: trading_critical
    rules:
      - alert: DataStale
        expr: data_freshness_seconds > 600
        for: 5m
        annotations:
          summary: "Data for {{ $labels.symbol }}:{{ $labels.interval }} is stale"
          
      - alert: HighErrorRate
        expr: rate(data_ingestion_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High ingestion error rate: {{ $value }}"
          
      - alert: OrderQueueBackup
        expr: queue_depth{queue_name="order_queue"} > 100
        for: 2m
        annotations:
          summary: "Order queue backed up: {{ $value }} orders"
```

### Warning Alerts

```yaml
      - alert: SlowBacktest
        expr: histogram_quantile(0.95, backtest_duration_seconds) > 300
        for: 10m
        annotations:
          summary: "Backtests taking too long (P95 > 5min)"
          
      - alert: LowFillRate
        expr: rate(live_orders_total{status="filled"}[5m]) / rate(live_orders_total[5m]) < 0.8
        for: 10m
        annotations:
          summary: "Order fill rate below 80%"
```

## Testing

### Unit Tests
```bash
pytest tests/infrastructure/monitoring/test_metrics.py -v
```

### Integration Tests
- Verify metrics registry has expected series
- Test staleness simulation
- Validate Prometheus export format

### Manual Testing
```bash
# Run metrics demo
python scripts/demo_metrics.py

# Check metrics endpoint
curl http://localhost:8000/metrics

# Simulate staleness
curl -X POST http://localhost:8000/metrics/freshness/simulate \
  -d '{"symbol": "BTCUSDT", "interval": "5m", "age_seconds": 600}'
```

## Performance Considerations

1. **Histogram Buckets**: Use appropriate bucket boundaries for expected latencies
2. **Label Cardinality**: Avoid high-cardinality labels (e.g., order IDs)
3. **Update Frequency**: Balance freshness monitoring interval vs. overhead
4. **Memory Usage**: Histograms store all observations; consider retention limits
5. **Export Performance**: Cache Prometheus export for high-traffic scenarios

## Best Practices

1. **Instrument at Boundaries**: Add metrics at system boundaries (ports)
2. **Use Consistent Labels**: Maintain consistent label naming across metrics
3. **Track Business Metrics**: Include domain-specific metrics (win rate, Sharpe)
4. **Set Reasonable Thresholds**: Avoid alert fatigue with appropriate thresholds
5. **Document Metrics**: Include metric descriptions and expected ranges
6. **Version Metrics**: Include version labels for A/B testing

## Future Enhancements

- [ ] Add OpenTelemetry support for distributed tracing
- [ ] Implement metric aggregation for high-frequency data
- [ ] Add custom business metrics (PnL tracking, strategy performance)
- [ ] Create automated dashboard generation
- [ ] Implement anomaly detection on metrics
- [ ] Add metric-based circuit breakers