#!/usr/bin/env python3
"""
Test ATR Grid Strategy with simple data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backtesting import Backtest
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

from src.infrastructure.backtesting.strategies.atr_grid_strategy import ATRGridStrategy

# Generate simple test data
dates = pd.date_range(end=datetime.now(), periods=1000, freq='1h')
prices = 60000 + np.sin(np.arange(1000) * 0.1) * 5000 + np.random.randn(1000) * 500

df = pd.DataFrame(index=dates)
df['Close'] = prices
df['Open'] = df['Close'].shift(1).fillna(df['Close'])
df['High'] = df[['Open', 'Close']].max(axis=1) * (1 + np.random.rand(len(df)) * 0.002)
df['Low'] = df[['Open', 'Close']].min(axis=1) * (1 - np.random.rand(len(df)) * 0.002)
df['Volume'] = np.random.rand(len(df)) * 1000000 + 500000

print("Test Data Statistics:")
print(f"  Price range: ${df['Low'].min():,.2f} - ${df['High'].max():,.2f}")
print(f"  Average price: ${df['Close'].mean():,.2f}")

# Run backtest
bt = Backtest(
    df,
    ATRGridStrategy,
    cash=100000,
    commission=0.002
)

# Run with default parameters
stats = bt.run(
    atr_multiplier=0.75,
    grid_levels=5,
    max_position_size=0.1,
    use_regime=True,
    initial_regime='range'
)

print("\nBacktest Results:")
print(f"  Return: {stats['Return [%]']:.2f}%")
print(f"  Trades: {stats['# Trades']}")
print(f"  Win Rate: {stats.get('Win Rate [%]', 0):.2f}%")
print(f"  Sharpe: {stats.get('Sharpe Ratio', 0):.2f}")
print(f"  Max Drawdown: {stats['Max. Drawdown [%]']:.2f}%")

# Save plot
bt.plot(filename='test_grid_plot.html', open_browser=False)