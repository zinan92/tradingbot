#!/usr/bin/env python3
"""
Demo script for Futures Backtesting Engine

Shows how to run a futures backtest with LONG/SHORT positions and leverage.
"""

from datetime import datetime
from src.infrastructure.backtesting.data_adapter import DataAdapter
from src.infrastructure.backtesting.futures_backtest_engine import FuturesBacktestEngine
from src.application.backtesting.strategies.futures_sma_cross_strategy import (
    FuturesSmaCrossStrategy,
    FuturesMeanReversionStrategy,
    FuturesMomentumStrategy
)


def run_futures_backtest_demo():
    """Run a demo futures backtest with various strategies"""
    
    print("=" * 80)
    print("FUTURES BACKTESTING ENGINE DEMO")
    print("=" * 80)
    print()
    
    # Initialize components
    data_adapter = DataAdapter()
    engine = FuturesBacktestEngine()
    
    # Fetch data (using mock data for demo)
    print("Fetching market data...")
    data = data_adapter.fetch_ohlcv(
        symbol='BTCUSDT',
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2023, 12, 31),
        interval='4h'
    )
    print(f"Loaded {len(data)} candles from {data.index[0]} to {data.index[-1]}")
    print()
    
    # Test 1: Futures SMA Crossover Strategy
    print("-" * 80)
    print("TEST 1: FUTURES SMA CROSSOVER STRATEGY (LONG & SHORT)")
    print("-" * 80)
    
    results1 = engine.run_futures_backtest(
        data=data,
        strategy_class=FuturesSmaCrossStrategy,
        initial_cash=10000,
        leverage=10,  # 10x leverage
        market_commission=0.0004,  # 0.04%
        limit_commission=0.0002,   # 0.02%
        n1=10,  # Fast SMA
        n2=20   # Slow SMA
    )
    
    print_results(results1)
    
    # Test 2: Mean Reversion Strategy
    print("\n" + "-" * 80)
    print("TEST 2: MEAN REVERSION STRATEGY (SHORT at resistance, LONG at support)")
    print("-" * 80)
    
    results2 = engine.run_futures_backtest(
        data=data,
        strategy_class=FuturesMeanReversionStrategy,
        initial_cash=10000,
        leverage=5,  # Lower leverage for mean reversion
        market_commission=0.0004,
        limit_commission=0.0002,
        bb_period=20,
        bb_std=2,
        rsi_period=14
    )
    
    print_results(results2)
    
    # Test 3: Momentum Strategy
    print("\n" + "-" * 80)
    print("TEST 3: MOMENTUM STRATEGY (MACD-based)")
    print("-" * 80)
    
    results3 = engine.run_futures_backtest(
        data=data,
        strategy_class=FuturesMomentumStrategy,
        initial_cash=10000,
        leverage=8,  # 8x leverage for momentum
        market_commission=0.0004,
        limit_commission=0.0002,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9
    )
    
    print_results(results3)
    
    # Save best performing strategy chart
    best_results = max([results1, results2, results3], 
                      key=lambda r: r.stats.get('Leveraged Return [%]', 0))
    
    with open('futures_backtest_chart.html', 'w') as f:
        f.write(best_results.chart_html)
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\nBest performing strategy chart saved to: futures_backtest_chart.html")
    print("Open this file in a browser to view the interactive plot")


def print_results(results):
    """Print formatted futures backtest results"""
    
    stats = results.stats
    futures_metrics = results.futures_metrics
    
    # Basic metrics
    print(f"\nPerformance Metrics:")
    print(f"  Base Return:           {stats.get('Base Return [%]', 0):.2f}%")
    print(f"  Leveraged Return:      {stats.get('Leveraged Return [%]', 0):.2f}%")
    print(f"  Sharpe Ratio:          {stats.get('Sharpe Ratio', 0):.2f}")
    print(f"  Max Drawdown:          {stats.get('Max. Drawdown [%]', 0):.2f}%")
    print(f"  Win Rate:              {stats.get('Win Rate [%]', 0):.2f}%")
    
    # Futures-specific metrics
    print(f"\nFutures Trading Metrics:")
    print(f"  Total Trades:          {stats.get('# Trades', 0)}")
    print(f"  Long Trades:           {futures_metrics.get('total_longs', 0)}")
    print(f"  Short Trades:          {futures_metrics.get('total_shorts', 0)}")
    print(f"  Long Win Rate:         {futures_metrics.get('long_win_rate', 0):.2f}%")
    print(f"  Short Win Rate:        {futures_metrics.get('short_win_rate', 0):.2f}%")
    print(f"  Leverage Used:         {futures_metrics.get('avg_leverage_used', 1):.1f}x")
    print(f"  Total Commission:      ${futures_metrics.get('total_commission_paid', 0):.2f}")
    
    # Risk metrics
    print(f"\nRisk Metrics:")
    print(f"  Volatility (Annual):   {stats.get('Volatility (Ann.) [%]', 0):.2f}%")
    print(f"  Sortino Ratio:         {stats.get('Sortino Ratio', 0):.2f}")
    print(f"  Calmar Ratio:          {stats.get('Calmar Ratio', 0):.2f}")
    print(f"  Kelly Criterion:       {stats.get('Kelly Criterion', 0):.4f}")


if __name__ == "__main__":
    run_futures_backtest_demo()