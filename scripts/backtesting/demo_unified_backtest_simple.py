#!/usr/bin/env python3
"""
Simple Demo for Unified Backtesting System

Demonstrates the core functionality without database dependencies.
"""

from datetime import datetime
from src.infrastructure.strategy.strategy_registry import get_registry

def main():
    """Demonstrate the unified backtesting system"""
    
    print("\n" + "=" * 80)
    print("UNIFIED BACKTESTING SYSTEM - SIMPLIFIED DEMO")
    print("=" * 80 + "\n")
    
    # Initialize registry
    registry = get_registry()
    
    # Display available strategies
    print("Available Strategies:")
    print("-" * 40)
    
    strategies = registry.list_strategies()
    
    for strategy in strategies:
        print(f"\nStrategy ID: {strategy.strategy_id.id}")
        print(f"  Name: {strategy.strategy_id.name}")
        print(f"  Category: {strategy.strategy_id.category.value}")
        print(f"  Trading Mode: {strategy.trading_mode.value}")
        print(f"  Interval: {strategy.interval}")
        print(f"  Leverage: {strategy.leverage}x")
        print(f"  Description: {strategy.description}")
    
    print("\n" + "=" * 80)
    print("EXAMPLE BACKTEST REQUEST FORMAT")
    print("=" * 80 + "\n")
    
    # Show example request
    example_request = {
        "strategy_id": "momentum_macd_futures",
        "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        "start_time": "2023-01-01T00:00:00",
        "end_time": "2023-12-31T23:59:59",
        "initial_capital": 10000
    }
    
    print("To run a backtest, send a POST request to:")
    print("  /api/v1/backtests/run_unified")
    print("\nWith payload:")
    import json
    print(json.dumps(example_request, indent=2))
    
    print("\n" + "=" * 80)
    print("STRATEGY CONFIGURATION DETAILS")
    print("=" * 80 + "\n")
    
    # Show detailed configuration for one strategy
    config = registry.get("momentum_macd_futures")
    if config:
        print(f"Configuration for '{config.strategy_id.id}':")
        print("-" * 40)
        print(f"Class Name: {config.class_name}")
        print(f"Order Type: {config.order_type.value}")
        print(f"Position Sizing: {config.position_sizing.type.value} @ {config.position_sizing.value}")
        print(f"Risk Management:")
        print(f"  - Stop Loss: {config.risk_management.stop_loss_percentage}%")
        print(f"  - Take Profit: {config.risk_management.take_profit_percentage}%")
        print(f"  - Trailing Stop: {config.risk_management.trailing_stop_enabled}")
        print(f"Commission Rates:")
        print(f"  - Market: {config.market_commission * 100}%")
        print(f"  - Limit: {config.limit_commission * 100}%")
        print(f"Parameters: {json.dumps(config.params, indent=2)}")
    
    print("\n" + "=" * 80)
    print("REGISTRY STATISTICS")
    print("=" * 80 + "\n")
    
    stats = registry.get_statistics()
    print(f"Total Strategies: {stats['total_strategies']}")
    print(f"Enabled Strategies: {stats['enabled_strategies']}")
    print(f"\nStrategies by Category:")
    for cat, count in stats['categories'].items():
        print(f"  - {cat}: {count}")
    print(f"\nStrategies by Trading Mode:")
    for mode, count in stats['trading_modes'].items():
        print(f"  - {mode}: {count}")
    
    print("\n" + "=" * 80)
    print("API ENDPOINTS AVAILABLE")
    print("=" * 80 + "\n")
    
    endpoints = [
        ("POST", "/api/v1/backtests/run_unified", "Run unified backtest"),
        ("GET", "/api/v1/backtests/strategies", "List available strategies"),
        ("GET", "/api/v1/backtests/strategies/{id}", "Get strategy details"),
        ("GET", "/api/v1/backtests/historical", "Get historical results"),
        ("GET", "/api/v1/backtests/{job_id}", "Get backtest results"),
        ("GET", "/api/v1/backtests/{job_id}/chart", "Get backtest chart"),
        ("GET", "/api/v1/backtests/{job_id}/trades", "Get trade history"),
    ]
    
    for method, path, description in endpoints:
        print(f"{method:6} {path:45} - {description}")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80 + "\n")
    
    print("The unified backtesting system provides:")
    print("1. Strategy ID-based configuration (all params encapsulated)")
    print("2. Multi-symbol parallel execution")
    print("3. Automatic engine selection (spot/futures)")
    print("4. Portfolio-level aggregated metrics")
    print("5. Database persistence (when configured)")
    print("6. RESTful API interface")
    print("\nYou can now run backtests with just:")
    print("  - strategy_id")
    print("  - symbols[]")
    print("  - start_time")
    print("  - end_time")
    print("  - initial_capital")


if __name__ == "__main__":
    main()