# Data Fetching Module Documentation

## Module Overview

The Data Fetching module is responsible for acquiring real-time and historical market data from cryptocurrency exchanges, primarily Binance Futures. It implements a robust, production-ready system with automatic reconnection, data validation, and efficient storage.

**Location**: `src/infrastructure/market_data/`  
**Status**: ✅ **90% Complete**  
**Test Coverage**: ~60%

## Architecture

```mermaid
graph TD
    A[Binance Exchange] -->|WebSocket| B[BinanceFuturesClient]
    A -->|REST API| B
    B --> C[DataNormalizer]
    C --> D[MarketDataService]
    D --> E[PostgreSQL Storage]
    D --> F[Event Bus]
    F --> G[Strategy Subscribers]
```

## Current Implementation

### Core Components

#### 1. **BinanceFuturesClient** (`binance_client.py`)
- WebSocket streaming for real-time data
- REST API for historical data
- Automatic reconnection with exponential backoff
- Rate limit handling
- Connection pooling

#### 2. **MarketDataService** (`market_data_service.py`)
- Orchestrates data collection
- Manages subscriptions
- Publishes events to subscribers
- Tracks statistics
- Handles multiple data types simultaneously

#### 3. **DataNormalizer** (`data_normalizer.py`)
- Standardizes data formats
- Validates data integrity
- Handles missing values
- Converts timestamps

#### 4. **MarketDataRepository** (`persistence/postgres/market_data_repository.py`)
- PostgreSQL storage with optimized schemas
- Batch inserts for efficiency
- Indexed queries for fast retrieval
- Data deduplication

### Supported Data Types

| Data Type | Stream | Storage | Update Frequency |
|-----------|--------|---------|------------------|
| Klines (OHLCV) | ✅ | ✅ | 1s - 1M intervals |
| Order Book | ✅ | ✅ | 100ms |
| Trades | ✅ | ✅ | Real-time |
| Ticker 24hr | ✅ | ✅ | 1s |
| Mark Price | ✅ | ✅ | 1s |
| Funding Rate | ✅ | ✅ | 8h |

### Key Features Implemented

✅ **Reliability**
- Automatic WebSocket reconnection
- Connection health monitoring
- Dead connection detection
- Graceful degradation

✅ **Performance**
- Concurrent data processing
- Batch database writes
- Connection pooling
- Async I/O throughout

✅ **Data Quality**
- Duplicate detection
- Gap identification
- Data validation
- Timestamp normalization

✅ **Monitoring**
- Real-time statistics
- Error tracking
- Latency monitoring
- Data flow metrics

## Usage Examples

### Basic Usage

```python
from src.infrastructure.market_data.market_data_service import MarketDataService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from sqlalchemy.orm import Session

# Initialize service
event_bus = InMemoryEventBus()
service = MarketDataService(
    db_session=session,
    event_bus=event_bus,
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# Start service
await service.start()

# Subscribe to symbol
await service.subscribe_symbol(
    symbol="BTCUSDT",
    data_types=["kline", "depth", "trade"],
    interval="1m"
)

# Service will now stream data and store to database
```

### Historical Data Download

```bash
# Quick download for recent data
python scripts/data_download/quick_download.py \
    --symbols BTCUSDT ETHUSDT \
    --days 30

# Full historical download
python scripts/data_download/start_full_download.py \
    --symbols BTCUSDT \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --intervals 1h 4h 1d
```

### Monitoring Data Flow

```bash
# Monitor live updates
python scripts/monitor_live_updates.py

# Check data integrity
python scripts/data_validation_tests.py
```

## Configuration

### Environment Variables

```bash
# Binance API Configuration
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
BINANCE_TESTNET=false

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost/tradingbot

# Data Collection Settings
DEFAULT_INTERVAL=1m
DEFAULT_DEPTH=20
STORE_TO_DB=true
PUBLISH_EVENTS=true
```

### Service Configuration

```python
# In market_data_service.py
self.default_interval = '1m'
self.default_depth = 20
self.store_to_db = True
self.publish_events = True
```

## Database Schema

### Kline Data Table

