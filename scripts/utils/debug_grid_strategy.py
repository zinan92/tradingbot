#!/usr/bin/env python3
"""
Debug Grid Strategy to understand why no trades are happening
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

from src.domain.strategy.aggregates.grid_strategy_aggregate import (
    GridStrategyAggregate,
    GridConfiguration
)
from src.domain.strategy.regime.regime_models import MarketRegime
from src.domain.trading.value_objects.symbol import Symbol

# Connect to database and load data
db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
engine = create_engine(db_url)

query = """
SELECT 
    open_time as timestamp,
    close_price as price
FROM kline_data
WHERE symbol = 'BTCUSDT'
  AND interval = '1h'
  AND open_time >= '2024-08-07'
ORDER BY open_time
LIMIT 100
"""

df = pd.read_sql(query, engine)

print("Data loaded:")
print(f"  Records: {len(df)}")
print(f"  Price range: ${df['price'].min():,.2f} - ${df['price'].max():,.2f}")
print(f"  Average price: ${df['price'].mean():,.2f}")

# Create grid strategy
config = GridConfiguration(
    atr_multiplier=0.75,
    grid_levels=5,
    max_position_size=0.1
)

strategy = GridStrategyAggregate(
    strategy_id="test",
    symbol=Symbol("BTCUSDT"),
    config=config,
    initial_regime=MarketRegime.RANGE
)

# Calculate ATR manually (simplified)
prices = df['price'].values
atr_values = []
for i in range(14, len(prices)):
    # Simple ATR approximation using price changes
    changes = np.abs(np.diff(prices[i-14:i]))
    atr = np.mean(changes)
    atr_values.append(atr)

print(f"\nATR Statistics:")
print(f"  Min ATR: ${min(atr_values):,.2f}")
print(f"  Max ATR: ${max(atr_values):,.2f}")
print(f"  Avg ATR: ${np.mean(atr_values):,.2f}")

# Test grid initialization
test_price = prices[20]
test_atr = atr_values[6]

print(f"\nTest with price=${test_price:,.2f}, ATR=${test_atr:,.2f}")

# Check if grid should activate
should_activate = strategy.should_activate_grid(test_atr, atr_values[:20])
print(f"  Should activate grid: {should_activate}")

# Update grid
strategy.update_grid(test_price, test_atr)

print(f"\nGrid State: {strategy.state}")
print(f"Reference Price: ${strategy.reference_price:,.2f}")
print(f"Grid Spacing: ${test_atr * 0.75:,.2f}")

# Display grid levels
print(f"\nBuy Levels ({len(strategy.buy_levels)}):")
for i, level in enumerate(strategy.buy_levels[:3]):
    print(f"  Level {i+1}: ${level.price:,.2f} (Active: {level.is_active})")

print(f"\nSell Levels ({len(strategy.sell_levels)}):")
for i, level in enumerate(strategy.sell_levels[:3]):
    print(f"  Level {i+1}: ${level.price:,.2f} (Active: {level.is_active})")

# Test signal detection
print("\nTesting signal detection:")
for i in range(20, 30):
    current_price = prices[i]
    buy_signal = strategy.check_buy_signal(current_price)
    sell_signal = strategy.check_sell_signal(current_price)
    
    if buy_signal or sell_signal:
        print(f"  Price ${current_price:,.2f}: BUY={buy_signal is not None}, SELL={sell_signal is not None}")

# Check position sizing
pos_size = strategy.calculate_position_size()
print(f"\nPosition size calculation: {pos_size:.4f}")