#!/usr/bin/env python3
"""
Demo script for Unified Backtesting System

Demonstrates the simplified interface for running backtests using strategy IDs.
"""

import asyncio
from datetime import datetime
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from src.application.backtesting.services.unified_backtest_service import (
    UnifiedBacktestService,
    UnifiedBacktestRequest
)
from src.infrastructure.strategy.strategy_registry import get_registry

console = Console()


async def demo_unified_backtest():
    """Demonstrate the unified backtesting system"""
    
    console.print("\n[bold cyan]=" * 80)
    console.print("[bold cyan]UNIFIED BACKTESTING SYSTEM DEMO")
    console.print("[bold cyan]=" * 80 + "\n")
    
    # Initialize services
    registry = get_registry()
    unified_service = UnifiedBacktestService()
    
    # Display available strategies
    console.print("[bold]Available Strategies:[/bold]\n")
    
    strategies = registry.list_strategies()
    
    table = Table(title="Strategy Registry", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=25)
    table.add_column("Name", style="green")
    table.add_column("Category", style="yellow")
    table.add_column("Mode", style="blue")
    table.add_column("Leverage", justify="right")
    
    for strategy in strategies:
        table.add_row(
            strategy.strategy_id.id,
            strategy.strategy_id.name,
            strategy.strategy_id.category.value,
            strategy.trading_mode.value,
            f"{strategy.leverage}x"
        )
    
    console.print(table)
    console.print()
    
    # Test 1: Single Symbol Backtest
    console.print("[bold yellow]TEST 1: Single Symbol Backtest[/bold]")
    console.print("-" * 40)
    
    request1 = UnifiedBacktestRequest(
        strategy_id="sma_cross_basic",
        symbols=["BTCUSDT"],
        start_time=datetime(2023, 1, 1),
        end_time=datetime(2023, 12, 31),
        initial_capital=10000
    )
    
    console.print(f"Strategy: [cyan]{request1.strategy_id}[/cyan]")
    console.print(f"Symbol: [green]{request1.symbols[0]}[/green]")
    console.print(f"Period: {request1.start_time.date()} to {request1.end_time.date()}")
    
    with console.status("[bold green]Running backtest...") as status:
        result1 = await unified_service.run_backtest(request1)
    
    display_results(result1)
    
    # Test 2: Multi-Symbol Futures Backtest
    console.print("\n[bold yellow]TEST 2: Multi-Symbol Futures Backtest[/bold]")
    console.print("-" * 40)
    
    request2 = UnifiedBacktestRequest(
        strategy_id="momentum_macd_futures",
        symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        start_time=datetime(2023, 1, 1),
        end_time=datetime(2023, 12, 31),
        initial_capital=10000
    )
    
    console.print(f"Strategy: [cyan]{request2.strategy_id}[/cyan]")
    console.print(f"Symbols: [green]{', '.join(request2.symbols)}[/green]")
    console.print(f"Period: {request2.start_time.date()} to {request2.end_time.date()}")
    
    with console.status("[bold green]Running parallel backtests...") as status:
        result2 = await unified_service.run_backtest(request2)
    
    display_results(result2)
    
    # Test 3: Mean Reversion Strategy
    console.print("\n[bold yellow]TEST 3: Mean Reversion Strategy[/bold]")
    console.print("-" * 40)
    
    request3 = UnifiedBacktestRequest(
        strategy_id="mean_reversion_bb",
        symbols=["BTCUSDT", "ETHUSDT"],
        start_time=datetime(2023, 6, 1),
        end_time=datetime(2023, 12, 31),
        initial_capital=10000
    )
    
    console.print(f"Strategy: [cyan]{request3.strategy_id}[/cyan]")
    console.print(f"Symbols: [green]{', '.join(request3.symbols)}[/green]")
    console.print(f"Period: {request3.start_time.date()} to {request3.end_time.date()}")
    
    with console.status("[bold green]Running backtests...") as status:
        result3 = await unified_service.run_backtest(request3)
    
    display_results(result3)
    
    # Summary
    console.print("\n[bold cyan]=" * 80)
    console.print("[bold cyan]DEMO COMPLETE")
    console.print("[bold cyan]=" * 80)
    
    # Display execution comparison
    comparison_table = Table(title="Execution Summary", show_header=True)
    comparison_table.add_column("Test", style="cyan")
    comparison_table.add_column("Strategy", style="green")
    comparison_table.add_column("Symbols", justify="center")
    comparison_table.add_column("Execution Time", justify="right")
    comparison_table.add_column("Avg Return", justify="right", style="yellow")
    
    for i, result in enumerate([result1, result2, result3], 1):
        if result.portfolio_stats:
            avg_return = f"{result.portfolio_stats.get('avg_return', 0):.2f}%"
        else:
            # For single symbol, use the symbol's return
            first_symbol = list(result.symbol_results.keys())[0]
            avg_return = f"{result.symbol_results[first_symbol].stats.get('Return [%]', 0):.2f}%"
        
        comparison_table.add_row(
            f"Test {i}",
            result.strategy_name,
            str(len(result.symbol_results)),
            f"{result.execution_time_ms}ms" if result.execution_time_ms else "N/A",
            avg_return
        )
    
    console.print("\n")
    console.print(comparison_table)
    
    # Shutdown service
    unified_service.shutdown()


