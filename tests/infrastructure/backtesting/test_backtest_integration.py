"""
Integration test for backtest with artifact generation

Demonstrates the complete flow from backtest to standardized artifacts.
"""
import pytest
import json
import csv
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import tempfile
import shutil

from src.infrastructure.backtesting.artifact_writer import BacktestArtifactWriter


class MockBacktestEngine:
    """Mock backtest engine for testing"""
    
    def run_backtest(self, strategy_name: str, **params):
        """Run a mock backtest and return results"""
        
        # Generate mock equity curve
        initial_capital = float(params.get('initial_capital', 10000))
        days = 30
        equity_curve = []
        current_equity = initial_capital
        
        for i in range(days):
            # Simulate some volatility
            daily_return = (i % 3 - 1) * 0.02  # -2%, 0%, +2% pattern
            current_equity *= (1 + daily_return)
            drawdown = max(0, (initial_capital - current_equity) / initial_capital * 100)
            total_return = (current_equity - initial_capital) / initial_capital * 100
            
            equity_curve.append({
                'timestamp': (datetime.now() - timedelta(days=days-i)).strftime('%Y-%m-%d %H:%M:%S'),
                'equity': current_equity,
                'drawdown': drawdown,
                'returns': total_return
            })
        
        # Generate mock trades
        trades = []
        for i in range(10):
            entry_time = datetime.now() - timedelta(days=25-i*2)
            exit_time = entry_time + timedelta(hours=4)
            
            # Mix of winning and losing trades
            is_winner = i % 3 != 0
            pnl = 50 if is_winner else -30
            pnl_percent = 1.0 if is_winner else -0.6
            
            trades.append({
                'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                'exit_time': exit_time.strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': 'BTCUSDT' if i % 2 == 0 else 'ETHUSDT',
                'side': 'long' if i % 2 == 0 else 'short',
                'entry_price': 45000 if i % 2 == 0 else 3000,
                'exit_price': 45000 + (pnl * 10) if i % 2 == 0 else 3000 + pnl,
                'quantity': 0.1 if i % 2 == 0 else 1.0,
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'commission': 2.0
            })
        
        # Calculate metrics
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        total_profit = sum(t['pnl'] for t in winning_trades)
        total_loss = abs(sum(t['pnl'] for t in losing_trades))
        
        metrics = {
            'sharpe': 1.2,
            'profit_factor': total_profit / total_loss if total_loss > 0 else 0,
            'win_rate': len(winning_trades) / len(trades) * 100 if trades else 0,
            'max_dd': max(p['drawdown'] for p in equity_curve),
            'returns': equity_curve[-1]['returns'],
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'avg_win': total_profit / len(winning_trades) if winning_trades else 0,
            'avg_loss': total_loss / len(losing_trades) if losing_trades else 0
        }
        
        return {
            'metrics': metrics,
            'equity_curve': equity_curve,
            'trades': trades,
            'metadata': {
                'strategy': strategy_name,
                'start_date': equity_curve[0]['timestamp'],
                'end_date': equity_curve[-1]['timestamp'],
                'initial_capital': initial_capital,
                **params
            }
        }


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for artifacts"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


