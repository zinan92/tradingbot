#!/usr/bin/env python3
"""
Metrics System Demonstration

Shows how the metrics system tracks various operations and data freshness.
"""
import asyncio
import time
import random
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.monitoring.metrics import metrics_registry, system_metrics, Timer
from src.infrastructure.monitoring.freshness_collector import DataFreshnessCollector, MockMarketDataPort


async def simulate_data_ingestion():
    """Simulate data ingestion with metrics"""
    print("\n=== Data Ingestion Metrics ===")
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    intervals = ['1m', '5m', '1h']
    
    for symbol in symbols:
        for interval in intervals:
            labels = {
                'source': 'binance',
                'symbol': symbol,
                'interval': interval
            }
            
            # Track request
            system_metrics['data_ingestion_requests'].inc(labels=labels)
            
            # Simulate latency
            latency = random.uniform(0.01, 0.5)
            system_metrics['data_ingestion_latency'].observe(latency, labels)
            
            # Randomly simulate errors
            if random.random() < 0.1:  # 10% error rate
                error_labels = {**labels, 'error_type': 'ConnectionError'}
                system_metrics['data_ingestion_errors'].inc(labels=error_labels)
            
            print(f"  {symbol}:{interval} - latency: {latency:.3f}s")
    
    # Update queue depth
    for i in range(5):
        system_metrics['queue_depth'].set(
            random.randint(0, 20),
            labels={'queue_name': 'market_data_requests'}
        )
        await asyncio.sleep(0.1)


async def simulate_indicator_calculation():
    """Simulate indicator calculations with metrics"""
    print("\n=== Indicator Calculation Metrics ===")
    
    indicators = ['SMA', 'EMA', 'RSI', 'MACD']
    symbols = ['BTCUSDT', 'ETHUSDT']
    
    for indicator in indicators:
        for symbol in symbols:
            labels = {
                'indicator': indicator,
                'symbol': symbol,
                'interval': '5m'
            }
            
            # Measure calculation time
            with Timer(system_metrics['indicator_calc_latency'], labels):
                # Simulate calculation
                await asyncio.sleep(random.uniform(0.001, 0.05))
            
            # Randomly simulate errors
            if random.random() < 0.05:  # 5% error rate
                error_labels = {**labels, 'error_type': 'CalculationError'}
                system_metrics['indicator_calc_errors'].inc(labels=error_labels)
            
            latency_summary = system_metrics['indicator_calc_latency'].get_summary(labels)
            print(f"  {indicator} for {symbol}: {latency_summary['avg']:.3f}s avg")


async def simulate_backtest():
    """Simulate backtest execution with metrics"""
    print("\n=== Backtest Metrics ===")
    
    strategies = ['EMACross', 'RSIMeanReversion', 'MACD']
    
    for strategy in strategies:
        labels = {
            'strategy': strategy,
            'symbol': 'BTCUSDT',
            'interval': '5m'
        }
        
        # Simulate backtest duration
        duration = random.uniform(1, 10)
        system_metrics['backtest_duration'].observe(duration, labels)
        
        # Simulate trades
        winning_trades = random.randint(10, 50)
        losing_trades = random.randint(5, 30)
        
        system_metrics['backtest_trades'].inc(
            winning_trades,
            labels={**labels, 'result': 'win'}
        )
        system_metrics['backtest_trades'].inc(
            losing_trades,
            labels={**labels, 'result': 'loss'}
        )
        
        win_rate = winning_trades / (winning_trades + losing_trades) * 100
        print(f"  {strategy}: {duration:.1f}s, {winning_trades}W/{losing_trades}L ({win_rate:.1f}% win rate)")


async def simulate_live_trading():
    """Simulate live trading with metrics"""
    print("\n=== Live Trading Metrics ===")
    
    order_types = ['market', 'limit']
    sides = ['buy', 'sell']
    
    for _ in range(10):
        order_type = random.choice(order_types)
        side = random.choice(sides)
        
        labels = {
            'exchange': 'binance',
            'symbol': 'BTCUSDT',
            'order_type': order_type
        }
        
        # Measure order latency
        latency = random.uniform(0.05, 0.5)
        system_metrics['live_order_latency'].observe(latency, labels)
        
        # Track order status
        status = random.choice(['filled', 'filled', 'filled', 'cancelled'])  # 75% fill rate
        system_metrics['live_orders'].inc(
            labels={
                'exchange': 'binance',
                'symbol': 'BTCUSDT',
                'side': side,
                'status': status
            }
        )
        
        # Randomly simulate errors
        if random.random() < 0.02:  # 2% error rate
            error_labels = {**labels, 'error_type': 'InsufficientBalance'}
            system_metrics['live_order_errors'].inc(labels=error_labels)
        
        # Update queue depth
        system_metrics['queue_depth'].set(
            random.randint(0, 10),
            labels={'queue_name': 'order_queue'}
        )
    
    print(f"  Submitted 10 orders with various outcomes")


