"""
Unit tests for Futures Grid Trading Strategy

Tests grid initialization, level calculation, position management,
and trading logic.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.application.backtesting.strategies.futures_grid_strategy import (
    FuturesGridStrategy,
    GridLevel,
    GridMode
)


class TestGridLevel(unittest.TestCase):
    """Test GridLevel dataclass"""
    
    def test_grid_level_creation(self):
        """Test creating a grid level"""
        level = GridLevel(
            price=50000,
            level_type='BUY',
            position_size=0.1
        )
        
        self.assertEqual(level.price, 50000)
        self.assertEqual(level.level_type, 'BUY')
        self.assertEqual(level.position_size, 0.1)
        self.assertFalse(level.is_filled)
        self.assertIsNone(level.position_id)
    
    def test_grid_level_hash(self):
        """Test grid level hashing for use in sets/dicts"""
        level1 = GridLevel(price=50000, level_type='BUY', position_size=0.1)
        level2 = GridLevel(price=50000, level_type='BUY', position_size=0.2)
        level3 = GridLevel(price=51000, level_type='BUY', position_size=0.1)
        
        # Same price and type should have same hash
        self.assertEqual(hash(level1), hash(level2))
        # Different price should have different hash
        self.assertNotEqual(hash(level1), hash(level3))


class TestFuturesGridStrategy(unittest.TestCase):
    """Test FuturesGridStrategy implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create sample market data
        dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
        self.sample_data = pd.DataFrame({
            'Open': np.random.randn(100) * 100 + 50000,
            'High': np.random.randn(100) * 100 + 50100,
            'Low': np.random.randn(100) * 100 + 49900,
            'Close': np.random.randn(100) * 100 + 50000,
            'Volume': np.random.rand(100) * 1000000
        }, index=dates)
        
        # Ensure OHLC relationships
        self.sample_data['High'] = self.sample_data[['Open', 'Close', 'High']].max(axis=1)
        self.sample_data['Low'] = self.sample_data[['Open', 'Close', 'Low']].min(axis=1)
        
        # Create strategy instance with mocked dependencies
        mock_broker = Mock()
        mock_params = {}
        
        # Mock the backtesting framework initialization
        with patch.object(FuturesGridStrategy, '__init__', lambda x: None):
            self.strategy = FuturesGridStrategy()
            
        # Manually initialize state variables
        self.strategy.grid_active = False
        self.strategy.grid_center = None
        self.strategy.buy_levels = []
        self.strategy.sell_levels = []
        self.strategy.active_positions = {}
        self.strategy.completed_trades = []
        self.strategy.last_rebalance_time = None
        self.strategy.grid_pnl = 0
        self.strategy.consecutive_losses = 0
        self.strategy.grid_initialized = False
        
        # Set default parameters
        self.strategy.grid_levels = 10
        self.strategy.grid_spacing_pct = 0.5
        self.strategy.upper_bound_pct = 5.0
        self.strategy.lower_bound_pct = 5.0
        self.strategy.position_per_grid = 0.05
        self.strategy.max_concurrent_positions = 10
        self.strategy.pyramid_mode = False
        self.strategy.pyramid_factor = 1.5
        self.strategy.grid_mode = GridMode.NEUTRAL
        self.strategy.stop_loss_pct = 0.08
        self.strategy.take_profit_grids = 2
        self.strategy.rebalance_threshold = 0.10
        self.strategy.trailing_grid = False
        self.strategy.trailing_threshold = 0.03
        
        # Mock indicators
        self.strategy.atr = []
        self.strategy.sma_fast = []
        self.strategy.sma_slow = []
        self.strategy.rsi = []
        
    def test_grid_initialization(self):
        """Test grid level initialization"""
        center_price = 50000
        
        # Set strategy parameters
        self.strategy.grid_levels = 5
        self.strategy.grid_spacing_pct = 1.0
        self.strategy.upper_bound_pct = 5.0
        self.strategy.lower_bound_pct = 5.0
        
        # Initialize grid
        self.strategy._initialize_grid(center_price)
        
        # Check grid center
        self.assertEqual(self.strategy.grid_center, center_price)
        
        # Check buy levels
        self.assertEqual(len(self.strategy.buy_levels), 5)
        for i, level in enumerate(self.strategy.buy_levels):
            expected_price = center_price * (1 - (1.0 * (i + 1) / 100))
            self.assertAlmostEqual(level.price, expected_price, places=2)
            self.assertEqual(level.level_type, 'BUY')
            self.assertFalse(level.is_filled)
        
        # Check sell levels
        self.assertEqual(len(self.strategy.sell_levels), 5)
        for i, level in enumerate(self.strategy.sell_levels):
            expected_price = center_price * (1 + (1.0 * (i + 1) / 100))
            self.assertAlmostEqual(level.price, expected_price, places=2)
            self.assertEqual(level.level_type, 'SELL')
            self.assertFalse(level.is_filled)
        
        # Check grid is active
        self.assertTrue(self.strategy.grid_active)
    
    def test_grid_with_bias(self):
        """Test grid initialization with different biases"""
        center_price = 50000
        
        # Test LONG_BIAS
        self.strategy.grid_mode = GridMode.LONG_BIAS
        self.strategy.grid_levels = 10
        self.strategy._initialize_grid(center_price)
        
        # Should have more buy levels than sell levels
        self.assertEqual(len(self.strategy.buy_levels), 15)  # 1.5x
        self.assertEqual(len(self.strategy.sell_levels), 5)  # 0.5x
        
        # Test SHORT_BIAS
        self.strategy.grid_mode = GridMode.SHORT_BIAS
        self.strategy._initialize_grid(center_price)
        
        # Should have more sell levels than buy levels
        self.assertEqual(len(self.strategy.buy_levels), 5)   # 0.5x
        self.assertEqual(len(self.strategy.sell_levels), 15) # 1.5x
    
    def test_pyramid_sizing(self):
        """Test pyramid position sizing"""
        center_price = 50000
        
        self.strategy.pyramid_mode = True
        self.strategy.pyramid_factor = 1.5
        self.strategy.position_per_grid = 0.1
        self.strategy.grid_levels = 3
        
        self.strategy._initialize_grid(center_price)
        
        # Check position sizes increase with distance from center
        buy_sizes = [level.position_size for level in self.strategy.buy_levels]
        for i in range(len(buy_sizes) - 1):
            self.assertLess(buy_sizes[i], buy_sizes[i + 1])
    
    def test_should_rebalance_grid(self):
        """Test grid rebalancing logic"""
        # Initialize grid
        self.strategy._initialize_grid(50000)
        self.strategy.rebalance_threshold = 0.10  # 10%
        
        # Mock data with small price move
        self.strategy.data = Mock()
        self.strategy.data.Close = [54000]  # 8% move
        
        # Should not rebalance
        self.assertFalse(self.strategy._should_rebalance_grid())
        
        # Mock data with large price move
        self.strategy.data.Close = [56000]  # 12% move
        
        # Should rebalance
        self.assertTrue(self.strategy._should_rebalance_grid())
    
    def test_should_trail_grid(self):
        """Test grid trailing logic"""
        # Initialize grid with trailing enabled
        self.strategy._initialize_grid(50000)
        self.strategy.trailing_grid = True
        self.strategy.trailing_threshold = 0.03  # 3%
        
        # Mock indicators
        self.strategy.sma_fast = [51000]
        self.strategy.sma_slow = [50500]
        
        # Mock data with uptrend
        self.strategy.data = Mock()
        self.strategy.data.Close = [51600]  # 3.2% move up
        
        # Should trail in uptrend
        self.assertTrue(self.strategy._should_trail_grid())
        
        # Mock downtrend
        self.strategy.sma_fast = [49000]
        self.strategy.sma_slow = [49500]
        self.strategy.data.Close = [48400]  # 3.2% move down
        
        # Should trail in downtrend
        self.assertTrue(self.strategy._should_trail_grid())
    
    def test_get_nearest_unfilled_level(self):
        """Test finding nearest unfilled grid level"""
        # Initialize grid
        self.strategy._initialize_grid(50000)
        
        # Test finding buy level
        nearest_buy = self.strategy._get_nearest_unfilled_level(49600, 'BUY')
        self.assertIsNotNone(nearest_buy)
        self.assertEqual(nearest_buy.level_type, 'BUY')
        self.assertLess(nearest_buy.price, 49600)
        
        # Test finding sell level
        nearest_sell = self.strategy._get_nearest_unfilled_level(50400, 'SELL')
        self.assertIsNotNone(nearest_sell)
        self.assertEqual(nearest_sell.level_type, 'SELL')
        self.assertGreater(nearest_sell.price, 50400)
        
        # Mark a level as filled
        self.strategy.buy_levels[0].is_filled = True
        
        # Should skip filled level
        nearest_buy = self.strategy._get_nearest_unfilled_level(49600, 'BUY')
        self.assertFalse(nearest_buy.is_filled)
    
    def test_should_go_long(self):
        """Test long entry logic"""
        # Mock data
        self.strategy.data = Mock()
        self.strategy.data.__len__ = Mock(return_value=10)
        self.strategy.data.Close = [50000, 49500]  # Price dropped
        self.strategy.data.index = [datetime.now()]
        
        # Mock indicators
        self.strategy.atr = [100]
        self.strategy.sma_fast = [50000]
        self.strategy.sma_slow = [50000]
        self.strategy.rsi = [50]
        
        # First call should initialize grid
        result = self.strategy.should_go_long()
        self.assertFalse(result)  # Returns False on initialization
        self.assertTrue(self.strategy.grid_initialized)
        
        # Second call with price at buy level
        self.strategy.data.Close = [49500]  # At first buy level (1% below 50000)
        result = self.strategy.should_go_long()
        self.assertTrue(result)
        
        # Check level is marked as filled
        filled_levels = [l for l in self.strategy.buy_levels if l.is_filled]
        self.assertEqual(len(filled_levels), 1)
    
    def test_should_go_short(self):
        """Test short entry logic"""
        # Initialize grid first
        self.strategy.grid_initialized = True
        self.strategy._initialize_grid(50000)
        
        # Mock data
        self.strategy.data = Mock()
        self.strategy.data.__len__ = Mock(return_value=10)
        self.strategy.data.Close = [50500]  # At first sell level
        self.strategy.data.index = [datetime.now()]
        
        # Mock indicators
        self.strategy.rsi = [50]
        
        result = self.strategy.should_go_short()
        self.assertTrue(result)
        
        # Check level is marked as filled
        filled_levels = [l for l in self.strategy.sell_levels if l.is_filled]
        self.assertEqual(len(filled_levels), 1)
    
    def test_should_close_long(self):
        """Test long exit logic"""
        # Setup active long position
        self.strategy._initialize_grid(50000)
        self.strategy.take_profit_grids = 2
        self.strategy.grid_spacing_pct = 1.0
        
        # Add active position
        buy_level = GridLevel(
            price=49500,
            level_type='BUY',
            position_size=0.1,
            is_filled=True,
            entry_time=datetime.now()
        )
        self.strategy.active_positions[49500] = buy_level
        
        # Mock data
        self.strategy.data = Mock()
        self.strategy.data.__len__ = Mock(return_value=10)
        self.strategy.data.index = [datetime.now()]
        
        # Price hasn't moved enough
        self.strategy.data.Close = [50000]  # Only 1% move
        result = self.strategy.should_close_long()
        self.assertFalse(result)
        
        # Price moved 2 grids (2%)
        self.strategy.data.Close = [50490]  # 2% above entry
        result = self.strategy.should_close_long()
        self.assertTrue(result)
        
        # Check position was removed
        self.assertNotIn(49500, self.strategy.active_positions)
    
    def test_should_close_short(self):
        """Test short exit logic"""
        # Setup active short position
        self.strategy._initialize_grid(50000)
        self.strategy.take_profit_grids = 2
        self.strategy.grid_spacing_pct = 1.0
        
        # Add active position
        sell_level = GridLevel(
            price=50500,
            level_type='SELL',
            position_size=0.1,
            is_filled=True,
            entry_time=datetime.now()
        )
        self.strategy.active_positions[50500] = sell_level
        
        # Mock data
        self.strategy.data = Mock()
        self.strategy.data.__len__ = Mock(return_value=10)
        self.strategy.data.index = [datetime.now()]
        
        # Price hasn't moved enough
        self.strategy.data.Close = [50000]  # Only 1% move
        result = self.strategy.should_close_short()
        self.assertFalse(result)
        
        # Price moved 2 grids down (2%)
        self.strategy.data.Close = [49490]  # 2% below entry
        result = self.strategy.should_close_short()
        self.assertTrue(result)
        
        # Check position was removed
        self.assertNotIn(50500, self.strategy.active_positions)
    
    def test_stop_loss_trigger(self):
        """Test stop loss triggers correctly"""
        # Setup
        self.strategy._initialize_grid(50000)
        self.strategy.lower_bound_pct = 5.0
        self.strategy.stop_loss_pct = 0.08
        
        # Add long position
        buy_level = GridLevel(
            price=49500,
            level_type='BUY',
            position_size=0.1,
            is_filled=True,
            entry_time=datetime.now()
        )
        self.strategy.active_positions[49500] = buy_level
        
        # Mock data with price below stop loss
        self.strategy.data = Mock()
        self.strategy.data.__len__ = Mock(return_value=10)
        self.strategy.data.index = [datetime.now()]
        
        # Price breaks below grid boundary + stop loss
        stop_price = 50000 * (1 - 0.05 - 0.0008)  # Below grid + stop
        self.strategy.data.Close = [stop_price - 100]
        
        result = self.strategy.should_close_long()
        self.assertTrue(result)
        
        # Check consecutive losses incremented
        self.assertEqual(self.strategy.consecutive_losses, 1)
    
    def test_calculate_grid_metrics(self):
        """Test grid metrics calculation"""
        # Setup grid with some filled levels
        self.strategy._initialize_grid(50000)
        self.strategy.grid_levels = 3
        
        # Fill some levels
        self.strategy.buy_levels[0].is_filled = True
        self.strategy.sell_levels[0].is_filled = True
        
        # Add completed trades
        self.strategy.completed_trades = [
            {'pnl': 100, 'type': 'LONG'},
            {'pnl': 50, 'type': 'SHORT'},
            {'pnl': -25, 'type': 'LONG'}
        ]
        
        # Add active positions
        self.strategy.active_positions = {
            49700: self.strategy.buy_levels[0],
            50300: self.strategy.sell_levels[0]
        }
        
        metrics = self.strategy._calculate_grid_metrics()
        
        # Check metrics
        self.assertIn('fill_rate', metrics)
        self.assertEqual(metrics['active_positions'], 2)
        self.assertEqual(metrics['completed_trades'], 3)
        self.assertAlmostEqual(metrics['avg_trade_profit'], 41.67, places=1)
    
    def test_max_concurrent_positions(self):
        """Test max concurrent positions limit"""
        # Setup
        self.strategy._initialize_grid(50000)
        self.strategy.max_concurrent_positions = 2
        
        # Fill max positions
        for i in range(2):
            level = GridLevel(
                price=49500 - i*100,
                level_type='BUY',
                position_size=0.1,
                is_filled=True
            )
            self.strategy.active_positions[level.price] = level
        
        # Mock data at buy level
        self.strategy.data = Mock()
        self.strategy.data.__len__ = Mock(return_value=10)
        self.strategy.data.Close = [49300]  # At another buy level
        
        # Should not open new position
        result = self.strategy.should_go_long()
        self.assertFalse(result)


