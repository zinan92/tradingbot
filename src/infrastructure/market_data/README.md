# Market Data Infrastructure

## Overview

Complete market data infrastructure for Binance Futures trading bot, providing real-time data streaming, historical data loading, technical indicator calculation, and event-driven architecture integration.

## Components

### 1. **Binance Client** (`binance_client.py`)
- WebSocket streaming for real-time data
- REST API for historical data
- Supports multiple data types:
  - Kline/Candlestick data
  - Order book depth
  - Trade data
  - 24hr ticker
  - Mark price and funding rates

### 2. **Data Normalizer** (`data_normalizer.py`)
- Converts Binance raw data to internal format
- Creates domain events (MarketDataReceived, IndicatorCalculated)
- Handles all Binance data formats

### 3. **Market Data Service** (`market_data_service.py`)
- Orchestrates data collection
- Manages WebSocket subscriptions
- Stores data in PostgreSQL
- Publishes events to event bus

### 4. **Indicator Calculator** (`../indicators/indicator_calculator.py`)
- Calculates 20+ technical indicators:
  - Trend: SMA, EMA, MACD
  - Momentum: RSI, Stochastic, Williams %R
  - Volatility: Bollinger Bands, ATR
  - Volume: OBV, VWAP
  - Advanced: Ichimoku, ADX, CCI

### 5. **Indicator Service** (`../indicators/indicator_service.py`)
- Periodic indicator calculation
- Event publishing for calculated indicators
- Historical indicator retrieval

### 6. **Database Models** (`../persistence/postgres/market_data_tables.py`)
- KlineData: OHLCV candlestick data
- OrderBookSnapshot: Bid/ask levels
- TradeData: Executed trades
- IndicatorValue: Calculated indicators
- MarketMetrics: 24hr stats, funding rates
- SymbolInfo: Trading pair information

### 7. **Repository** (`../persistence/postgres/market_data_repository.py`)
- Database operations for all market data
- Query methods for historical data
- Data cleanup utilities

## Usage

### Basic Setup

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.market_data.market_data_service import MarketDataService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

# Database setup
engine = create_engine("postgresql://user:pass@localhost/tradingbot")
Session = sessionmaker(bind=engine)
db_session = Session()

# Event bus
event_bus = InMemoryEventBus()

# Create service
market_service = MarketDataService(
    db_session=db_session,
    event_bus=event_bus,
    api_key="your_api_key",  # Optional
    api_secret="your_secret"  # Optional
)

# Start service
await market_service.start()

# Subscribe to symbol
await market_service.subscribe_symbol(
    symbol='BTCUSDT',
    data_types=['kline', 'depth', 'trade'],
    interval='1m'
)
```

### Load Historical Data

```python
# Load 7 days of historical klines
await market_service.load_historical_data(
    symbol='BTCUSDT',
    interval='1m',
    days_back=7
)
```

### Calculate Indicators

```python
from src.infrastructure.indicators.indicator_service import IndicatorService

indicator_service = IndicatorService(db_session, event_bus)

# Start periodic calculation
await indicator_service.start_periodic_calculation(
    symbol='BTCUSDT',
    interval='1m',
    calculate_every=60  # seconds
)

# Get latest indicators
indicators = indicator_service.get_latest_indicators('BTCUSDT', '1m')
```

### Event Handling

```python
# Subscribe to events
def handle_market_data(event):
    print(f"Price: {event.symbol} @ {event.price}")

def handle_indicator(event):
    print(f"Indicator: {event.indicator_name} = {event.value}")

event_bus.subscribe('MarketDataReceived', handle_market_data)
event_bus.subscribe('IndicatorCalculated', handle_indicator)
```

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/tradingbot

# Binance API (optional for public data)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
```

### Supported Intervals

- 1m, 3m, 5m, 15m, 30m
- 1h, 2h, 4h, 6h, 8h, 12h
- 1d, 3d, 1w, 1M

### Available Indicators

**Trend Indicators:**
- SMA (20, 50, 200)
- EMA (12, 26)
- MACD

**Momentum Indicators:**
- RSI
- Stochastic (K, D)
- Williams %R
- CCI

**Volatility Indicators:**
- Bollinger Bands
- ATR

**Volume Indicators:**
- OBV
- VWAP

**Advanced:**
- Ichimoku Cloud
- ADX (+DI, -DI)
- Pivot Points
- Fibonacci Retracement

## Testing

Run tests:

```bash
# Test data normalizer
pytest tests/infrastructure/market_data/test_data_normalizer.py

# Test indicator calculator
pytest tests/infrastructure/indicators/test_indicator_calculator.py
```

## Database Schema

The infrastructure creates the following tables:

- `kline_data`: Candlestick/OHLCV data
- `orderbook_snapshots`: Order book depth
- `trade_data`: Individual trades
- `indicator_values`: Calculated indicators
- `market_metrics`: Market statistics
- `symbol_info`: Trading pair information

## Performance Considerations

1. **Data Storage**: Implements automatic cleanup of old data (configurable retention period)
2. **WebSocket Management**: Automatic reconnection with exponential backoff
3. **Batch Processing**: Indicators calculated in batches for efficiency
4. **Event Throttling**: Order book updates throttled to reduce database writes
5. **Indexing**: Database tables properly indexed for query performance

## Integration with Trading System

The market data infrastructure publishes two types of events that other contexts can subscribe to:

1. **MarketDataReceived**: Raw market data for strategies
2. **IndicatorCalculated**: Calculated indicators for signal generation

These events follow the contracts defined in `src/domain/shared/contracts/core_events.py` and maintain clean separation between contexts.

## Error Handling

- Automatic WebSocket reconnection
- Database transaction rollback on errors
- Comprehensive logging at all levels
- Statistics tracking for monitoring

## Future Enhancements

- [ ] Add more exchanges (Bybit, OKX)
- [ ] Implement data aggregation for multiple timeframes
- [ ] Add custom indicator support
- [ ] Implement data compression for storage
- [ ] Add real-time indicator alerts
- [ ] Support for options and perpetual futures data