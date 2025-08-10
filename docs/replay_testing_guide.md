# Replay Testing Guide

## Overview

The replay testing system enables deterministic end-to-end testing by recording and replaying market data. This ensures that tests produce identical results across multiple runs, making it possible to verify that changes don't affect trading behavior unexpectedly.

## Architecture

### Components

1. **MarketDataPort Interface** (`src/domain/ports/market_data_port.py`)
   - Abstract interface for all market data sources
   - Defines contracts for ticks, klines, and streaming data
   - Supports both live and replay adapters

2. **ReplayAdapter** (`src/infrastructure/market_data/replay_adapter.py`)
   - Reads recorded market data from files
   - Supports deterministic and real-time playback modes
   - Memory-efficient streaming with configurable buffers

3. **DataRecorder** (`src/infrastructure/market_data/data_recorder.py`)
   - Records live market data to files
   - Supports compression and buffered writing
   - Creates session metadata for tracking

4. **DeterministicClock** (`src/infrastructure/market_data/deterministic_clock.py`)
   - Provides controlled time progression
   - Ensures reproducible time-based operations
   - Supports different playback speeds

5. **MetricsValidator** (`src/infrastructure/monitoring/metrics_validator.py`)
   - Validates metrics consistency across runs
   - Calculates deterministic hashes
   - Generates validation reports

## Recording Market Data

### Basic Recording

```python
from src.infrastructure.market_data.data_recorder import DataRecorder
from src.infrastructure.market_data.binance_adapter import BinanceAdapter

# Create recorder with live data source
source = BinanceAdapter()
recorder = DataRecorder(
    source_adapter=source,
    output_path="data/recordings",
    compress=True
)

# Start recording
session_id = await recorder.start_recording(
    symbols=["BTCUSDT", "ETHUSDT"],
    timeframes=[TimeFrame.M1, TimeFrame.M5],
    duration=timedelta(hours=24)
)

# Recording runs in background...

# Stop and save
session = await recorder.stop_recording()
print(f"Recorded {session.tick_count} ticks, {session.kline_count} klines")
```

### Recording Session Management

```python
# Create combined file for easier distribution
combined_file = await recorder.create_combined_file(session_id)
print(f"Combined data saved to: {combined_file}")

# Get recording statistics
stats = recorder.get_statistics()
print(f"Total recorded: {stats['total_ticks']} ticks")
```

## Replay Testing

### Basic Replay Test

```python
from src.infrastructure.market_data.replay_adapter import ReplayAdapter
from src.domain.ports.market_data_port import MarketDataConfig, TimeFrame

# Create replay adapter
replay = ReplayAdapter("data/replay/test")

# Configure for deterministic testing
config = MarketDataConfig(
    symbols=["BTCUSDT"],
    timeframes=[TimeFrame.M5],
    deterministic=True,  # Critical for reproducibility
    replay_speed=0       # As fast as possible
)

# Connect and load data
await replay.connect(config)

# Stream ticks deterministically
async for tick in replay.stream_ticks(["BTCUSDT"]):
    # Process tick...
    pass
```

### E2E Test Framework

```python
from tests.e2e.test_deterministic_replay import DeterministicTestFramework

# Create framework
framework = DeterministicTestFramework()

# Setup test environment
await framework.setup(
    symbols=["BTCUSDT", "ETHUSDT"],
    timeframes=[TimeFrame.M5, TimeFrame.M15]
)

# Run test with strategy
result = await framework.run_test(
    strategy_name="SMAStrategy",
    strategy_params={
        "fast_period": 10,
        "slow_period": 20,
        "position_size": 0.1
    },
    test_duration=timedelta(hours=1)
)

print(f"Test complete: PnL={result['metrics']['total_pnl']}")
print(f"Metrics hash: {result['metrics_hash']}")
```

### Verifying Determinism

```python
# Run multiple iterations to verify determinism
deterministic = await framework.run_multiple_iterations(
    strategy_name="SMAStrategy",
    strategy_params={"fast_period": 10, "slow_period": 20},
    test_duration=timedelta(hours=1),
    iterations=3
)

if deterministic:
    print("✓ Test is deterministic")
else:
    print("✗ Test is NOT deterministic")
```

## File Formats

### Combined Data File

```json
{
  "metadata": {
    "session_id": "20240115_120000",
    "start_time": "2024-01-15T12:00:00",
    "end_time": "2024-01-15T13:00:00",
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "timeframes": ["1m", "5m"]
  },
  "ticks": {
    "BTCUSDT": [
      {
        "symbol": "BTCUSDT",
        "timestamp": "2024-01-15T12:00:00",
        "bid": "50000.00",
        "ask": "50001.00",
        "last": "50000.50",
        "volume": "0.1"
      }
    ]
  },
  "klines": {
    "BTCUSDT": {
      "1m": [
        {
          "symbol": "BTCUSDT",
          "timeframe": "1m",
          "timestamp": "2024-01-15T12:00:00",
          "open": "50000.00",
          "high": "50100.00",
          "low": "49900.00",
          "close": "50050.00",
          "volume": "10.5",
          "trades": 100
        }
      ]
    }
  }
}
```

