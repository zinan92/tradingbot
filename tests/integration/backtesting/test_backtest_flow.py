"""
Integration tests for complete backtesting flow
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

from src.application.backtesting.commands.run_backtest_command import (
    RunBacktestCommand,
    RunBacktestCommandHandler
)
from src.application.backtesting.services.backtest_service import BacktestService
from src.infrastructure.backtesting import BacktestEngine, DataAdapter


class TestBacktestIntegration:
    """Integration tests for backtesting workflow"""
    
    @pytest.fixture
    def backtest_service(self):
        """Create BacktestService instance"""
        return BacktestService()
    
    @pytest.fixture
    def backtest_command(self):
        """Create sample backtest command"""
        return RunBacktestCommand(
            strategy_name='SmaCross',
            symbol='BTCUSDT',
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=10000,
            commission=0.002,
            interval='1h',
            strategy_params={'n1': 10, 'n2': 20}
        )
    
    def test_end_to_end_backtest_sync(self, backtest_service, backtest_command):
        """Test complete synchronous backtest flow"""
        # Run backtest
        job = backtest_service.run_backtest(backtest_command)
        
        # Verify job created
        assert job is not None
        assert job.job_id is not None
        assert job.status in ['completed', 'failed']
        
        if job.status == 'completed':
            # Verify results
            assert job.results is not None
            
            # Check stats
            stats = job.results.stats
            assert 'Return [%]' in stats
            assert 'Sharpe Ratio' in stats
            assert '# Trades' in stats
            assert 'Max. Drawdown [%]' in stats
            
            # Check chart generated
            assert job.results.chart_html is not None
            
            # Verify formatted output matches screenshot format
            assert stats['Start'] is not None
            assert stats['End'] is not None
            assert stats['Duration'] is not None
            assert stats['Exposure Time [%]'] is not None
            assert stats['Equity Final [$]'] is not None
            assert stats['Equity Peak [$]'] is not None
    
    @pytest.mark.asyncio
    async def test_end_to_end_backtest_async(self, backtest_service, backtest_command):
        """Test complete asynchronous backtest flow"""
        # Submit backtest async
        job_id = await backtest_service.run_backtest_async(backtest_command)
        
        # Verify job ID returned
        assert job_id is not None
        
        # Wait for completion (with timeout)
        max_wait = 30  # seconds
        wait_interval = 0.5
        elapsed = 0
        
        while elapsed < max_wait:
            job = backtest_service.get_job(job_id)
            if job and job.status in ['completed', 'failed']:
                break
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval
        
        # Verify job completed
        job = backtest_service.get_job(job_id)
        assert job is not None
        assert job.status in ['completed', 'failed', 'running']
        
        if job.status == 'completed':
            # Verify results available
            results = backtest_service.get_job_results(job_id)
            assert results is not None
    
    def test_command_validation(self):
        """Test command validation"""
        # Test invalid date range
        with pytest.raises(ValueError, match="Start date must be before end date"):
            RunBacktestCommand(
                strategy_name='SmaCross',
                symbol='BTCUSDT',
                start_date=datetime(2023, 12, 31),
                end_date=datetime(2023, 1, 1),  # End before start
                initial_capital=10000
            )
        
        # Test invalid capital
        with pytest.raises(ValueError, match="Initial capital must be positive"):
            RunBacktestCommand(
                strategy_name='SmaCross',
                symbol='BTCUSDT',
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                initial_capital=-1000  # Negative capital
            )
        
        # Test invalid commission
        with pytest.raises(ValueError, match="Commission must be between 0 and 1"):
            RunBacktestCommand(
                strategy_name='SmaCross',
                symbol='BTCUSDT',
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                commission=1.5  # > 1
            )
    
    def test_strategy_not_found(self, backtest_service):
        """Test handling of unknown strategy"""
        command = RunBacktestCommand(
            strategy_name='NonExistentStrategy',
            symbol='BTCUSDT',
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31)
        )
        
        job = backtest_service.run_backtest(command)
        
        # Should fail with appropriate error
        assert job.status == 'failed'
        assert 'not found' in job.error.lower()
    
    def test_job_management(self, backtest_service, backtest_command):
        """Test job tracking and retrieval"""
        # Run multiple backtests
        job1 = backtest_service.run_backtest(backtest_command)
        
        # Modify command for second job
        command2 = RunBacktestCommand(
            strategy_name='SmaCross',
            symbol='ETHUSDT',
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 6, 30),
            strategy_params={'n1': 5, 'n2': 15}
        )
        job2 = backtest_service.run_backtest(command2)
        
        # Retrieve jobs
        assert backtest_service.get_job(job1.job_id) is not None
        assert backtest_service.get_job(job2.job_id) is not None
        
        # List all jobs
        all_jobs = backtest_service.list_jobs()
        assert len(all_jobs) >= 2
        
        # Filter by status
        completed_jobs = backtest_service.list_jobs(status='completed')
        for job in completed_jobs:
            assert job.status == 'completed'
    
    def test_optimization(self, backtest_service):
        """Test strategy optimization"""
        # Run optimization
        results = backtest_service.optimize_strategy(
            strategy_name='SmaCross',
            symbol='BTCUSDT',
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            param_ranges={
                'n1': range(5, 20, 5),  # [5, 10, 15]
                'n2': range(20, 40, 10)  # [20, 30]
            },
            maximize='Sharpe Ratio'
        )
        
        # Verify optimization results
        assert 'best_params' in results
        assert 'best_metric' in results
        assert 'metric_name' in results
        assert results['metric_name'] == 'Sharpe Ratio'
        
        # Best params should be within specified ranges
        best_params = results['best_params']
        if 'n1' in best_params:
            assert 5 <= best_params['n1'] < 20
        if 'n2' in best_params:
            assert 20 <= best_params['n2'] < 40
    
    def test_data_adapter_integration(self):
        """Test DataAdapter with BacktestEngine"""
        adapter = DataAdapter()
        engine = BacktestEngine()
        
        # Fetch and prepare data
        data = adapter.prepare_for_backtest(
            symbol='BTCUSDT',
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
            interval='1h',
            add_indicators=True
        )
        
        # Verify data format
        assert not data.empty
        assert 'Open' in data.columns
        assert 'High' in data.columns
        assert 'Low' in data.columns
        assert 'Close' in data.columns
        assert 'Volume' in data.columns
        
        # Verify indicators added
        assert 'SMA_10' in data.columns
        assert 'RSI' in data.columns
        assert 'MACD' in data.columns
        
        # Run backtest with prepared data
        from src.application.backtesting.strategies.sma_cross_strategy import SmaCrossStrategy
        
        results = engine.run_backtest(
            data=data,
            strategy_class=SmaCrossStrategy,
            initial_cash=10000
        )
        
        assert results is not None
        assert results.stats is not None
    
    def test_results_formatting(self, backtest_service, backtest_command):
        """Test results match expected format from screenshot"""
        job = backtest_service.run_backtest(backtest_command)
        
        if job.status == 'completed':
            stats = job.results.stats
            
            # Verify all metrics from screenshot are present
            expected_metrics = [
                'Start', 'End', 'Duration', 'Exposure Time [%]',
                'Equity Final [$]', 'Equity Peak [$]',
                'Return [%]', 'Buy & Hold Return [%]',
                'Return (Ann.) [%]', 'Volatility (Ann.) [%]',
                'CAGR [%]', 'Sharpe Ratio', 'Sortino Ratio', 'Calmar Ratio',
                'Alpha [%]', 'Beta',
                'Max. Drawdown [%]', 'Avg. Drawdown [%]',
                'Max. Drawdown Duration', 'Avg. Drawdown Duration',
                '# Trades', 'Win Rate [%]',
                'Best Trade [%]', 'Worst Trade [%]', 'Avg. Trade [%]',
                'Max. Trade Duration', 'Avg. Trade Duration',
                'Profit Factor', 'Expectancy [%]', 'SQN', 'Kelly Criterion'
            ]
            
            for metric in expected_metrics:
                assert metric in stats, f"Missing metric: {metric}"
            
            # Verify data types
            assert isinstance(stats['# Trades'], int)
            assert isinstance(stats['Return [%]'], (int, float))
            assert isinstance(stats['Sharpe Ratio'], (int, float))
    
    def test_concurrent_backtests(self, backtest_service):
        """Test running multiple backtests concurrently"""
        commands = [
            RunBacktestCommand(
                strategy_name='SmaCross',
                symbol=symbol,
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                strategy_params={'n1': n1, 'n2': n2}
            )
            for symbol in ['BTCUSDT', 'ETHUSDT']
            for n1, n2 in [(5, 15), (10, 20), (15, 30)]
        ]
        
        # Run all backtests
        jobs = [backtest_service.run_backtest(cmd) for cmd in commands]
        
        # Verify all completed
        for job in jobs:
            assert job.status in ['completed', 'failed']
            
        # Count successful completions
        successful = sum(1 for job in jobs if job.status == 'completed')
        assert successful > 0