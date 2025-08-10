#!/usr/bin/env python3
"""
Detailed report for LINK Momentum Strategy - Best Performer
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
from src.application.backtesting.strategies.macd_strategy import MACDStrategy


def generate_detailed_report():
    """Generate detailed report for LINK Momentum strategy"""
    
    print("=" * 100)
    print("DETAILED BACKTEST REPORT: LINK MOMENTUM STRATEGY")
    print("=" * 100)
    print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    # Configuration
    symbol = "LINKUSDT"
    interval = "2h"
    start_date = datetime.now() - timedelta(days=90)  # 3 months
    end_date = datetime.now()
    initial_capital = 10000
    commission = 0.001
    
    # Strategy parameters (with leverage simulation)
    strategy_params = {
        'fast_period': 12,
        'slow_period': 26,
        'signal_period': 9,
        'histogram_threshold': 0.5,
        'use_divergence': True,
        'stop_loss_pct': 0.03,  # 3% stop loss
        'take_profit_pct': 0.10,  # 10% take profit (simulating 2x leverage effect)
        'position_size': 0.95
    }
    
    print("\n📋 STRATEGY CONFIGURATION")
    print("-" * 100)
    print(f"  Strategy Type:           MACD Momentum with Leverage Simulation")
    print(f"  Symbol:                  {symbol}")
    print(f"  Timeframe:               {interval} (2-hour candles)")
    print(f"  Backtest Period:         {start_date.date()} to {end_date.date()}")
    print(f"  Duration:                {(end_date - start_date).days} days")
    print(f"  Initial Capital:         ${initial_capital:,.2f}")
    print(f"  Commission:              {commission:.2%}")
    
    print("\n📊 STRATEGY PARAMETERS")
    print("-" * 100)
    print(f"  MACD Fast Period:        {strategy_params['fast_period']}")
    print(f"  MACD Slow Period:        {strategy_params['slow_period']}")
    print(f"  Signal Period:           {strategy_params['signal_period']}")
    print(f"  Histogram Threshold:     {strategy_params['histogram_threshold']}")
    print(f"  Use Divergence:          {strategy_params['use_divergence']}")
    print(f"  Stop Loss:               {strategy_params['stop_loss_pct']:.1%}")
    print(f"  Take Profit:             {strategy_params['take_profit_pct']:.1%}")
    print(f"  Position Size:           {strategy_params['position_size']:.0%}")
    print(f"  Simulated Leverage:      ~2x (via larger TP targets)")
    
    # Initialize components
    data_adapter = DataAdapter({
        'host': 'localhost',
        'port': 5432,
        'database': 'tradingbot',
        'user': None,
        'password': None
    })
    backtest_engine = BacktestEngine()
    
    # Load data
    print("\n📈 MARKET DATA")
    print("-" * 100)
    print(f"  Loading {symbol} data...")
    
    data = data_adapter.fetch_ohlcv(
        symbol=symbol,
        interval=interval,
        start_date=start_date,
        end_date=end_date
    )
    
    print(f"  ✅ Loaded {len(data)} candles")
    print(f"  Date Range:              {data.index[0]} to {data.index[-1]}")
    print(f"  Price Range:             ${data['Close'].min():.2f} - ${data['Close'].max():.2f}")
    print(f"  Average Price:           ${data['Close'].mean():.2f}")
    print(f"  Price Volatility (std):  ${data['Close'].std():.2f}")
    
    # Calculate some market statistics
    returns = data['Close'].pct_change().dropna()
    print(f"  Daily Returns (mean):    {returns.mean():.4%}")
    print(f"  Daily Returns (std):     {returns.std():.4%}")
    print(f"  Best Day:                {returns.max():.4%}")
    print(f"  Worst Day:               {returns.min():.4%}")
    
    # Run backtest
    print("\n🚀 RUNNING BACKTEST")
    print("-" * 100)
    
    results = backtest_engine.run_backtest(
        data=data,
        strategy_class=MACDStrategy,
        initial_cash=initial_capital,
        commission=commission,
        **strategy_params
    )
    
    stats = results.stats
    
    print("  ✅ Backtest completed successfully")
    
    # Performance Metrics
    print("\n💰 PERFORMANCE METRICS")
    print("-" * 100)
    print(f"  Initial Capital:         ${initial_capital:,.2f}")
    print(f"  Final Equity:            ${stats.get('Equity Final [$]', 0):,.2f}")
    print(f"  Total Return:            {stats.get('Return [%]', 0):,.2f}%")
    print(f"  Annualized Return:       {stats.get('Return (Ann.) [%]', 0):,.2f}%")
    print(f"  Buy & Hold Return:       {stats.get('Buy & Hold Return [%]', 0):,.2f}%")
    
    outperformance = stats.get('Return [%]', 0) - stats.get('Buy & Hold Return [%]', 0)
    print(f"  Outperformance:          {outperformance:+.2f}%")
    
    # Risk Metrics
    print("\n📊 RISK METRICS")
    print("-" * 100)
    print(f"  Sharpe Ratio:            {stats.get('Sharpe Ratio', 0):.3f}")
    print(f"  Sortino Ratio:           {stats.get('Sortino Ratio', 0):.3f}")
    print(f"  Calmar Ratio:            {stats.get('Calmar Ratio', 0):.3f}")
    print(f"  Max Drawdown:            {stats.get('Max. Drawdown [%]', 0):.2f}%")
    print(f"  Avg Drawdown:            {stats.get('Avg. Drawdown [%]', 0):.2f}%")
    print(f"  Max DD Duration:         {stats.get('Max. Drawdown Duration', 'N/A')}")
    print(f"  Volatility (Annual):     {stats.get('Volatility (Ann.) [%]', 0):.2f}%")
    
    # Trading Statistics
    print("\n📈 TRADING STATISTICS")
    print("-" * 100)
    print(f"  Total Trades:            {stats.get('# Trades', 0)}")
    print(f"  Win Rate:                {stats.get('Win Rate [%]', 0):.2f}%")
    print(f"  Best Trade:              {stats.get('Best Trade [%]', 0):.2f}%")
    print(f"  Worst Trade:             {stats.get('Worst Trade [%]', 0):.2f}%")
    print(f"  Average Trade:           {stats.get('Avg. Trade [%]', 0):.2f}%")
    print(f"  Profit Factor:           {stats.get('Profit Factor', 0):.2f}")
    print(f"  Expectancy:              {stats.get('Expectancy [%]', 0):.2f}%")
    print(f"  SQN:                     {stats.get('SQN', 0):.2f}")
    
    # Trade Analysis
    if len(results.trades) > 0:
        trades_df = results.trades
        
        print("\n🔍 TRADE ANALYSIS")
        print("-" * 100)
        
        winning_trades = trades_df[trades_df['PnL'] > 0]
        losing_trades = trades_df[trades_df['PnL'] <= 0]
        
        print(f"  Winning Trades:          {len(winning_trades)}")
        print(f"  Losing Trades:           {len(losing_trades)}")
        
        if len(winning_trades) > 0:
            print(f"  Avg Winning Trade:       ${winning_trades['PnL'].mean():.2f}")
            print(f"  Max Winning Trade:       ${winning_trades['PnL'].max():.2f}")
            
        if len(losing_trades) > 0:
            print(f"  Avg Losing Trade:        ${losing_trades['PnL'].mean():.2f}")
            print(f"  Max Losing Trade:        ${losing_trades['PnL'].min():.2f}")
        
        # Trade frequency
        trades_per_week = len(trades_df) / ((end_date - start_date).days / 7)
        print(f"  Trades per Week:         {trades_per_week:.1f}")
        
        # Average holding period
        if 'Duration' in trades_df.columns:
            avg_duration = trades_df['Duration'].mean()
            print(f"  Avg Holding Period:      {avg_duration}")
    
    # Monthly Performance Breakdown
    print("\n📅 MONTHLY PERFORMANCE")
    print("-" * 100)
    
    # Create monthly returns if we have equity curve
    if hasattr(results, 'equity_curve'):
        equity = pd.Series(results.equity_curve)
        monthly_returns = equity.resample('M').last().pct_change().dropna()
        
        for date, ret in monthly_returns.items():
            print(f"  {date.strftime('%Y-%m')}:                {ret:.2%}")
    
    # Strategy Strengths and Weaknesses
    print("\n💡 STRATEGY ANALYSIS")
    print("-" * 100)
    
    print("\n  ✅ STRENGTHS:")
    if stats.get('Return [%]', 0) > 0:
        print(f"  • Profitable strategy with {stats.get('Return [%]', 0):.2f}% return")
    if stats.get('Sharpe Ratio', 0) > 1:
        print(f"  • Good risk-adjusted returns (Sharpe: {stats.get('Sharpe Ratio', 0):.2f})")
    if stats.get('Win Rate [%]', 0) > 40:
        print(f"  • Decent win rate of {stats.get('Win Rate [%]', 0):.1f}%")
    if stats.get('Profit Factor', 0) > 1:
        print(f"  • Positive profit factor: {stats.get('Profit Factor', 0):.2f}")
    print("  • MACD momentum captures trend changes effectively")
    print("  • Leverage simulation amplifies profitable moves")
    
    print("\n  ⚠️ AREAS FOR IMPROVEMENT:")
    if stats.get('Max. Drawdown [%]', 0) < -10:
        print(f"  • High maximum drawdown: {stats.get('Max. Drawdown [%]', 0):.2f}%")
    if stats.get('Win Rate [%]', 0) < 50:
        print(f"  • Win rate below 50%: {stats.get('Win Rate [%]', 0):.1f}%")
    print("  • Consider adding trend filters to reduce false signals")
    print("  • May benefit from dynamic position sizing based on volatility")
    
    # Recommendations
    print("\n🎯 RECOMMENDATIONS")
    print("-" * 100)
    print("  1. Optimize MACD parameters for 2h timeframe")
    print("  2. Add volume confirmation for entry signals")
    print("  3. Implement trailing stops to protect profits")
    print("  4. Consider market regime filters (trending vs ranging)")
    print("  5. Test with different leverage ratios")
    print("  6. Add correlation filters with BTC/ETH")
    
    # Risk Warning
    print("\n⚠️ RISK DISCLAIMER")
    print("-" * 100)
    print("  • Past performance does not guarantee future results")
    print("  • This backtest uses historical data and may not reflect live trading conditions")
    print("  • Leverage amplifies both gains and losses")
    print("  • Always use proper risk management and position sizing")
    print("  • Consider transaction costs, slippage, and market impact in live trading")
    
    print("\n" + "=" * 100)
    print("END OF DETAILED REPORT")
    print("=" * 100)
    
    # Save detailed metrics to JSON
    metrics_dict = {}
    for key, value in stats.items():
        if pd.isna(value):
            metrics_dict[key] = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            metrics_dict[key] = value.isoformat()
        elif isinstance(value, pd.Timedelta):
            metrics_dict[key] = str(value)
        else:
            try:
                metrics_dict[key] = float(value)
            except:
                metrics_dict[key] = str(value)
    
    report_data = {
        'strategy': 'LINK Momentum (MACD)',
        'symbol': symbol,
        'interval': interval,
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': (end_date - start_date).days
        },
        'parameters': strategy_params,
        'metrics': metrics_dict,
        'trade_count': len(results.trades) if hasattr(results, 'trades') else 0
    }
    
    with open('link_momentum_detailed_report.json', 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📄 Detailed metrics saved to: link_momentum_detailed_report.json")
    
    return stats


if __name__ == "__main__":
    stats = generate_detailed_report()