def display_results(result):
    """Display backtest results in a formatted way"""
    
    # Create results panel
    if result.portfolio_stats:
        # Multi-symbol results
        stats_text = f"""
[bold]Portfolio Statistics:[/bold]
  Total Symbols: {result.portfolio_stats['total_symbols']}
  Successful: {result.portfolio_stats['successful_symbols']}
  Avg Return: {result.portfolio_stats.get('avg_return', 0):.2f}%
  Total Trades: {result.portfolio_stats.get('total_trades', 0)}
  Avg Win Rate: {result.portfolio_stats.get('avg_win_rate', 0):.2f}%
  Avg Sharpe: {result.portfolio_stats.get('avg_sharpe_ratio', 0):.2f}
  Worst Drawdown: {result.portfolio_stats.get('worst_drawdown', 0):.2f}%
"""
        
        if result.portfolio_stats.get('best_performer'):
            stats_text += f"  Best Performer: {result.portfolio_stats['best_performer']}\n"
    else:
        # Single symbol results
        stats_text = "[bold]Results:[/bold]\n"
    
    # Add symbol-specific results
    stats_text += "\n[bold]Symbol Results:[/bold]\n"
    for symbol, sym_result in result.symbol_results.items():
        if sym_result.error:
            stats_text += f"  {symbol}: [red]Error - {sym_result.error}[/red]\n"
        else:
            stats = sym_result.stats
            stats_text += f"""  {symbol}:
    Return: {stats.get('Return [%]', 0):.2f}%
    Sharpe: {stats.get('Sharpe Ratio', 0):.2f}
    Trades: {stats.get('# Trades', 0)}
    Win Rate: {stats.get('Win Rate [%]', 0):.2f}%
"""
    
    # Add execution info
    stats_text += f"\n[dim]Execution Time: {result.execution_time_ms}ms[/dim]"
    stats_text += f"\n[dim]Job ID: {result.job_id}[/dim]"
    
    panel = Panel(
        stats_text,
        title=f"[bold]{result.strategy_name}[/bold]",
        border_style="green"
    )
    
    console.print(panel)


def test_strategy_registry():
    """Test strategy registry functionality"""
    console.print("\n[bold cyan]Testing Strategy Registry[/bold]")
    console.print("-" * 40)
    
    registry = get_registry()
    
    # Test filtering
    console.print("\n[bold]Momentum Strategies:[/bold]")
    momentum_strategies = registry.list_strategies(
        category=StrategyCategory.MOMENTUM
    )
    for s in momentum_strategies:
        console.print(f"  - {s.strategy_id.id}: {s.strategy_id.name}")
    
    console.print("\n[bold]Futures Strategies:[/bold]")
    futures_strategies = registry.list_strategies(
        trading_mode=TradingMode.FUTURES
    )
    for s in futures_strategies:
        console.print(f"  - {s.strategy_id.id}: {s.strategy_id.name} ({s.leverage}x leverage)")
    
    # Test statistics
    stats = registry.get_statistics()
    console.print("\n[bold]Registry Statistics:[/bold]")
    console.print(f"  Total Strategies: {stats['total_strategies']}")
    console.print(f"  Enabled Strategies: {stats['enabled_strategies']}")
    console.print(f"  Categories: {json.dumps(stats['categories'], indent=4)}")
    console.print(f"  Trading Modes: {json.dumps(stats['trading_modes'], indent=4)}")


if __name__ == "__main__":
    # Import after checking main
    from src.domain.strategy.value_objects.strategy_configuration import (
        StrategyCategory, TradingMode
    )
    
    # Test registry first
    test_strategy_registry()
    
    # Run async demo
    asyncio.run(demo_unified_backtest())