def test_complete_backtest_workflow(temp_output_dir):
    """Test complete workflow from backtest to artifacts"""
    
    # 1. Run backtest
    engine = MockBacktestEngine()
    results = engine.run_backtest(
        'MovingAverageCrossover',
        initial_capital=10000,
        fast_period=10,
        slow_period=20,
        symbol='BTCUSDT'
    )
    
    # 2. Write artifacts
    writer = BacktestArtifactWriter(str(temp_output_dir))
    artifacts = writer.write_all_artifacts(
        results['metrics'],
        results['equity_curve'],
        results['trades'],
        'MovingAverageCrossover',
        results['metadata']
    )
    
    # 3. Verify all artifacts exist
    assert (temp_output_dir / 'metrics.json').exists()
    assert (temp_output_dir / 'equity.csv').exists()
    assert (temp_output_dir / 'trades.csv').exists()
    assert (temp_output_dir / 'report.html').exists()
    
    # 4. Verify metrics.json structure
    with open(temp_output_dir / 'metrics.json') as f:
        metrics = json.load(f)
    
    required_keys = ['sharpe', 'profit_factor', 'win_rate', 'max_dd', 'returns']
    for key in required_keys:
        assert key in metrics, f"Missing required metric: {key}"
        assert isinstance(metrics[key], (int, float)), f"{key} should be numeric"
    
    # 5. Verify equity.csv structure
    with open(temp_output_dir / 'equity.csv') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    
    assert headers == ['timestamp', 'equity', 'drawdown', 'returns']
    assert len(rows) == 30  # 30 days of data
    
    # Check first and last rows have valid data
    assert rows[0]['timestamp']
    assert float(rows[0]['equity']) > 0
    assert float(rows[-1]['equity']) > 0
    
    # 6. Verify trades.csv structure
    with open(temp_output_dir / 'trades.csv') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    
    expected_headers = [
        'entry_time', 'exit_time', 'symbol', 'side',
        'entry_price', 'exit_price', 'quantity',
        'pnl', 'pnl_percent', 'commission'
    ]
    assert headers == expected_headers
    assert len(rows) == 10  # 10 trades
    
    # 7. Verify HTML report contains summary
    with open(temp_output_dir / 'report.html') as f:
        html = f.read()
    
    assert '<h1>Backtest Report: MovingAverageCrossover</h1>' in html
    assert 'Summary' in html
    assert 'Key Metrics' in html
    assert 'Trade Statistics' in html
    assert 'Strategy Parameters' in html
    
    # Check that metadata is included
    assert 'fast_period' in html
    assert '10' in html  # fast_period value
    assert 'slow_period' in html
    assert '20' in html  # slow_period value
    
    print(f"\n✅ All artifacts generated successfully in: {temp_output_dir}")
    print(f"  - metrics.json: {metrics}")
    print(f"  - equity.csv: {len(rows)} days of equity data")
    print(f"  - trades.csv: 10 trades recorded")
    print(f"  - report.html: Complete HTML report with summary")


def test_artifact_consistency(temp_output_dir):
    """Test that artifacts are consistent with each other"""
    
    # Run backtest
    engine = MockBacktestEngine()
    results = engine.run_backtest('TestStrategy', initial_capital=10000)
    
    # Write artifacts
    writer = BacktestArtifactWriter(str(temp_output_dir))
    artifacts = writer.write_all_artifacts(
        results['metrics'],
        results['equity_curve'],
        results['trades'],
        'TestStrategy',
        results['metadata']
    )
    
    # Load all artifacts
    with open(temp_output_dir / 'metrics.json') as f:
        metrics = json.load(f)
    
    with open(temp_output_dir / 'trades.csv') as f:
        reader = csv.DictReader(f)
        trades = list(reader)
    
    with open(temp_output_dir / 'equity.csv') as f:
        reader = csv.DictReader(f)
        equity = list(reader)
    
    # Verify consistency
    # Total trades in metrics should match trades.csv
    assert metrics['total_trades'] == len(trades)
    
    # Win rate calculation
    winning = sum(1 for t in trades if float(t['pnl']) > 0)
    expected_win_rate = (winning / len(trades) * 100) if trades else 0
    assert abs(metrics['win_rate'] - expected_win_rate) < 0.1
    
    # Final returns should match last equity point
    final_returns = float(equity[-1]['returns'])
    assert abs(metrics['returns'] - final_returns) < 0.1
    
    print("\n✅ All artifacts are consistent with each other")


def test_artifacts_handle_edge_cases(temp_output_dir):
    """Test that artifacts handle edge cases properly"""
    
    # Test with no trades
    writer = BacktestArtifactWriter(str(temp_output_dir))
    
    artifacts = writer.write_all_artifacts(
        metrics={'sharpe': float('nan'), 'profit_factor': float('inf')},
        equity_curve=[],
        trades=[],
        strategy_name='EmptyStrategy',
        metadata=None
    )
    
    # Should still create all files
    assert all(p.exists() for p in artifacts.values())
    
    # Metrics should have sanitized values
    with open(temp_output_dir / 'metrics.json') as f:
        metrics = json.load(f)
    
    assert metrics['sharpe'] == 0.0  # NaN converted to 0
    assert metrics['profit_factor'] == 0.0  # Inf converted to 0
    
    # CSV files should have headers even if empty
    with open(temp_output_dir / 'equity.csv') as f:
        lines = f.readlines()
    assert lines[0].strip() == 'timestamp,equity,drawdown,returns'
    
    with open(temp_output_dir / 'trades.csv') as f:
        lines = f.readlines()
    assert 'entry_time' in lines[0]
    
    print("\n✅ Edge cases handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])