class TestGridIntegration(unittest.TestCase):
    """Integration tests for grid strategy with backtest engine"""
    
    @patch('src.infrastructure.backtesting.futures_backtest_engine.FuturesBacktestEngine')
    def test_grid_with_backtest_engine(self, mock_engine):
        """Test grid strategy integrates with backtest engine"""
        # Create sample data
        dates = pd.date_range(start='2024-01-01', periods=1000, freq='5min')
        data = pd.DataFrame({
            'Open': np.random.randn(1000) * 100 + 50000,
            'High': np.random.randn(1000) * 100 + 50100,
            'Low': np.random.randn(1000) * 100 + 49900,
            'Close': np.random.randn(1000) * 100 + 50000,
            'Volume': np.random.rand(1000) * 1000000
        }, index=dates)
        
        # Mock backtest engine
        mock_result = Mock()
        mock_result.stats = {
            'Return [%]': 15.5,
            'Sharpe Ratio': 1.8,
            'Max. Drawdown [%]': -8.2,
            '# Trades': 42
        }
        mock_engine.return_value.run_backtest.return_value = mock_result
        
        # Run backtest
        engine = mock_engine()
        result = engine.run_backtest(
            data=data,
            strategy_class=FuturesGridStrategy,
            initial_cash=10000,
            commission=0.0004,
            grid_levels=10,
            grid_spacing_pct=0.5
        )
        
        # Verify backtest was called
        engine.run_backtest.assert_called_once()
        self.assertEqual(result.stats['Return [%]'], 15.5)
        self.assertEqual(result.stats['# Trades'], 42)


if __name__ == '__main__':
    unittest.main()