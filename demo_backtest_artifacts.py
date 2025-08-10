#!/usr/bin/env python3
"""
Demonstration of Backtest Artifact Generation

Shows how the standardized backtest artifacts are created.
"""
import json
import csv
from pathlib import Path
from datetime import datetime, timedelta

from src.infrastructure.backtesting.artifact_writer import BacktestArtifactWriter


def generate_sample_backtest_results():
    """Generate sample backtest results for demonstration"""
    
    # Sample metrics
    metrics = {
        'sharpe': 1.65,
        'profit_factor': 2.8,
        'win_rate': 68.5,
        'max_dd': 8.3,
        'returns': 125.6,
        'total_trades': 245,
        'winning_trades': 168,
        'losing_trades': 77,
        'avg_win': 450.25,
        'avg_loss': -210.50,
        'best_trade': 2500.00,
        'worst_trade': -850.00,
        'recovery_factor': 3.2,
        'calmar_ratio': 1.8
    }
    
    # Sample equity curve (30 days)
    equity_curve = []
    initial_capital = 10000
    current_equity = initial_capital
    peak_equity = initial_capital
    
    for i in range(30):
        # Simulate equity changes
        daily_change = (i % 5 - 2) * 50  # Oscillating pattern
        current_equity += daily_change
        
        # Track peak for drawdown calculation
        if current_equity > peak_equity:
            peak_equity = current_equity
        
        drawdown = ((peak_equity - current_equity) / peak_equity) * 100 if peak_equity > 0 else 0
        returns = ((current_equity - initial_capital) / initial_capital) * 100
        
        equity_curve.append({
            'timestamp': (datetime.now() - timedelta(days=30-i)).strftime('%Y-%m-%d %H:%M:%S'),
            'equity': current_equity,
            'drawdown': drawdown,
            'returns': returns
        })
    
    # Sample trades
    trades = []
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    for i in range(10):
        entry_time = datetime.now() - timedelta(days=25-i*2, hours=i)
        exit_time = entry_time + timedelta(hours=2+i%3)
        
        symbol = symbols[i % 3]
        side = 'long' if i % 2 == 0 else 'short'
        
        # Vary trade outcomes
        if i % 3 == 0:  # Losing trade
            pnl = -50 - (i * 10)
            pnl_percent = -1.5 - (i * 0.2)
        else:  # Winning trade
            pnl = 100 + (i * 15)
            pnl_percent = 2.5 + (i * 0.3)
        
        base_price = 45000 if symbol == 'BTCUSDT' else (3000 if symbol == 'ETHUSDT' else 300)
        
        trades.append({
            'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': exit_time.strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'side': side,
            'entry_price': base_price,
            'exit_price': base_price * (1 + pnl_percent/100),
            'quantity': 0.1 if symbol == 'BTCUSDT' else (1.0 if symbol == 'ETHUSDT' else 10.0),
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'commission': abs(pnl) * 0.01  # 1% commission
        })
    
    return metrics, equity_curve, trades