async def demonstrate_data_freshness():
    """Demonstrate data freshness monitoring"""
    print("\n=== Data Freshness Monitoring ===")
    
    # Create mock market data port
    mock_port = MockMarketDataPort()
    
    # Create freshness collector
    collector = DataFreshnessCollector(
        market_data_port=mock_port,
        update_interval=1,
        staleness_threshold=30
    )
    
    # Add symbols to monitor
    symbols = [
        ('BTCUSDT', '1m'),
        ('BTCUSDT', '5m'),
        ('ETHUSDT', '5m'),
        ('BNBUSDT', '1h')
    ]
    
    for symbol, interval in symbols:
        collector.add_symbol(symbol, interval)
    
    # Start monitoring
    await collector.start()
    print("  Started freshness monitoring for 4 symbol/interval pairs")
    
    # Let it run briefly
    await asyncio.sleep(2)
    
    # Check freshness
    print("\n  Initial freshness (should be fresh ~5s):")
    for symbol, interval in symbols:
        freshness = system_metrics['data_freshness'].get_value({
            'symbol': symbol,
            'interval': interval
        })
        print(f"    {symbol}:{interval} = {freshness:.1f}s")
    
    # Simulate staleness for one symbol
    print("\n  Pausing data updates to simulate staleness...")
    mock_port.pause_updates()
    
    # Wait for staleness
    await asyncio.sleep(2)
    
    # Check again
    print("\n  After pause (should show increasing age):")
    for symbol, interval in symbols:
        freshness = system_metrics['data_freshness'].get_value({
            'symbol': symbol,
            'interval': interval
        })
        status = "STALE" if freshness > 30 else "fresh"
        print(f"    {symbol}:{interval} = {freshness:.1f}s [{status}]")
    
    # Resume updates
    mock_port.resume_updates()
    await asyncio.sleep(2)
    
    print("\n  After resuming (should be fresh again):")
    for symbol, interval in symbols:
        freshness = system_metrics['data_freshness'].get_value({
            'symbol': symbol,
            'interval': interval
        })
        print(f"    {symbol}:{interval} = {freshness:.1f}s")
    
    # Stop collector
    await collector.stop()


def print_metrics_summary():
    """Print summary of collected metrics"""
    print("\n" + "="*60)
    print("METRICS SUMMARY")
    print("="*60)
    
    # Data ingestion summary
    requests = system_metrics['data_ingestion_requests']
    errors = system_metrics['data_ingestion_errors']
    total_requests = sum(v.value for v in requests.get_all())
    total_errors = sum(v.value for v in errors.get_all())
    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
    
    print(f"\nData Ingestion:")
    print(f"  Total requests: {total_requests}")
    print(f"  Total errors: {total_errors}")
    print(f"  Error rate: {error_rate:.1f}%")
    
    # Get latency summary for BTCUSDT 5m
    latency = system_metrics['data_ingestion_latency'].get_summary({
        'source': 'binance',
        'symbol': 'BTCUSDT',
        'interval': '5m'
    })
    if latency['count'] > 0:
        print(f"  BTCUSDT 5m latency: avg={latency['avg']:.3f}s, p95={latency['p95']:.3f}s")
    
    # Backtest summary
    trades = system_metrics['backtest_trades']
    total_trades = sum(v.value for v in trades.get_all())
    print(f"\nBacktest:")
    print(f"  Total trades simulated: {total_trades}")
    
    # Live trading summary
    orders = system_metrics['live_orders']
    order_errors = system_metrics['live_order_errors']
    total_orders = sum(v.value for v in orders.get_all())
    total_order_errors = sum(v.value for v in order_errors.get_all())
    
    print(f"\nLive Trading:")
    print(f"  Total orders: {total_orders}")
    print(f"  Order errors: {total_order_errors}")
    
    # Queue depths
    print(f"\nQueue Depths:")
    print(f"  Market data queue: {system_metrics['queue_depth'].get_value({'queue_name': 'market_data_requests'})}")
    print(f"  Order queue: {system_metrics['queue_depth'].get_value({'queue_name': 'order_queue'})}")
    
    # Export sample
    print("\n" + "="*60)
    print("PROMETHEUS FORMAT SAMPLE")
    print("="*60)
    
    # Get first few lines of Prometheus export
    export = metrics_registry.export_prometheus()
    lines = export.split('\n')[:20]
    for line in lines:
        if line:
            print(line)
    print("... (truncated)")


async def main():
    """Run the demonstration"""
    print("="*60)
    print("METRICS SYSTEM DEMONSTRATION")
    print("="*60)
    
    # Run simulations
    await simulate_data_ingestion()
    await simulate_indicator_calculation()
    await simulate_backtest()
    await simulate_live_trading()
    await demonstrate_data_freshness()
    
    # Print summary
    print_metrics_summary()
    
    print("\n✅ Metrics demonstration complete!")
    print("\nIn production, these metrics would be:")
    print("- Exposed at /metrics endpoint for Prometheus scraping")
    print("- Visualized in Grafana dashboards")
    print("- Used for alerting on anomalies")
    print("- Tracked for performance optimization")


if __name__ == "__main__":
    asyncio.run(main())