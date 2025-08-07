#!/usr/bin/env python3
"""
Demo script for Backtesting Engine

Shows how to run a backtest and display results matching the screenshot format.
"""

from datetime import datetime
from src.application.backtesting.commands.run_backtest_command import (
    RunBacktestCommand,
    RunBacktestCommandHandler
)
from src.infrastructure.backtesting.results_formatter import ResultsFormatter


def run_demo_backtest():
    """Run a demo backtest with SMA crossover strategy"""
    
    print("=" * 60)
    print("BACKTESTING ENGINE DEMO")
    print("=" * 60)
    print()
    
    # Create backtest command
    command = RunBacktestCommand(
        strategy_name='SmaCross',
        symbol='BTCUSDT',
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
        initial_capital=10000,
        commission=0.002,
        interval='1h',
        strategy_params={'n1': 10, 'n2': 20}
    )
    
    print(f"Strategy: {command.strategy_name}(n1={command.strategy_params['n1']}, n2={command.strategy_params['n2']})")
    print(f"Symbol: {command.symbol}")
    print(f"Period: {command.start_date.date()} to {command.end_date.date()}")
    print(f"Initial Capital: ${command.initial_capital:,.2f}")
    print(f"Commission: {command.commission:.2%}")
    print()
    
    # Create handler and run backtest
    handler = RunBacktestCommandHandler()
    
    print("Running backtest...")
    print("-" * 60)
    
    try:
        # Execute backtest
        results = handler.handle(command)
        
        # Display results in exact format from screenshot
        print("\nResults in:")
        print()
        
        stats = results.stats
        
        # Time metrics
        print(f"{'Start':<30} {stats.get('Start', '')}")
        print(f"{'End':<30} {stats.get('End', '')}")
        print(f"{'Duration':<30} {stats.get('Duration', '')}")
        print(f"{'Exposure Time [%]':<30} {stats.get('Exposure Time [%]', 0):.2f}")
        
        # Equity metrics
        print(f"{'Equity Final [$]':<30} {stats.get('Equity Final [$]', 0):.2f}")
        print(f"{'Equity Peak [$]':<30} {stats.get('Equity Peak [$]', 0):.2f}")
        print(f"{'Return [%]':<30} {stats.get('Return [%]', 0):.2f}")
        print(f"{'Buy & Hold Return [%]':<30} {stats.get('Buy & Hold Return [%]', 0):.2f}")
        print(f"{'Return (Ann.) [%]':<30} {stats.get('Return (Ann.) [%]', 0):.2f}")
        print(f"{'Volatility (Ann.) [%]':<30} {stats.get('Volatility (Ann.) [%]', 0):.2f}")
        
        # Risk metrics
        print(f"{'CAGR [%]':<30} {stats.get('CAGR [%]', 0):.2f}")
        print(f"{'Sharpe Ratio':<30} {stats.get('Sharpe Ratio', 0):.2f}")
        print(f"{'Sortino Ratio':<30} {stats.get('Sortino Ratio', 0):.2f}")
        print(f"{'Calmar Ratio':<30} {stats.get('Calmar Ratio', 0):.2f}")
        print(f"{'Alpha [%]':<30} {stats.get('Alpha [%]', 0):.2f}")
        print(f"{'Beta':<30} {stats.get('Beta', 0):.2f}")
        
        # Drawdown metrics
        print(f"{'Max. Drawdown [%]':<30} {stats.get('Max. Drawdown [%]', 0):.2f}")
        print(f"{'Avg. Drawdown [%]':<30} {stats.get('Avg. Drawdown [%]', 0):.2f}")
        print(f"{'Max. Drawdown Duration':<30} {stats.get('Max. Drawdown Duration', '')}")
        print(f"{'Avg. Drawdown Duration':<30} {stats.get('Avg. Drawdown Duration', '')}")
        
        # Trade metrics
        print(f"{'# Trades':<30} {stats.get('# Trades', 0)}")
        print(f"{'Win Rate [%]':<30} {stats.get('Win Rate [%]', 0):.2f}")
        print(f"{'Best Trade [%]':<30} {stats.get('Best Trade [%]', 0):.2f}")
        print(f"{'Worst Trade [%]':<30} {stats.get('Worst Trade [%]', 0):.2f}")
        print(f"{'Avg. Trade [%]':<30} {stats.get('Avg. Trade [%]', 0):.2f}")
        print(f"{'Max. Trade Duration':<30} {stats.get('Max. Trade Duration', '')}")
        print(f"{'Avg. Trade Duration':<30} {stats.get('Avg. Trade Duration', '')}")
        
        # Advanced metrics
        print(f"{'Profit Factor':<30} {stats.get('Profit Factor', 0):.2f}")
        print(f"{'Expectancy [%]':<30} {stats.get('Expectancy [%]', 0):.2f}")
        print(f"{'SQN':<30} {stats.get('SQN', 0):.2f}")
        print(f"{'Kelly Criterion':<30} {stats.get('Kelly Criterion', 0):.4f}")
        
        # Strategy info
        print(f"{'_strategy':<30} SmaCross(n1={command.strategy_params['n1']}, n2={command.strategy_params['n2']})")
        print(f"{'_equity_curve':<30} Equ...")
        print(f"{'_trades':<30} Size   EntryB...")
        print(f"dtype: object")
        
        print()
        print("=" * 60)
        print("BACKTEST COMPLETE")
        print("=" * 60)
        
        # Save chart
        if results.chart_html:
            with open('backtest_chart.html', 'w') as f:
                f.write(results.chart_html)
            print("\nInteractive chart saved to: backtest_chart.html")
            print("Open this file in a browser to view the interactive plot")
        
    except Exception as e:
        print(f"\nError running backtest: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_demo_backtest()