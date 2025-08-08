#!/usr/bin/env python3
"""
Simple Grid Strategy Test - Minimal implementation
"""

import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from sqlalchemy import create_engine
import os

# Load real data
db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
engine = create_engine(db_url)

query = """
SELECT 
    open_time as timestamp,
    open_price as "Open",
    high_price as "High",
    low_price as "Low",
    close_price as "Close",
    volume as "Volume"
FROM kline_data
WHERE symbol = 'BTCUSDT'
  AND interval = '1h'
  AND open_time >= '2024-01-01'
  AND open_time <= '2024-02-01'
ORDER BY open_time
"""

df = pd.read_sql(query, engine, parse_dates=['timestamp'], index_col='timestamp')

print(f"Data loaded: {len(df)} rows")
print(f"Price range: ${df['Low'].min():,.2f} - ${df['High'].max():,.2f}")


class SimpleGridStrategy(Strategy):
    """Simplified grid strategy for testing"""
    
    grid_spacing_pct = 1.0  # 1% spacing
    n_grids = 5
    
    def init(self):
        self.grid_set = False
        self.buy_levels = []
        self.sell_levels = []
        self.last_signal = None
        
    def next(self):
        current_price = self.data.Close[-1]
        
        # Initialize grid on first tick
        if not self.grid_set:
            # Set grid levels
            for i in range(1, self.n_grids + 1):
                buy_price = current_price * (1 - self.grid_spacing_pct * i / 100)
                sell_price = current_price * (1 + self.grid_spacing_pct * i / 100)
                self.buy_levels.append(buy_price)
                self.sell_levels.append(sell_price)
            
            self.grid_set = True
            print(f"Grid initialized at price ${current_price:,.2f}")
            print(f"  Buy levels: {[f'${p:,.2f}' for p in self.buy_levels[:3]]}")
            print(f"  Sell levels: {[f'${p:,.2f}' for p in self.sell_levels[:3]]}")
            return
        
        # Check for buy signals
        for buy_level in self.buy_levels:
            if current_price <= buy_level and self.last_signal != 'BUY':
                if not self.position:
                    self.buy()
                    self.last_signal = 'BUY'
                    print(f"BUY at ${current_price:,.2f}")
                    break
        
        # Check for sell signals
        for sell_level in self.sell_levels:
            if current_price >= sell_level and self.last_signal != 'SELL':
                if self.position:
                    self.position.close()
                    self.last_signal = 'SELL'
                    print(f"SELL at ${current_price:,.2f}")
                    break


# Run backtest
bt = Backtest(df, SimpleGridStrategy, cash=100000, commission=0.002)
stats = bt.run()

print("\nBacktest Results:")
print(f"  Return: {stats['Return [%]']:.2f}%")
print(f"  Trades: {stats['# Trades']}")
print(f"  Win Rate: {stats.get('Win Rate [%]', 0):.2f}%")
print(f"  Sharpe: {stats.get('Sharpe Ratio', 0):.2f}")
print(f"  Max Drawdown: {stats['Max. Drawdown [%]']:.2f}%")