## Metrics Validation

### Comparing Metrics

```python
from src.infrastructure.monitoring.metrics_validator import MetricsValidator

validator = MetricsValidator(tolerance=0.0)  # Exact match required

# Validate two metric sets
is_valid, differences = validator.validate_metrics(metrics1, metrics2)

if not is_valid:
    print("Differences found:")
    for diff in differences:
        print(f"  - {diff}")
```

### Generating Reports

```python
# Generate validation report
report = validator.generate_report(output_path=Path("validation_report.txt"))
print(report)

# Compare multiple strategies
comparator = MetricsComparator()
comparison = comparator.compare_strategies({
    "SMA": sma_results,
    "RSI": rsi_results,
    "MACD": macd_results
})

print(f"Deterministic strategies: {comparison['determinism']}")
```

## Best Practices

### 1. Recording Data

- **Record during low volatility**: Reduces file size while maintaining test coverage
- **Use compression**: Saves 80-90% disk space with minimal performance impact
- **Record multiple timeframes**: Enables testing different strategy types
- **Include metadata**: Track recording conditions for reproducibility

### 2. Test Design

- **Use deterministic mode**: Set `deterministic=True` in config
- **Avoid random operations**: No `random.random()` in strategies during tests
- **Mock external services**: Replace API calls with deterministic responses
- **Control time**: Use `DeterministicClock` for time-based operations

### 3. Validation

- **Run multiple iterations**: Verify determinism with at least 3 runs
- **Compare hashes**: Use metrics hashes for quick validation
- **Check key metrics**: Focus on PnL, trades, and risk metrics
- **Save results**: Keep metrics.json for regression testing

### 4. Performance

- **Use appropriate buffer sizes**: Balance memory vs I/O operations
- **Compress large files**: Use gzip for files > 10MB
- **Stream data**: Don't load entire datasets into memory
- **Parallelize tests**: Run independent tests concurrently

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Replay Tests

on: [push, pull_request]

jobs:
  replay-test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Setup Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Download replay data
      run: |
        wget https://storage.example.com/replay-data.tar.gz
        tar -xzf replay-data.tar.gz -C data/replay/
    
    - name: Run deterministic tests
      run: python -m pytest tests/e2e/test_deterministic_replay.py -v
    
    - name: Validate metrics
      run: |
        python scripts/validate_metrics.py \
          --baseline metrics_baseline.json \
          --current test_results/metrics.json
    
    - name: Upload results
      uses: actions/upload-artifact@v2
      with:
        name: replay-test-results
        path: test_results/
```

## Troubleshooting

### Common Issues

1. **Non-deterministic results**
   - Check for random operations in strategy
   - Verify time handling uses deterministic clock
   - Ensure no external API calls during replay

2. **File not found errors**
   - Verify replay data exists in expected location
   - Check file permissions
   - Ensure correct compression format

3. **Memory issues with large files**
   - Use streaming instead of loading entire file
   - Increase buffer size for better performance
   - Consider splitting large recordings

4. **Slow replay performance**
   - Use deterministic mode (replay_speed=0)
   - Optimize data structures
   - Profile for bottlenecks

## Example Test Script

```python
#!/usr/bin/env python3
"""
Example replay test script for CI/CD.
"""

import asyncio
import sys
from pathlib import Path
from datetime import timedelta

from tests.e2e.test_deterministic_replay import DeterministicTestFramework

async def main():
    # Create framework
    framework = DeterministicTestFramework()
    
    try:
        # Setup
        await framework.setup(
            symbols=["BTCUSDT"],
            timeframes=[TimeFrame.M5]
        )
        
        # Run test
        deterministic = await framework.run_multiple_iterations(
            "SMAStrategy",
            {"fast_period": 10, "slow_period": 20},
            timedelta(hours=1),
            iterations=3
        )
        
        # Save results
        await framework.save_results()
        
        # Exit with appropriate code
        sys.exit(0 if deterministic else 1)
        
    finally:
        await framework.teardown()

if __name__ == "__main__":
    asyncio.run(main())
```

## Summary

The replay testing system provides:

1. **Deterministic Testing**: Identical results across multiple runs
2. **Regression Detection**: Catch unintended behavior changes
3. **Performance Validation**: Ensure strategies meet expectations
4. **CI/CD Integration**: Automated testing in pipelines
5. **Debug Capability**: Reproduce production issues locally

By following this guide, you can ensure your trading strategies behave consistently and correctly across different environments and code changes.