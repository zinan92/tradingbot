#!/usr/bin/env python3
"""
Script to create sample replay data for testing.

Generates realistic market data files for deterministic testing.
"""

import json
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import random
import math

# Setup paths
OUTPUT_DIR = Path("data/replay/test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_realistic_price(
    base_price: float,
    time_offset: float,
    volatility: float = 0.02
) -> float:
    """Generate realistic price with trends and noise."""
    # Add trend component
    trend = math.sin(time_offset / 100) * base_price * 0.1
    
    # Add volatility
    noise = random.gauss(0, base_price * volatility)
    
    # Add intraday pattern
    intraday = math.sin(time_offset / 20) * base_price * 0.01
    
    return max(base_price * 0.5, base_price + trend + noise + intraday)


def create_sample_ticks(
    symbol: str,
    start_time: datetime,
    duration_hours: int = 24,
    base_price: float = 50000.0
) -> list:
    """Create sample tick data."""
    ticks = []
    current_time = start_time
    tick_interval = timedelta(seconds=1)
    
    for i in range(duration_hours * 3600):
        # Generate price
        mid_price = generate_realistic_price(base_price, i)
        
        # Create bid/ask spread
        spread = mid_price * 0.0002  # 0.02% spread
        bid = mid_price - spread / 2
        ask = mid_price + spread / 2
        
        # Generate volume
        volume = abs(random.gauss(100, 50))
        
        tick = {
            "symbol": symbol,
            "timestamp": current_time.isoformat(),
            "bid": str(round(bid, 2)),
            "ask": str(round(ask, 2)),
            "last": str(round(mid_price, 2)),
            "volume": str(round(volume, 8))
        }
        
        ticks.append(tick)
        current_time += tick_interval
    
    return ticks


def create_sample_klines(
    symbol: str,
    timeframe: str,
    start_time: datetime,
    duration_hours: int = 24,
    base_price: float = 50000.0
) -> list:
    """Create sample kline data."""
    klines = []
    
    # Determine interval
    intervals = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1)
    }
    
    interval = intervals.get(timeframe, timedelta(minutes=5))
    num_klines = int(duration_hours * 3600 / interval.total_seconds())
    
    current_time = start_time
    
    for i in range(num_klines):
        # Generate OHLC
        open_price = generate_realistic_price(base_price, i * 10)
        
        # Generate high/low with realistic wicks
        high = open_price * random.uniform(1.001, 1.01)
        low = open_price * random.uniform(0.99, 0.999)
        
        # Close between high and low
        close = random.uniform(low, high)
        
        # Volume
        volume = abs(random.gauss(1000, 500))
        trades = int(abs(random.gauss(50, 20)))
        
        kline = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": current_time.isoformat(),
            "open": str(round(open_price, 2)),
            "high": str(round(high, 2)),
            "low": str(round(low, 2)),
            "close": str(round(close, 2)),
            "volume": str(round(volume, 8)),
            "trades": trades
        }
        
        klines.append(kline)
        current_time += interval
    
    return klines