```sql
CREATE TABLE kline_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open_time TIMESTAMP NOT NULL,
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    close_time TIMESTAMP NOT NULL,
    quote_volume DECIMAL(20, 8),
    trades_count INTEGER,
    taker_buy_volume DECIMAL(20, 8),
    taker_buy_quote_volume DECIMAL(20, 8),
    UNIQUE(symbol, interval, open_time)
);

CREATE INDEX idx_kline_symbol_time ON kline_data(symbol, open_time DESC);
CREATE INDEX idx_kline_interval ON kline_data(interval);
```

## Integration Points

### Event Publishing

The module publishes events for:
- New kline data
- Order book updates  
- Trade executions
- Price updates

Subscribers can listen via:

```python
event_bus.subscribe("market_data.kline", handler_function)
event_bus.subscribe("market_data.trade", handler_function)
```

### Data Access

Other modules access data via:

```python
# Direct repository access
repository = MarketDataRepository(session)
klines = repository.get_klines(
    symbol="BTCUSDT",
    interval="1h",
    start_time=start,
    end_time=end
)

# Via service layer
data = await service.get_historical_data(
    symbol="BTCUSDT",
    interval="1h",
    limit=1000
)
```

## Testing

### Unit Tests
```bash
pytest tests/infrastructure/market_data/ -v
```

### Integration Tests
```bash
pytest tests/integration/market_data/ -v
```

### Performance Tests
```python
# Test WebSocket throughput
python scripts/test_binance_connection.py --benchmark
```

## Performance Metrics

| Metric | Current | Target |
|--------|---------|--------|
| WebSocket Latency | <50ms | <100ms |
| Data Processing | 1000 msg/s | 5000 msg/s |
| Database Writes | 500 rows/s | 1000 rows/s |
| Memory Usage | ~200MB | <500MB |
| Reconnection Time | <5s | <10s |

## Known Issues

1. **Rate Limiting**: Occasional 429 errors during high-frequency requests
2. **Memory Growth**: Slow memory increase with long-running sessions
3. **Gap Detection**: May miss gaps during network interruptions
4. **Timezone Handling**: Some edge cases with daylight saving transitions

## Future Enhancements

### High Priority
- [ ] Support for additional exchanges (FTX, Bybit)
- [ ] Implement data compression for storage
- [ ] Add WebSocket connection pool
- [ ] Implement circuit breaker pattern

### Medium Priority  
- [ ] Support for options data
- [ ] Implement data archival strategy
- [ ] Add data quality scoring
- [ ] Create data replay functionality

### Low Priority
- [ ] GraphQL API for data access
- [ ] Support for decentralized exchanges
- [ ] Implement custom data transformations
- [ ] Add data export functionality

## Troubleshooting

### Common Issues

**WebSocket Disconnections**
```bash
# Check connection status
curl -X GET http://localhost:8000/api/health/websocket

# Force reconnect
python scripts/utils/reconnect_websocket.py
```

**Data Gaps**
```sql
-- Find gaps in data
SELECT 
    symbol,
    interval,
    LAG(close_time) OVER (ORDER BY open_time) as prev_close,
    open_time,
    open_time - LAG(close_time) OVER (ORDER BY open_time) as gap
FROM kline_data
WHERE symbol = 'BTCUSDT'
AND gap > INTERVAL '1 minute';
```

**High Memory Usage**
```python
# Clear cache
service.clear_cache()

# Reduce subscription depth
await service.update_subscription(
    symbol="BTCUSDT",
    depth=5  # Reduce from 20
)
```

## Dependencies

- `python-binance`: Binance API wrapper
- `websockets`: WebSocket client
- `asyncio`: Async I/O
- `sqlalchemy`: Database ORM
- `pandas`: Data manipulation
- `numpy`: Numerical operations

## Related Modules

- **Indicator Calculation**: Consumes market data for technical analysis
- **Backtesting Engine**: Uses historical data for strategy testing
- **Live Trading**: Subscribes to real-time data for execution
- **Risk Management**: Monitors price data for risk metrics

## Contact & Support

For issues or questions about this module:
1. Check logs in `logs/market_data/`
2. Review test cases in `tests/infrastructure/market_data/`
3. Consult team lead for architectural decisions