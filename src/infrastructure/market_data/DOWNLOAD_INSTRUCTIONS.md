# Historical Data Download Instructions

## Overview
This system downloads 3 years of historical market data for the top 30 Binance Futures symbols with highest daily volume.

## Quick Start

### 1. Setup Database
```bash
# Update database credentials in scripts/run_historical_download.sh
export DATABASE_URL="postgresql://user:password@localhost/tradingbot"
```

### 2. Run Full Download (3 years, 30 symbols)
```bash
./scripts/run_historical_download.sh
```

**Expected:**
- Time: 6-10 hours
- Storage: 3-5 GB
- Candles: ~15.6 million

### 3. Test Mode (1 symbol, 7 days)
```bash
./scripts/run_historical_download.sh --test
```

### 4. Resume Interrupted Download
```bash
./scripts/run_historical_download.sh --resume
```

## Configuration Options

Edit `download_config.json`:

```json
{
  "top_symbols_count": 30,        // Number of top symbols
  "years_back": 3,                // Years of historical data
  "intervals": ["5m", "15m", "30m", "1h", "2h", "4h", "1d"],
  "parallel_workers": 4,           // Concurrent downloads
  "calculate_indicators": true,    // Calculate technical indicators
  "validate_data": true,           // Validate data integrity
  "custom_symbols": []             // Override with specific symbols
}
```

## Command Line Options

```bash
python3 -m src.infrastructure.market_data.download_historical_data \
    --symbols BTCUSDT ETHUSDT      # Specific symbols
    --intervals 5m 15m 1h           # Specific intervals
    --years 1                       # Years of data
    --no-indicators                 # Skip indicator calculation
    --no-validation                 # Skip data validation
    --non-interactive               # No user prompts
```

## Custom Symbol List

Download specific symbols:
```bash
python3 -m src.infrastructure.market_data.download_historical_data \
    --symbols BTCUSDT ETHUSDT BNBUSDT XRPUSDT ADAUSDT
```

## Data Storage

### Database Tables
- `kline_data` - OHLCV candlestick data
- `indicator_values` - Calculated indicators
- `market_metrics` - 24hr statistics
- `symbol_info` - Trading pair configuration

### Intervals Available
- **Sub-hour:** 5m, 15m, 30m
- **Hourly:** 1h, 2h, 4h
- **Daily:** 1d

### Indicators Calculated
- **Trend:** SMA (20, 50), EMA (12, 26), MACD
- **Momentum:** RSI, Stochastic
- **Volatility:** Bollinger Bands, ATR
- **Volume:** OBV, VWAP
- **Advanced:** ADX

## Progress Tracking

The download saves progress automatically:
- `download_progress.json` - Current progress
- `download_config.json` - Configuration
- `logs/` - Detailed logs

## Monitoring

### Check Progress
```bash
tail -f logs/download_*.log
```

### Database Size
```sql
SELECT pg_database_size('tradingbot') / 1024 / 1024 AS size_mb;
```

### Table Statistics
```sql
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS size,
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
```

## Data Validation

After download, validate data:
```python
from src.infrastructure.market_data.data_manager import DataManager

manager = DataManager(db_session)
report = manager.validate_data_integrity(
    symbols=['BTCUSDT'],
    intervals=['5m', '15m'],
    start_date=datetime(2021, 1, 1),
    end_date=datetime.now()
)
print(report['summary'])
```

## Troubleshooting

### Rate Limiting
- The system respects Binance's 1200 requests/minute limit
- Automatic retry with exponential backoff

### Insufficient Space
- Requires minimum 10 GB free space
- Check with: `df -h`

### Resume Failed Download
The system automatically saves progress. Simply run:
```bash
./scripts/run_historical_download.sh --resume
```

### Database Connection Issues
1. Check PostgreSQL is running: `pg_isready`
2. Verify credentials in DATABASE_URL
3. Ensure database exists: `createdb tradingbot`

### Memory Issues
For large downloads, increase Python memory:
```bash
export PYTHONMAXMEM=4G
```

## Performance Tips

1. **Use SSD Storage** - 10x faster than HDD
2. **Increase Workers** - Set `parallel_workers: 8` if you have good bandwidth
3. **Download Off-Peak** - Better performance during Asian market hours
4. **Batch Processing** - System automatically batches 1000 records

## Data Usage Examples

### Get Latest Price
```python
from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository

repo = MarketDataRepository(db_session)
latest = repo.get_latest_kline('BTCUSDT', '5m')
print(f"BTC Price: ${latest.close_price}")
```

### Get Historical Data
```python
klines = repo.get_klines(
    symbol='BTCUSDT',
    interval='1h',
    start_time=datetime(2023, 1, 1),
    end_time=datetime(2023, 12, 31)
)
```

### Get Indicators
```python
from src.infrastructure.indicators.indicator_service import IndicatorService

service = IndicatorService(db_session, event_bus)
indicators = service.get_latest_indicators('BTCUSDT', '1h')
print(f"RSI: {indicators['rsi']['value']}")
```

## Maintenance

### Clean Old Data (>365 days)
```python
deleted = repo.cleanup_old_data(days_to_keep=365)
```

### Optimize Database
```python
stats = manager.optimize_database()
```

### Backup Critical Data
```python
backup = manager.create_backup()
```

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review `download_report_*.json` for detailed statistics
3. Validate data using the DataManager validation methods