def create_combined_data_file():
    """Create a combined data file with multiple symbols."""
    start_time = datetime(2024, 1, 15, 0, 0, 0)
    
    # Generate data for multiple symbols
    symbols_config = [
        {"symbol": "BTCUSDT", "base_price": 50000.0},
        {"symbol": "ETHUSDT", "base_price": 3000.0},
        {"symbol": "BNBUSDT", "base_price": 500.0}
    ]
    
    combined_data = {
        "metadata": {
            "session_id": "test_replay_001",
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(hours=24)).isoformat(),
            "symbols": [cfg["symbol"] for cfg in symbols_config],
            "timeframes": ["1m", "5m", "15m"],
            "description": "Sample replay data for deterministic testing"
        },
        "ticks": {},
        "klines": {}
    }
    
    print("Generating sample replay data...")
    
    for config in symbols_config:
        symbol = config["symbol"]
        base_price = config["base_price"]
        
        print(f"  Generating data for {symbol}...")
        
        # Generate ticks (subset for file size)
        ticks = create_sample_ticks(symbol, start_time, 1, base_price)
        combined_data["ticks"][symbol] = ticks[:3600]  # 1 hour of ticks
        
        # Generate klines
        combined_data["klines"][symbol] = {}
        for timeframe in ["1m", "5m", "15m"]:
            klines = create_sample_klines(
                symbol, timeframe, start_time, 24, base_price
            )
            combined_data["klines"][symbol][timeframe] = klines
    
    # Save uncompressed
    output_file = OUTPUT_DIR / "sample_replay_data.json"
    with open(output_file, 'w') as f:
        json.dump(combined_data, f, indent=2)
    
    print(f"Created: {output_file}")
    
    # Save compressed
    output_file_gz = OUTPUT_DIR / "sample_replay_data.json.gz"
    with gzip.open(output_file_gz, 'wt') as f:
        json.dump(combined_data, f, indent=2)
    
    print(f"Created: {output_file_gz}")
    
    # Create individual symbol files for replay adapter
    for config in symbols_config:
        symbol = config["symbol"]
        
        symbol_data = {
            "metadata": combined_data["metadata"],
            "ticks": combined_data["ticks"].get(symbol, []),
            "klines": combined_data["klines"].get(symbol, {})
        }
        
        # Save individual file
        symbol_file = OUTPUT_DIR / f"{symbol}.json"
        with open(symbol_file, 'w') as f:
            json.dump(symbol_data, f, indent=2)
        
        print(f"Created: {symbol_file}")


def create_minimal_test_file():
    """Create a minimal test file for unit tests."""
    start_time = datetime(2024, 1, 15, 12, 0, 0)
    
    minimal_data = {
        "metadata": {
            "session_id": "minimal_test",
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(minutes=5)).isoformat()
        },
        "ticks": [
            {
                "symbol": "BTCUSDT",
                "timestamp": start_time.isoformat(),
                "bid": "49999.00",
                "ask": "50001.00",
                "last": "50000.00",
                "volume": "0.1"
            },
            {
                "symbol": "BTCUSDT",
                "timestamp": (start_time + timedelta(seconds=1)).isoformat(),
                "bid": "49998.00",
                "ask": "50002.00",
                "last": "50000.00",
                "volume": "0.2"
            }
        ],
        "klines": {
            "1m": [
                {
                    "symbol": "BTCUSDT",
                    "timeframe": "1m",
                    "timestamp": start_time.isoformat(),
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
    
    output_file = OUTPUT_DIR / "BTCUSDT_minimal.json"
    with open(output_file, 'w') as f:
        json.dump(minimal_data, f, indent=2)
    
    print(f"Created minimal test file: {output_file}")


def verify_files():
    """Verify created files can be loaded."""
    print("\nVerifying files...")
    
    for file_path in OUTPUT_DIR.glob("*.json*"):
        try:
            if file_path.suffix == ".gz":
                with gzip.open(file_path, 'rt') as f:
                    data = json.load(f)
            else:
                with open(file_path, 'r') as f:
                    data = json.load(f)
            
            # Count data points
            tick_count = 0
            kline_count = 0
            
            if "ticks" in data:
                if isinstance(data["ticks"], dict):
                    for symbol_ticks in data["ticks"].values():
                        tick_count += len(symbol_ticks)
                else:
                    tick_count = len(data["ticks"])
            
            if "klines" in data:
                if isinstance(data["klines"], dict):
                    for symbol_klines in data["klines"].values():
                        if isinstance(symbol_klines, dict):
                            for tf_klines in symbol_klines.values():
                                kline_count += len(tf_klines)
                        else:
                            kline_count += len(symbol_klines)
                else:
                    kline_count = len(data["klines"])
            
            file_size = file_path.stat().st_size / 1024  # KB
            
            print(f"  ✓ {file_path.name}: {tick_count} ticks, {kline_count} klines, {file_size:.1f} KB")
            
        except Exception as e:
            print(f"  ✗ {file_path.name}: Error loading - {e}")


def main():
    """Create all sample files."""
    print("Creating sample replay data files...")
    print(f"Output directory: {OUTPUT_DIR}")
    print()
    
    # Create main sample data
    create_combined_data_file()
    
    # Create minimal test file
    create_minimal_test_file()
    
    # Verify all files
    verify_files()
    
    print("\n✓ Sample replay data created successfully!")
    print(f"Files are located in: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()