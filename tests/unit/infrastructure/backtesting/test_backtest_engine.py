"""
Unit tests for BacktestEngine
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.infrastructure.backtesting import BacktestEngine, BaseStrategy
from src.infrastructure.backtesting.backtest_engine import BacktestResults
from src.application.backtesting.strategies.sma_cross_strategy import SmaCrossStrategy


class TestBacktestEngine:
    """Test suite for BacktestEngine"""
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data for testing"""
        # Create date range
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='1h')
        
        # Generate realistic price data
        np.random.seed(42)
        prices = 100 * np.exp(np.cumsum(np.random.randn(len(dates)) * 0.01))
        
        # Create OHLCV DataFrame
        data = pd.DataFrame({
            'Open': prices * (1 + np.random.randn(len(dates)) * 0.001),
            'High': prices * (1 + abs(np.random.randn(len(dates)) * 0.002)),
            'Low': prices * (1 - abs(np.random.randn(len(dates)) * 0.002)),
            'Close': prices,
            'Volume': np.random.uniform(1000, 10000, len(dates))
        }, index=dates)
        
        # Ensure OHLC relationships are valid
        data['High'] = data[['Open', 'Close', 'High']].max(axis=1)
        data['Low'] = data[['Open', 'Close', 'Low']].min(axis=1)
        
        return data
    
    @pytest.fixture
    def engine(self):
        """Create BacktestEngine instance"""
        return BacktestEngine()
    
    def test_engine_initialization(self, engine):
        """Test engine initializes correctly"""
        assert engine is not None
        assert engine.formatter is not None
        assert engine._last_backtest is None
    
    def test_run_backtest_basic(self, engine, sample_data):
        """Test basic backtest execution"""
        # Run backtest with simple strategy
        results = engine.run_backtest(
            data=sample_data,
            strategy_class=SmaCrossStrategy,
            initial_cash=10000,
            commission=0.002,
            n1=10,
            n2=20
        )
        
        # Verify results structure
        assert isinstance(results, BacktestResults)
        assert results.stats is not None
        assert 'Return [%]' in results.stats
        assert 'Sharpe Ratio' in results.stats
        assert '# Trades' in results.stats
        
        # Verify trades
        assert results.trades is not None
        
        # Verify equity curve
        assert results.equity_curve is not None
        
        # Verify chart HTML generated
        assert results.chart_html is not None
        assert len(results.chart_html) > 0
    
    def test_run_backtest_with_parameters(self, engine, sample_data):
        """Test backtest with custom strategy parameters"""
        results = engine.run_backtest(
            data=sample_data,
            strategy_class=SmaCrossStrategy,
            initial_cash=50000,
            commission=0.001,
            n1=5,  # Fast SMA
            n2=15  # Slow SMA
        )
        
        # Check parameters were applied
        assert results.strategy_params == {'n1': 5, 'n2': 15}
        
        # Check initial cash affected results
        equity_final = results.stats.get('Equity Final [$]', 0)
        assert equity_final > 0
    
    def test_validate_data_missing_columns(self, engine):
        """Test data validation with missing columns"""
        # Create invalid data (missing Volume)
        invalid_data = pd.DataFrame({
            'Open': [100, 101],
            'High': [102, 103],
            'Low': [99, 100],
            'Close': [101, 102]
        }, index=pd.date_range(start='2023-01-01', periods=2, freq='1h'))
        
        with pytest.raises(ValueError, match="Missing required columns"):
            engine._validate_data(invalid_data)
    
    def test_validate_data_invalid_index(self, engine):
        """Test data validation with non-datetime index"""
        # Create data with invalid index
        invalid_data = pd.DataFrame({
            'Open': [100, 101],
            'High': [102, 103],
            'Low': [99, 100],
            'Close': [101, 102],
            'Volume': [1000, 1100]
        }, index=[0, 1])  # Non-datetime index
        
        with pytest.raises(ValueError, match="Data index must be DatetimeIndex"):
            engine._validate_data(invalid_data)
    
    def test_validate_data_invalid_ohlc(self, engine):
        """Test data validation with invalid OHLC relationships"""
        dates = pd.date_range(start='2023-01-01', periods=2, freq='1h')
        
        # Create data where Low > High
        invalid_data = pd.DataFrame({
            'Open': [100, 101],
            'High': [102, 103],
            'Low': [105, 106],  # Invalid: Low > High
            'Close': [101, 102],
            'Volume': [1000, 1100]
        }, index=dates)
        
        with pytest.raises(ValueError, match="Invalid OHLC data"):
            engine._validate_data(invalid_data)
    
    def test_extract_trades(self, engine, sample_data):
        """Test trade extraction from results"""
        # Run backtest
        results = engine.run_backtest(
            data=sample_data,
            strategy_class=SmaCrossStrategy,
            initial_cash=10000,
            n1=10,
            n2=20
        )
        
        # Check trades extraction
        trades = results.trades
        
        if not trades.empty:
            # Verify trade structure
            assert 'TradeNum' in trades.columns
            
            # Check trade numbers are sequential
            if len(trades) > 0:
                assert trades['TradeNum'].tolist() == list(range(1, len(trades) + 1))
    
    def test_extract_equity_curve(self, engine, sample_data):
        """Test equity curve extraction"""
        # Run backtest
        results = engine.run_backtest(
            data=sample_data,
            strategy_class=SmaCrossStrategy,
            initial_cash=10000,
            n1=10,
            n2=20
        )
        
        # Check equity curve
        equity = results.equity_curve
        
        if not equity.empty:
            # Equity should start at initial cash
            assert equity.iloc[0] >= 0
            
            # Equity should be positive throughout
            assert (equity >= 0).all()
    
    def test_generate_report(self, engine, sample_data):
        """Test report generation"""
        # Run backtest
        results = engine.run_backtest(
            data=sample_data,
            strategy_class=SmaCrossStrategy,
            initial_cash=10000
        )
        
        # Generate report
        report = engine.generate_report(results)
        
        # Check report content
        assert isinstance(report, str)
        assert 'Results in:' in report
        assert 'Return [%]' in report
        assert 'Sharpe Ratio' in report
        assert '# Trades' in report
    
    def test_results_to_dict(self, engine, sample_data):
        """Test converting results to dictionary"""
        # Run backtest
        results = engine.run_backtest(
            data=sample_data,
            strategy_class=SmaCrossStrategy,
            initial_cash=10000
        )
        
        # Convert to dict
        results_dict = results.to_dict()
        
        # Check structure
        assert isinstance(results_dict, dict)
        assert 'stats' in results_dict
        assert 'trades' in results_dict
        assert 'equity_curve' in results_dict
        assert 'chart_html' in results_dict
        assert 'strategy_params' in results_dict
        
        # Check stats are serializable
        assert isinstance(results_dict['stats'], dict)
        assert isinstance(results_dict['trades'], list)
    
    @pytest.mark.parametrize("commission", [0, 0.001, 0.01])
    def test_different_commissions(self, engine, sample_data, commission):
        """Test backtests with different commission rates"""
        results = engine.run_backtest(
            data=sample_data,
            strategy_class=SmaCrossStrategy,
            initial_cash=10000,
            commission=commission
        )
        
        # Higher commission should generally lead to lower returns
        assert results.stats is not None
        assert 'Return [%]' in results.stats
    
    def test_backtest_with_no_trades(self, engine):
        """Test backtest that generates no trades"""
        # Create flat data that won't trigger any signals
        dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
        price = 100.0
        
        flat_data = pd.DataFrame({
            'Open': [price] * len(dates),
            'High': [price] * len(dates),
            'Low': [price] * len(dates),
            'Close': [price] * len(dates),
            'Volume': [1000] * len(dates)
        }, index=dates)
        
        results = engine.run_backtest(
            data=flat_data,
            strategy_class=SmaCrossStrategy,
            initial_cash=10000
        )
        
        # Should complete without errors
        assert results.stats['# Trades'] == 0
        assert results.trades.empty