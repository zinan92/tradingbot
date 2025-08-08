# 🚀 How to Execute the Historical Data Download

## Current Status
You already have **145,550 candles** in your database:
- **BTCUSDT**: 75,425 candles (~3 years, 30m interval)
- **BNBUSDT**: 52,560 candles (~3 years, 30m interval)  
- **ETHUSDT**: 17,565 candles (~1 year, mixed intervals)
- **Database size**: 54 MB

## Quick Test (Already Working ✅)
```bash
# Download 7 days of data for 2 symbols (takes 1 minute)
python3 quick_download.py
```

## Full 3-Year Download for Top 30 Symbols

### Option 1: Interactive Mode (Recommended)
```bash
# This will ask for confirmation and show progress
python3 start_full_download.py
```

### Option 2: Auto-approve Mode
```bash
# Skip all confirmations
python3 start_full_download.py --yes
```

### Option 3: Using the Main Script
```bash
# Full control with configuration file
python3 -m src.infrastructure.market_data.download_historical_data \
    --config download_config.json \
    --non-interactive
```

### Option 4: Custom Download
```bash
# Download specific symbols
python3 -m src.infrastructure.market_data.download_historical_data \
    --symbols BTCUSDT ETHUSDT BNBUSDT SOLUSDT ADAUSDT \
    --intervals 5m 15m 1h 4h 1d \
    --years 1 \
    --non-interactive
```

## What to Expect

### For Full 3-Year, 30 Symbols Download:
- **Time**: 6-10 hours
- **Storage**: 3-5 GB
- **Candles**: ~15.6 million
- **Intervals**: 5m, 15m, 30m, 1h, 2h, 4h, 1d
- **Top symbols**: Will be fetched automatically by 24hr volume

### Progress Tracking:
The download will show:
```
📦 Batch 1/6
   Symbols: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
   ✅ Downloaded 1,234,567 candles
   Success rate: 35/35
```

## Resume Interrupted Download

If the download is interrupted:
```bash
# The system automatically saves progress
# Just run the same command again:
python3 start_full_download.py
```

## Monitor Progress

### In another terminal:
```bash
# Check database size
psql -d tradingbot -c "SELECT COUNT(*) FROM kline_data;"

# Check current data
python3 check_data.py

# Watch logs
tail -f download_*.log
```

## After Download Completes

### Verify Data:
```bash
python3 check_data.py
```

### Use the Data:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.persistence.postgres.market_data_repository import MarketDataRepository

engine = create_engine('postgresql://localhost/tradingbot')
Session = sessionmaker(bind=engine)
session = Session()

repo = MarketDataRepository(session)

# Get latest price
latest = repo.get_latest_kline('BTCUSDT', '1h')
print(f"BTC: ${latest.close_price:,.2f}")

# Get historical data
from datetime import datetime, timedelta
klines = repo.get_klines(
    'BTCUSDT', '1h',
    start_time=datetime.now() - timedelta(days=30)
)
```

## Troubleshooting

### If download fails:
1. Check internet connection
2. Check disk space: `df -h` (need 10+ GB free)
3. Check PostgreSQL: `pg_isready`
4. Check logs: `tail -100 download_*.log`

### Rate limit errors:
- The system automatically handles rate limits
- If persistent, wait 1 minute and retry

### Database connection errors:
```bash
# Ensure PostgreSQL is running
brew services start postgresql@15  # macOS

# Check connection
psql -d tradingbot -c "SELECT 1;"
```

## Configuration

Edit `download_config.json` to customize:
```json
{
  "top_symbols_count": 30,    # Number of symbols
  "years_back": 3,             # Years of history
  "intervals": ["5m", "15m", "30m", "1h", "2h", "4h", "1d"],
  "parallel_workers": 4,       # Concurrent downloads
  "calculate_indicators": true # Calculate indicators
}
```

## Ready to Start?

1. **Test first**: `python3 quick_download.py` ✅ (Already working!)
2. **Then full download**: `python3 start_full_download.py`

The system will:
- ✅ Fetch top 30 symbols by volume
- ✅ Download 3 years of historical data
- ✅ Calculate 20+ technical indicators
- ✅ Validate data integrity
- ✅ Save progress (resumable)
- ✅ Generate detailed report

Good luck! 🚀