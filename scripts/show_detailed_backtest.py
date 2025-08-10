#!/usr/bin/env python3
"""
Show detailed metrics for Bitcoin EMA Crossing backtest
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.backtesting.backtest_engine import BacktestEngine
from src.infrastructure.backtesting.data_adapter import DataAdapter
from src.application.backtesting.strategies.ema_cross_strategy import EMACrossStrategy


def run_bitcoin_ema_backtest():
    """Run Bitcoin EMA Crossing backtest with detailed metrics"""
    
    print("=" * 80)
    print("DETAILED BACKTEST: Bitcoin EMA Crossing Strategy")
    print("=" * 80)
    
    # Configuration
    symbol = "BTCUSDT"
    interval = "5m"
    start_date = datetime.now() - timedelta(days=150)  # 5 months
    end_date = datetime.now()
    initial_capital = 10000
    commission = 0.001  # 0.1% commission
    
    # Strategy parameters
    strategy_params = {
        'fast_period': 12,
        'slow_period': 26,
        'stop_loss_pct': 0.02,  # 2% stop loss
        'take_profit_pct': 0.05,  # 5% take profit
        'position_size': 0.95,  # Use 95% of capital
        'use_volume_filter': False,
        'trailing_stop_pct': 0.03  # 3% trailing stop
    }
    
    print(f"\nConfiguration:")
    print(f"  Symbol: {symbol}")
    print(f"  Interval: {interval}")
    print(f"  Period: {start_date.date()} to {end_date.date()}")
    print(f"  Duration: {(end_date - start_date).days} days")
    print(f"  Initial Capital: ${initial_capital:,.2f}")
    print(f"  Commission: {commission:.2%}")
    
    print(f"\nStrategy Parameters:")
    for key, value in strategy_params.items():
        if isinstance(value, float) and value < 1:
            print(f"  {key}: {value:.2%}")
        else:
            print(f"  {key}: {value}")
    
    # Initialize components
    data_adapter = DataAdapter(None)  # Use sample data
    backtest_engine = BacktestEngine()
    
    # Load data
    print(f"\nLoading data...")
    data = data_adapter.fetch_ohlcv(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date
    )
    
    print(f"  Loaded {len(data)} candles")
    print(f"  Date range: {data.index[0]} to {data.index[-1]}")
    print(f"  Price range: ${data['Close'].min():.2f} - ${data['Close'].max():.2f}")
    
    # Run backtest
    print(f"\nRunning backtest...")
    results = backtest_engine.run_backtest(
        data=data,
        strategy_class=EMACrossStrategy,
        initial_cash=initial_capital,
        commission=commission,
        **strategy_params
    )
    
    # Display all metrics
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS - ALL METRICS")
    print("=" * 80)
    
    stats = results.stats
    
    # Group metrics by category
    print("\n📅 TIME METRICS:")
    print(f"  Start                          {stats.get('Start', 'N/A')}")
    print(f"  End                            {stats.get('End', 'N/A')}")
    print(f"  Duration                       {stats.get('Duration', 'N/A')}")
    print(f"  Exposure Time [%]              {stats.get('Exposure Time [%]', 0):.2f}%")
    
    print("\n💰 RETURN METRICS:")
    print(f"  Initial Capital                ${initial_capital:,.2f}")
    print(f"  Equity Final [$]               ${stats.get('Equity Final [$]', 0):,.2f}")
    print(f"  Equity Peak [$]                ${stats.get('Equity Peak [$]', 0):,.2f}")
    print(f"  Return [%]                     {stats.get('Return [%]', 0):,.2f}%")
    print(f"  Buy & Hold Return [%]          {stats.get('Buy & Hold Return [%]', 0):,.2f}%")
    print(f"  Return (Ann.) [%]              {stats.get('Return (Ann.) [%]', 0):,.2f}%")
    print(f"  CAGR [%]                       {stats.get('CAGR [%]', 0):,.2f}%")
    
    print("\n📊 RISK METRICS:")
    print(f"  Volatility (Ann.) [%]          {stats.get('Volatility (Ann.) [%]', 0):.2f}%")
    print(f"  Sharpe Ratio                   {stats.get('Sharpe Ratio', 0):.3f}")
    print(f"  Sortino Ratio                  {stats.get('Sortino Ratio', 0):.3f}")
    print(f"  Calmar Ratio                   {stats.get('Calmar Ratio', 0):.3f}")
    print(f"  Alpha [%]                      {stats.get('Alpha [%]', 0):.2f}%")
    print(f"  Beta                           {stats.get('Beta', 0):.3f}")
    
    print("\n📉 DRAWDOWN METRICS:")
    print(f"  Max. Drawdown [%]              {stats.get('Max. Drawdown [%]', 0):.2f}%")
    print(f"  Avg. Drawdown [%]              {stats.get('Avg. Drawdown [%]', 0):.2f}%")
    print(f"  Max. Drawdown Duration         {stats.get('Max. Drawdown Duration', 'N/A')}")
    print(f"  Avg. Drawdown Duration         {stats.get('Avg. Drawdown Duration', 'N/A')}")
    
    print("\n📈 TRADE METRICS:")
    print(f"  # Trades                       {stats.get('# Trades', 0)}")
    print(f"  Win Rate [%]                   {stats.get('Win Rate [%]', 0):.2f}%")
    print(f"  Best Trade [%]                 {stats.get('Best Trade [%]', 0):.2f}%")
    print(f"  Worst Trade [%]                {stats.get('Worst Trade [%]', 0):.2f}%")
    print(f"  Avg. Trade [%]                 {stats.get('Avg. Trade [%]', 0):.2f}%")
    print(f"  Max. Trade Duration            {stats.get('Max. Trade Duration', 'N/A')}")
    print(f"  Avg. Trade Duration            {stats.get('Avg. Trade Duration', 'N/A')}")
    
    print("\n🎯 ADVANCED METRICS:")
    print(f"  Profit Factor                  {stats.get('Profit Factor', 0):.3f}")
    print(f"  Expectancy [%]                 {stats.get('Expectancy [%]', 0):.2f}%")
    print(f"  SQN                            {stats.get('SQN', 0):.3f}")
    print(f"  Kelly Criterion                {stats.get('Kelly Criterion', 0):.4f}")
    
    # Trade distribution analysis
    if len(results.trades) > 0:
        print("\n📊 TRADE DISTRIBUTION:")
        trades_df = results.trades
        
        # Win/Loss distribution
        winning_trades = trades_df[trades_df['PnL'] > 0]
        losing_trades = trades_df[trades_df['PnL'] <= 0]
        
        print(f"  Winning Trades:                {len(winning_trades)}")
        print(f"  Losing Trades:                 {len(losing_trades)}")
        
        if len(winning_trades) > 0:
            print(f"  Avg. Winning Trade:            {winning_trades['PnL'].mean():.2f}")
            print(f"  Max Winning Trade:             {winning_trades['PnL'].max():.2f}")
        
        if len(losing_trades) > 0:
            print(f"  Avg. Losing Trade:             {losing_trades['PnL'].mean():.2f}")
            print(f"  Max Losing Trade:              {losing_trades['PnL'].min():.2f}")
        
        # Trade frequency
        print(f"\n📅 TRADE FREQUENCY:")
        trades_per_day = len(trades_df) / (end_date - start_date).days
        print(f"  Trades per Day:                {trades_per_day:.2f}")
        print(f"  Trades per Week:               {trades_per_day * 7:.2f}")
        print(f"  Trades per Month:              {trades_per_day * 30:.2f}")
    
    # Strategy-specific analysis
    print("\n🔍 STRATEGY ANALYSIS:")
    print(f"  Strategy Type:                 EMA Crossover")
    print(f"  Fast EMA Period:               {strategy_params['fast_period']}")
    print(f"  Slow EMA Period:               {strategy_params['slow_period']}")
    print(f"  Position Size:                 {strategy_params['position_size']:.0%}")
    print(f"  Stop Loss:                     {strategy_params['stop_loss_pct']:.1%}")
    print(f"  Take Profit:                   {strategy_params['take_profit_pct']:.1%}")
    
    # Performance comparison
    print("\n📊 PERFORMANCE COMPARISON:")
    outperformance = stats.get('Return [%]', 0) - stats.get('Buy & Hold Return [%]', 0)
    print(f"  Strategy Return:               {stats.get('Return [%]', 0):,.2f}%")
    print(f"  Buy & Hold Return:             {stats.get('Buy & Hold Return [%]', 0):,.2f}%")
    print(f"  Outperformance:                {outperformance:+,.2f}%")
    
    if stats.get('Sharpe Ratio', 0) > 0:
        risk_adjusted_performance = "Positive risk-adjusted returns"
    else:
        risk_adjusted_performance = "Negative risk-adjusted returns"
    print(f"  Risk-Adjusted Performance:     {risk_adjusted_performance}")
    
    # Save detailed results
    print("\n💾 SAVING RESULTS...")
    
    # Save stats to JSON
    stats_dict = {}
    for key, value in stats.items():
        if pd.isna(value):
            stats_dict[key] = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            stats_dict[key] = value.isoformat()
        elif isinstance(value, pd.Timedelta):
            stats_dict[key] = str(value)
        else:
            try:
                stats_dict[key] = float(value)
            except:
                stats_dict[key] = str(value)
    
    with open('bitcoin_ema_backtest_results.json', 'w') as f:
        json.dump({
            'configuration': {
                'symbol': symbol,
                'interval': interval,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'initial_capital': initial_capital,
                'commission': commission
            },
            'strategy_params': strategy_params,
            'metrics': stats_dict,
            'trade_count': len(results.trades)
        }, f, indent=2)
    
    print("  Results saved to: bitcoin_ema_backtest_results.json")
    
    if results.chart_html:
        with open('bitcoin_ema_backtest_chart.html', 'w') as f:
            f.write(results.chart_html)
        print("  Chart saved to: bitcoin_ema_backtest_chart.html")
    
    print("\n" + "=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_bitcoin_ema_backtest()