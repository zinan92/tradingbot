"""
Tests for Batch Backtest Engine

Verifies parameter optimization, leaderboard generation, and best parameter selection.
"""
import pytest
import asyncio
import csv
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import shutil

from src.infrastructure.backtesting.batch_backtest_engine import BatchBacktestEngine


class MockBacktestEngine:
    """Mock single backtest engine for testing"""
    
    def __init__(self, results_map: Dict[str, Dict[str, float]] = None):
        """
        Initialize with optional results map
        
        Args:
            results_map: Map of param combinations to metrics
        """
        self.results_map = results_map or {}
        self.run_count = 0
    
    async def run(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a mock backtest"""
        self.run_count += 1
        params = config.get('params', {})
        
        # Generate deterministic results based on parameters
        param_key = str(sorted(params.items()))
        
        if param_key in self.results_map:
            metrics = self.results_map[param_key]
        else:
            # Default calculation based on parameters
            fast = params.get('fast_period', 10)
            slow = params.get('slow_period', 50)
            stop_loss = params.get('stop_loss', 0.02)
            
            # Calculate metrics based on parameters
            ratio = slow / fast if fast > 0 else 1
            
            # Better ratio = better Sharpe
            if 3 <= ratio <= 5:
                sharpe = 2.0
            elif 2 <= ratio <= 6:
                sharpe = 1.5
            else:
                sharpe = 0.8
            
            # Tighter stop loss = lower drawdown
            max_dd = 10 + (stop_loss * 100)
            
            metrics = {
                'sharpe': sharpe,
                'profit_factor': 1.5 + sharpe * 0.5,
                'win_rate': 50 + sharpe * 10,
                'max_dd': max_dd,
                'returns': sharpe * 20,
                'total_trades': 100
            }
        
        return {'metrics': metrics}
    
    async def validate_config(self, config: Dict[str, Any]):
        return True, None
    
    async def estimate_duration(self, config: Dict[str, Any]):
        return 1.0
    
    async def get_available_data_range(self, symbol: str, interval: str):
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=365)
        return start, end


class MockStrategyRegistry:
    """Mock strategy registry for testing"""
    
    def __init__(self):
        self.strategies = {}
    
    async def register(self, name: str, version: str, params: Dict[str, Any], metadata: Dict[str, Any]):
        """Register strategy parameters"""
        key = f"{name}:{version}"
        self.strategies[key] = {
            'params': params,
            'metadata': metadata
        }
    
    def get_strategy(self, name: str, version: str) -> Dict[str, Any]:
        """Get registered strategy"""
        key = f"{name}:{version}"
        return self.strategies.get(key)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test outputs"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_backtest_engine():
    """Create mock backtest engine"""
    return MockBacktestEngine()


@pytest.fixture
def mock_registry():
    """Create mock strategy registry"""
    return MockStrategyRegistry()


@pytest.mark.asyncio
async def test_batch_backtest_generates_combinations(temp_dir, mock_backtest_engine, mock_registry):
    """Test that batch backtest generates all parameter combinations"""
    
    engine = BatchBacktestEngine(
        backtest_engine=mock_backtest_engine,
        strategy_registry=mock_registry,
        output_dir=str(temp_dir)
    )
    
    search_space = {
        'fast_period': [10, 20],
        'slow_period': [50, 100],
        'stop_loss': [0.01, 0.02]
    }
    
    base_config = {
        'symbol': 'BTCUSDT',
        'initial_capital': 10000
    }
    
    best_params, leaderboard_path = await engine.run_batch(
        strategy_name='TestStrategy',
        search_space=search_space,
        base_config=base_config
    )
    
    # Should have run 2 * 2 * 2 = 8 combinations
    assert mock_backtest_engine.run_count == 8
    
    # Leaderboard should exist
    assert leaderboard_path.exists()
    
    # Best params should be selected
    assert best_params is not None
    assert 'fast_period' in best_params
    assert 'slow_period' in best_params
    assert 'stop_loss' in best_params


@pytest.mark.asyncio
async def test_best_parameter_selection_by_sharpe(temp_dir):
    """Test that best parameters are selected by highest Sharpe ratio"""
    
    # Create engine with specific results
    results_map = {
        str(sorted([('fast', 10), ('slow', 50)])): {
            'sharpe': 1.5, 'max_dd': 15, 'returns': 30,
            'profit_factor': 2.0, 'win_rate': 60, 'total_trades': 100
        },
        str(sorted([('fast', 20), ('slow', 50)])): {
            'sharpe': 2.0,  # Best Sharpe
            'max_dd': 12, 
            'returns': 40,
            'profit_factor': 2.5, 'win_rate': 65, 'total_trades': 120
        },
        str(sorted([('fast', 30), ('slow', 50)])): {
            'sharpe': 1.2, 'max_dd': 18, 'returns': 25,
            'profit_factor': 1.8, 'win_rate': 55, 'total_trades': 90
        }
    }
    
    mock_engine = MockBacktestEngine(results_map)
    batch_engine = BatchBacktestEngine(
        backtest_engine=mock_engine,
        output_dir=str(temp_dir)
    )
    
    search_space = {
        'fast': [10, 20, 30],
        'slow': [50]
    }
    
    best_params, _ = await batch_engine.run_batch(
        strategy_name='TestStrategy',
        search_space=search_space,
        base_config={}
    )
    
    # Should select fast=20 (highest Sharpe of 2.0)
    assert best_params['fast'] == 20
    assert best_params['slow'] == 50


@pytest.mark.asyncio
async def test_max_drawdown_tiebreaker(temp_dir):
    """Test that MaxDD is used as tiebreaker when Sharpe ratios are equal"""
    
    # Create engine with equal Sharpe but different MaxDD
    results_map = {
        str(sorted([('stop_loss', 0.01)])): {
            'sharpe': 1.5,
            'max_dd': 10,  # Lower MaxDD - should win
            'returns': 30,
            'profit_factor': 2.0, 'win_rate': 60, 'total_trades': 100
        },
        str(sorted([('stop_loss', 0.02)])): {
            'sharpe': 1.5,  # Same Sharpe
            'max_dd': 15,   # Higher MaxDD
            'returns': 30,
            'profit_factor': 2.0, 'win_rate': 60, 'total_trades': 100
        },
        str(sorted([('stop_loss', 0.03)])): {
            'sharpe': 1.5,  # Same Sharpe
            'max_dd': 20,   # Highest MaxDD
            'returns': 30,
            'profit_factor': 2.0, 'win_rate': 60, 'total_trades': 100
        }
    }
    
    mock_engine = MockBacktestEngine(results_map)
    batch_engine = BatchBacktestEngine(
        backtest_engine=mock_engine,
        output_dir=str(temp_dir)
    )
    
    search_space = {
        'stop_loss': [0.01, 0.02, 0.03]
    }
    
    best_params, _ = await batch_engine.run_batch(
        strategy_name='TestStrategy',
        search_space=search_space,
        base_config={}
    )
    
    # Should select stop_loss=0.01 (lowest MaxDD with same Sharpe)
    assert best_params['stop_loss'] == 0.01


@pytest.mark.asyncio
async def test_leaderboard_generation(temp_dir, mock_backtest_engine):
    """Test that leaderboard CSV is generated correctly"""
    
    engine = BatchBacktestEngine(
        backtest_engine=mock_backtest_engine,
        output_dir=str(temp_dir)
    )
    
    search_space = {
        'fast_period': [10, 20],
        'slow_period': [50, 100]
    }
    
    best_params, leaderboard_path = await engine.run_batch(
        strategy_name='MovingAverage',
        search_space=search_space,
        base_config={'symbol': 'BTCUSDT'}
    )
    
    # Read leaderboard
    with open(leaderboard_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Should have 4 rows (2x2 combinations)
    assert len(rows) == 4
    
    # Check columns exist
    assert 'rank' in rows[0]
    assert 'strategy' in rows[0]
    assert 'sharpe' in rows[0]
    assert 'max_dd' in rows[0]
    assert 'profit_factor' in rows[0]
    assert 'win_rate' in rows[0]
    assert 'returns' in rows[0]
    assert 'total_trades' in rows[0]
    assert 'status' in rows[0]
    assert 'param_fast_period' in rows[0]
    assert 'param_slow_period' in rows[0]
    
    # Check ranking (should be sorted by Sharpe desc, then MaxDD asc)
    for i in range(len(rows) - 1):
        current = float(rows[i]['sharpe'])
        next_sharpe = float(rows[i + 1]['sharpe'])
        
        # Sharpe should be non-increasing
        assert current >= next_sharpe
        
        # If Sharpe is equal, MaxDD should be non-decreasing
        if current == next_sharpe:
            assert float(rows[i]['max_dd']) <= float(rows[i + 1]['max_dd'])
    
    # All strategies should be 'MovingAverage'
    assert all(row['strategy'] == 'MovingAverage' for row in rows)


@pytest.mark.asyncio
async def test_registry_persistence(temp_dir, mock_backtest_engine, mock_registry):
    """Test that best parameters are persisted to strategy registry"""
    
    engine = BatchBacktestEngine(
        backtest_engine=mock_backtest_engine,
        strategy_registry=mock_registry,
        output_dir=str(temp_dir)
    )
    
    search_space = {
        'fast_period': [10, 20],
        'slow_period': [50, 100]
    }
    
    best_params, _ = await engine.run_batch(
        strategy_name='TestStrategy',
        search_space=search_space,
        base_config={}
    )
    
    # Check registry was updated
    registered = mock_registry.get_strategy('TestStrategy', 'optimized')
    assert registered is not None
    
    # Check params were saved
    assert registered['params'] == best_params
    
    # Check metadata was saved
    assert 'sharpe' in registered['metadata']
    assert 'max_dd' in registered['metadata']
    assert 'returns' in registered['metadata']
    assert 'optimized_at' in registered['metadata']
    assert registered['metadata']['optimization_method'] == 'grid_search'


@pytest.mark.asyncio
async def test_empty_search_space(temp_dir, mock_backtest_engine):
    """Test handling of empty search space"""
    
    engine = BatchBacktestEngine(
        backtest_engine=mock_backtest_engine,
        output_dir=str(temp_dir)
    )
    
    # Empty search space
    search_space = {}
    
    best_params, leaderboard_path = await engine.run_batch(
        strategy_name='TestStrategy',
        search_space=search_space,
        base_config={}
    )
    
    # Should run once with no parameters
    assert mock_backtest_engine.run_count == 1
    
    # Best params should be empty
    assert best_params == {}
    
    # Leaderboard should still be created
    assert leaderboard_path.exists()


@pytest.mark.asyncio
async def test_failed_backtests_handling(temp_dir):
    """Test handling of failed backtests"""
    
    class FailingBacktestEngine:
        async def run(self, config):
            # Fail for certain parameters
            if config.get('params', {}).get('fail', False):
                raise Exception("Simulated failure")
            return {'metrics': {'sharpe': 1.0, 'max_dd': 10, 'returns': 20,
                               'profit_factor': 1.5, 'win_rate': 55, 'total_trades': 50}}
        
        async def validate_config(self, config):
            return True, None
        
        async def estimate_duration(self, config):
            return 1.0
        
        async def get_available_data_range(self, symbol, interval):
            from datetime import datetime, timedelta
            return datetime.now() - timedelta(days=365), datetime.now()
    
    engine = BatchBacktestEngine(
        backtest_engine=FailingBacktestEngine(),
        output_dir=str(temp_dir)
    )
    
    search_space = {
        'fail': [True, False],
        'param': [1, 2]
    }
    
    best_params, leaderboard_path = await engine.run_batch(
        strategy_name='TestStrategy',
        search_space=search_space,
        base_config={}
    )
    
    # Should select from successful runs only
    assert best_params['fail'] == False
    
    # Read leaderboard
    with open(leaderboard_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Failed runs should be at the bottom with negative Sharpe
    failed_rows = [r for r in rows if 'failed' in r['status']]
    successful_rows = [r for r in rows if r['status'] == 'success']
    
    assert len(failed_rows) == 2  # fail=True with param=[1,2]
    assert len(successful_rows) == 2  # fail=False with param=[1,2]
    
    # All failed should have worse rank than successful
    if failed_rows and successful_rows:
        worst_success_rank = max(int(r['rank']) for r in successful_rows)
        best_failed_rank = min(int(r['rank']) for r in failed_rows)
        assert best_failed_rank > worst_success_rank


@pytest.mark.asyncio
async def test_parameter_grid_size():
    """Test calculation of parameter grid size"""
    
    engine = BatchBacktestEngine(
        backtest_engine=MockBacktestEngine(),
        output_dir='temp'
    )
    
    # Test various search spaces
    test_cases = [
        ({}, 1),  # Empty = 1 combination
        ({'a': [1, 2, 3]}, 3),  # Single param
        ({'a': [1, 2], 'b': [3, 4]}, 4),  # 2x2
        ({'a': [1, 2], 'b': [3, 4], 'c': [5, 6, 7]}, 12),  # 2x2x3
        ({'a': [1], 'b': [2], 'c': [3]}, 1),  # All single values
    ]
    
    for search_space, expected_size in test_cases:
        combinations = engine._generate_param_combinations(search_space)
        assert len(combinations) == expected_size


def test_leaderboard_csv_format(temp_dir):
    """Test that leaderboard CSV has correct format"""
    
    engine = BatchBacktestEngine(
        backtest_engine=MockBacktestEngine(),
        output_dir=str(temp_dir)
    )
    
    # Create mock results
    results = [
        {
            'params': {'fast': 10, 'slow': 50},
            'sharpe': 2.0,
            'max_dd': 10,
            'profit_factor': 2.5,
            'win_rate': 65,
            'returns': 40,
            'total_trades': 100,
            'status': 'success'
        },
        {
            'params': {'fast': 20, 'slow': 50},
            'sharpe': 1.5,
            'max_dd': 15,
            'profit_factor': 2.0,
            'win_rate': 60,
            'returns': 30,
            'total_trades': 80,
            'status': 'success'
        }
    ]
    
    leaderboard_path = engine._write_leaderboard(results, 'TestStrategy')
    
    # Read and verify
    with open(leaderboard_path, 'r') as f:
        content = f.read()
        
        # Check header (now includes extended metrics)
        assert 'rank,strategy,sharpe,calmar_ratio,max_dd' in content
        assert 'param_fast' in content
        assert 'param_slow' in content
        
        # Check data rows
        lines = content.strip().split('\n')
        assert len(lines) == 3  # Header + 2 data rows
        
        # Parse CSV
        reader = csv.DictReader(lines)
        rows = list(reader)
        
        # First row should be best (highest Sharpe)
        assert rows[0]['rank'] == '1'
        assert float(rows[0]['sharpe']) == 2.0
        assert rows[0]['param_fast'] == '10'


@pytest.mark.asyncio
async def test_concurrent_execution(temp_dir, mock_backtest_engine):
    """Test that concurrent execution works correctly"""
    
    # Track execution times
    execution_times = []
    
    class TimedBacktestEngine:
        async def run(self, config):
            start = time.time()
            await asyncio.sleep(0.1)  # Simulate work
            execution_times.append(time.time() - start)
            return {'metrics': {'sharpe': 1.5, 'max_dd': 10, 'returns': 20,
                               'profit_factor': 2.0, 'win_rate': 60, 'total_trades': 100}}
        
        async def validate_config(self, config):
            return True, None
        
        async def estimate_duration(self, config):
            return 0.1
        
        async def get_available_data_range(self, symbol, interval):
            from datetime import datetime, timedelta
            return datetime.now() - timedelta(days=365), datetime.now()
    
    # Test with concurrent execution
    engine = BatchBacktestEngine(
        backtest_engine=TimedBacktestEngine(),
        output_dir=str(temp_dir),
        max_workers=4  # Enable concurrency
    )
    
    search_space = {
        'param1': [1, 2, 3],
        'param2': [10, 20]
    }
    
    start_time = time.time()
    best_params, leaderboard_path = await engine.run_batch(
        strategy_name='ConcurrentTest',
        search_space=search_space,
        base_config={}
    )
    
    total_time = time.time() - start_time
    
    # Should have run 6 combinations
    assert len(execution_times) == 6
    
    # With concurrency, total time should be less than sequential time
    # Sequential would take ~0.6s (6 * 0.1s), concurrent should be ~0.2s (2 batches)
    assert total_time < 0.4  # Allow some overhead
    
    # Results should still be correct
    assert best_params is not None
    assert leaderboard_path.exists()


@pytest.mark.asyncio
async def test_search_space_validation(temp_dir, mock_backtest_engine):
    """Test that search space size validation works"""
    
    engine = BatchBacktestEngine(
        backtest_engine=mock_backtest_engine,
        output_dir=str(temp_dir),
        max_search_space=100  # Set low limit for testing
    )
    
    # Create search space that exceeds limit
    large_search_space = {
        'param1': list(range(20)),  # 20 values
        'param2': list(range(10)),  # 10 values  
        'param3': list(range(5))    # 5 values
        # Total: 20 * 10 * 5 = 1000 combinations
    }
    
    with pytest.raises(ValueError, match="Search space too large"):
        await engine.run_batch(
            strategy_name='TestStrategy',
            search_space=large_search_space,
            base_config={}
        )
    
    # Empty search space should also raise
    with pytest.raises(ValueError, match="Empty search space"):
        await engine.run_batch(
            strategy_name='TestStrategy',
            search_space={'param1': []},
            base_config={}
        )


@pytest.mark.asyncio
async def test_extended_metrics_in_leaderboard(temp_dir, mock_backtest_engine):
    """Test that extended metrics are included in leaderboard"""
    
    engine = BatchBacktestEngine(
        backtest_engine=mock_backtest_engine,
        output_dir=str(temp_dir)
    )
    
    search_space = {
        'fast_period': [10, 20],
        'slow_period': [50]
    }
    
    best_params, leaderboard_path = await engine.run_batch(
        strategy_name='TestStrategy',
        search_space=search_space,
        base_config={}
    )
    
    # Read leaderboard
    with open(leaderboard_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Check extended metrics columns exist
    assert 'calmar_ratio' in rows[0]
    assert 'recovery_factor' in rows[0]
    assert 'avg_profit_per_trade' in rows[0]
    assert 'risk_reward_ratio' in rows[0]
    
    # Check values are calculated
    for row in rows:
        if row['status'] == 'success':
            assert float(row['calmar_ratio']) != 0
            assert float(row['recovery_factor']) >= 0
    
    # Check optimization summary was created
    summary_path = temp_dir / "optimization_summary.json"
    assert summary_path.exists()
    
    with open(summary_path, 'r') as f:
        summary = json.load(f)
    
    assert 'strategy' in summary
    assert 'total_combinations' in summary
    assert 'successful_runs' in summary
    assert 'best_sharpe' in summary
    assert 'avg_sharpe' in summary
    assert 'best_max_dd' in summary
    assert 'timestamp' in summary


@pytest.mark.asyncio
async def test_sequential_fallback(temp_dir, mock_backtest_engine):
    """Test that sequential execution works when max_workers=1"""
    
    engine = BatchBacktestEngine(
        backtest_engine=mock_backtest_engine,
        output_dir=str(temp_dir),
        max_workers=1  # Force sequential execution
    )
    
    search_space = {
        'param1': [1, 2],
        'param2': [10, 20]
    }
    
    best_params, leaderboard_path = await engine.run_batch(
        strategy_name='SequentialTest',
        search_space=search_space,
        base_config={}
    )
    
    # Should complete successfully
    assert best_params is not None
    assert leaderboard_path.exists()
    
    # Should have run all combinations
    with open(leaderboard_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 4  # 2 * 2 combinations


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])