def main():
    """Run the demonstration"""
    
    print("=" * 60)
    print("BACKTEST ARTIFACT GENERATION DEMONSTRATION")
    print("=" * 60)
    
    # Generate sample data
    print("\n1. Generating sample backtest results...")
    metrics, equity_curve, trades = generate_sample_backtest_results()
    
    print(f"   - Metrics: {len(metrics)} performance indicators")
    print(f"   - Equity curve: {len(equity_curve)} data points")
    print(f"   - Trades: {len(trades)} executed trades")
    
    # Create artifact writer
    output_dir = "artifacts"
    print(f"\n2. Writing standardized artifacts to '{output_dir}/'...")
    
    writer = BacktestArtifactWriter(output_dir)
    
    # Write all artifacts
    artifacts = writer.write_all_artifacts(
        metrics=metrics,
        equity_curve=equity_curve,
        trades=trades,
        strategy_name="EMA Crossover Strategy",
        metadata={
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'fast_period': 12,
            'slow_period': 26,
            'initial_capital': 10000,
            'commission': 0.001,
            'slippage': 0.0005,
            'start_date': equity_curve[0]['timestamp'],
            'end_date': equity_curve[-1]['timestamp']
        }
    )
    
    print("\n3. Artifacts created successfully:")
    print("-" * 40)
    
    # Display artifact information
    for name, path in artifacts.items():
        size = path.stat().st_size
        print(f"   ✓ {path.name:<15} ({size:,} bytes)")
    
    # Show sample content from each file
    print("\n4. Artifact Contents:")
    print("-" * 40)
    
    # Show metrics.json
    print("\n📊 metrics.json (first 5 metrics):")
    with open(artifacts['metrics']) as f:
        metrics_data = json.load(f)
    for i, (key, value) in enumerate(list(metrics_data.items())[:5]):
        print(f"   {key:<20}: {value:>10.2f}")
    
    # Show equity.csv
    print("\n📈 equity.csv (first 3 rows):")
    with open(artifacts['equity']) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 3:
                break
            print(f"   {row['timestamp']}: ${float(row['equity']):,.2f} "
                  f"(DD: {float(row['drawdown']):.1f}%, Ret: {float(row['returns']):.1f}%)")
    
    # Show trades.csv
    print("\n💹 trades.csv (first 3 trades):")
    with open(artifacts['trades']) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 3:
                break
            pnl = float(row['pnl'])
            pnl_class = "🟢" if pnl > 0 else "🔴"
            print(f"   {pnl_class} {row['symbol']:<8} {row['side']:<5}: "
                  f"PnL ${pnl:>7.2f} ({float(row['pnl_percent']):>5.1f}%)")
    
    # Show HTML report summary
    print("\n📄 report.html:")
    with open(artifacts['report']) as f:
        html = f.read()
    print(f"   - Size: {len(html):,} characters")
    print(f"   - Contains: Summary, Key Metrics, Trade Statistics")
    print(f"   - Strategy: EMA Crossover Strategy")
    
    # Validation
    print("\n5. Data Validation:")
    print("-" * 40)
    
    # Check all metrics are finite
    all_finite = all(
        isinstance(v, (int, float)) and not (v != v or v in [float('inf'), -float('inf')])
        for v in metrics_data.values()
    )
    print(f"   ✓ All metrics are finite numbers: {all_finite}")
    
    # Check CSV schemas
    with open(artifacts['equity']) as f:
        equity_headers = csv.DictReader(f).fieldnames
    print(f"   ✓ Equity CSV has required columns: {equity_headers == ['timestamp', 'equity', 'drawdown', 'returns']}")
    
    with open(artifacts['trades']) as f:
        trade_headers = csv.DictReader(f).fieldnames
    expected_trade_headers = ['entry_time', 'exit_time', 'symbol', 'side', 'entry_price', 
                              'exit_price', 'quantity', 'pnl', 'pnl_percent', 'commission']
    print(f"   ✓ Trades CSV has required columns: {trade_headers == expected_trade_headers}")
    
    # Check HTML contains summary
    has_summary = all(text in html for text in ['Summary', 'Key Metrics', 'Trade Statistics'])
    print(f"   ✓ HTML report contains summary sections: {has_summary}")
    
    print("\n" + "=" * 60)
    print("✅ DEMONSTRATION COMPLETE")
    print(f"\nAll standardized artifacts have been written to: ./{output_dir}/")
    print("\nFiles created:")
    print("  • report.html    - Human-readable HTML report with summary")
    print("  • metrics.json   - Performance metrics (sharpe, profit_factor, etc.)")
    print("  • equity.csv     - Equity curve time series data")
    print("  • trades.csv     - Detailed trade log with entry/exit data")
    print("=" * 60)


if __name__ == "__main__":
    main()