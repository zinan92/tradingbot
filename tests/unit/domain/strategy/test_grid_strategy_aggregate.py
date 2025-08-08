"""
Unit tests for Grid Strategy Aggregate

Tests domain logic for grid strategy including level calculation,
position management, and risk controls.
"""

import unittest
from datetime import datetime
from unittest.mock import Mock, patch
import numpy as np

from src.domain.strategy.aggregates.grid_strategy_aggregate import (
    GridStrategyAggregate,
    GridConfiguration,
    GridLevel,
    GridState
)
from src.domain.strategy.regime.regime_models import MarketRegime, GridMode
from src.domain.trading.value_objects.symbol import Symbol


class TestGridLevel(unittest.TestCase):
    """Test GridLevel value object."""
    
    def test_valid_grid_level(self):
        """Test creating valid grid level."""
        level = GridLevel(
            price=50000.0,
            side='BUY',
            level_index=1,
            is_active=True
        )
        
        self.assertEqual(level.price, 50000.0)
        self.assertEqual(level.side, 'BUY')
        self.assertEqual(level.level_index, 1)
        self.assertTrue(level.is_active)
    
    def test_invalid_side(self):
        """Test grid level with invalid side."""
        with self.assertRaises(ValueError):
            GridLevel(
                price=50000.0,
                side='INVALID',
                level_index=1
            )
    
    def test_invalid_price(self):
        """Test grid level with invalid price."""
        with self.assertRaises(ValueError):
            GridLevel(
                price=-100,
                side='BUY',
                level_index=1
            )


class TestGridConfiguration(unittest.TestCase):
    """Test GridConfiguration value object."""
    
    def test_valid_configuration(self):
        """Test creating valid configuration."""
        config = GridConfiguration(
            atr_multiplier=0.75,
            grid_levels=5,
            max_position_size=0.1
        )
        
        self.assertEqual(config.atr_multiplier, 0.75)
        self.assertEqual(config.grid_levels, 5)
        self.assertEqual(config.max_position_size, 0.1)
    
    def test_invalid_atr_multiplier(self):
        """Test configuration with invalid ATR multiplier."""
        with self.assertRaises(ValueError):
            GridConfiguration(atr_multiplier=-0.5)
    
    def test_invalid_position_size(self):
        """Test configuration with invalid position size."""
        with self.assertRaises(ValueError):
            GridConfiguration(max_position_size=1.5)


class TestGridStrategyAggregate(unittest.TestCase):
    """Test GridStrategyAggregate domain logic."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = GridConfiguration(
            atr_multiplier=0.75,
            grid_levels=5,
            max_position_size=0.1
        )
        
        self.strategy = GridStrategyAggregate(
            strategy_id="test_strategy",
            symbol=Symbol("BTCUSDT"),
            config=self.config,
            initial_regime=MarketRegime.RANGE
        )
    
    def test_initialization(self):
        """Test strategy initialization."""
        self.assertEqual(self.strategy.id, "test_strategy")
        self.assertEqual(self.strategy.symbol.value, "BTCUSDT")
        self.assertEqual(self.strategy.market_regime, MarketRegime.RANGE)
        self.assertEqual(self.strategy.grid_mode, GridMode.BIDIRECTIONAL)
        self.assertEqual(self.strategy.state, GridState.INACTIVE)
    
    def test_regime_update(self):
        """Test updating market regime."""
        self.strategy.update_market_regime(MarketRegime.BULLISH)
        
        self.assertEqual(self.strategy.market_regime, MarketRegime.BULLISH)
        self.assertEqual(self.strategy.grid_mode, GridMode.LONG_ONLY)
        
        # Check event was created
        events = self.strategy.clear_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'RegimeChanged')
    
    def test_calculate_grid_levels(self):
        """Test grid level calculation."""
        reference_price = 50000.0
        atr_value = 1000.0
        
        buy_levels, sell_levels = self.strategy.calculate_grid_levels(
            reference_price, atr_value
        )
        
        # Check bidirectional mode creates both levels
        self.assertEqual(len(buy_levels), 5)
        self.assertEqual(len(sell_levels), 5)
        
        # Check spacing
        expected_spacing = atr_value * 0.75
        first_buy = reference_price - expected_spacing
        self.assertAlmostEqual(buy_levels[0].price, first_buy, places=2)
        
        first_sell = reference_price + expected_spacing
        self.assertAlmostEqual(sell_levels[0].price, first_sell, places=2)
    
    def test_long_only_grid(self):
        """Test grid calculation in LONG_ONLY mode."""
        self.strategy.update_market_regime(MarketRegime.BULLISH)
        
        buy_levels, sell_levels = self.strategy.calculate_grid_levels(50000, 1000)
        
        self.assertEqual(len(buy_levels), 5)
        self.assertEqual(len(sell_levels), 0)  # No sell levels in LONG_ONLY
    
    def test_short_only_grid(self):
        """Test grid calculation in SHORT_ONLY mode."""
        self.strategy.update_market_regime(MarketRegime.BEARISH)
        
        buy_levels, sell_levels = self.strategy.calculate_grid_levels(50000, 1000)
        
        self.assertEqual(len(buy_levels), 0)  # No buy levels in SHORT_ONLY
        self.assertEqual(len(sell_levels), 5)
    
    def test_should_recalculate_grid(self):
        """Test grid recalculation logic."""
        # Initially should recalculate (no reference)
        self.assertTrue(self.strategy.should_recalculate_grid(50000, 1000))
        
        # Set reference values
        self.strategy.reference_price = 50000
        self.strategy.last_atr = 1000
        
        # Small price change - no recalculation
        self.assertFalse(self.strategy.should_recalculate_grid(50200, 1000))
        
        # Large price change - should recalculate
        self.assertTrue(self.strategy.should_recalculate_grid(50600, 1000))
    
    def test_update_grid(self):
        """Test grid update process."""
        self.strategy.update_grid(50000, 1000)
        
        self.assertEqual(self.strategy.state, GridState.ACTIVE)
        self.assertEqual(self.strategy.reference_price, 50000)
        self.assertEqual(self.strategy.last_atr, 1000)
        self.assertEqual(len(self.strategy.buy_levels), 5)
        self.assertEqual(len(self.strategy.sell_levels), 5)
        
        # Check event was created
        events = self.strategy.clear_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'GridUpdated')
    
    def test_check_buy_signal(self):
        """Test buy signal detection."""
        # Setup grid
        self.strategy.update_grid(50000, 1000)
        
        # Price above all buy levels - no signal
        signal = self.strategy.check_buy_signal(51000)
        self.assertIsNone(signal)
        
        # Price at buy level - should signal
        first_buy_price = self.strategy.buy_levels[0].price
        signal = self.strategy.check_buy_signal(first_buy_price - 10)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.side, 'BUY')
    
    def test_check_sell_signal(self):
        """Test sell signal detection."""
        # Setup grid
        self.strategy.update_grid(50000, 1000)
        
        # Price below all sell levels - no signal
        signal = self.strategy.check_sell_signal(49000)
        self.assertIsNone(signal)
        
        # Price at sell level - should signal
        first_sell_price = self.strategy.sell_levels[0].price
        signal = self.strategy.check_sell_signal(first_sell_price + 10)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.side, 'SELL')
    
    def test_position_size_calculation(self):
        """Test position size calculation."""
        # Initial size
        size = self.strategy.calculate_position_size()
        expected = 0.1 / 5  # max_position_size / grid_levels
        self.assertEqual(size, expected)
        
        # With positions open
        self.strategy.position_count = 2
        self.strategy.total_position_size = 0.04
        
        size = self.strategy.calculate_position_size()
        self.assertLess(size, expected)  # Reduced due to open positions
    
    def test_volatility_filtering(self):
        """Test grid activation based on volatility."""
        # Create ATR history
        atr_history = [1000] * 20
        
        # Normal volatility - should activate
        self.assertTrue(self.strategy.should_activate_grid(1000, atr_history))
        
        # Extreme high volatility - should not activate
        self.assertFalse(self.strategy.should_activate_grid(2000, atr_history))
        
        # Extreme low volatility - should not activate
        self.assertFalse(self.strategy.should_activate_grid(200, atr_history))
    
    def test_stop_loss_check(self):
        """Test stop loss detection."""
        self.strategy.last_atr = 1000
        
        # Long position
        entry_price = 50000
        
        # Price above entry - no stop loss
        self.assertFalse(self.strategy.check_stop_loss(51000, entry_price, 'LONG'))
        
        # Price at stop loss level
        stop_price = entry_price - (1000 * 2)  # 2x ATR stop
        self.assertTrue(self.strategy.check_stop_loss(stop_price - 10, entry_price, 'LONG'))
        
        # Short position
        self.assertFalse(self.strategy.check_stop_loss(49000, entry_price, 'SHORT'))
        stop_price = entry_price + (1000 * 2)
        self.assertTrue(self.strategy.check_stop_loss(stop_price + 10, entry_price, 'SHORT'))
    
    def test_position_tracking(self):
        """Test position open/close tracking."""
        level = GridLevel(price=49500, side='BUY', level_index=1)
        
        # Open position
        self.strategy.record_position_opened(
            position_id="pos_1",
            grid_level=level,
            size=0.02
        )
        
        self.assertEqual(self.strategy.position_count, 1)
        self.assertEqual(self.strategy.total_position_size, 0.02)
        self.assertIn("pos_1", self.strategy.active_positions)
        
        # Check level deactivated
        self.assertFalse(self.strategy.buy_levels[0].is_active)
        
        # Close position
        self.strategy.record_position_closed(
            position_id="pos_1",
            exit_price=50000,
            pnl=100
        )
        
        self.assertEqual(self.strategy.position_count, 0)
        self.assertEqual(self.strategy.total_position_size, 0)
        self.assertEqual(self.strategy.total_pnl, 100)
        self.assertNotIn("pos_1", self.strategy.active_positions)
        
        # Check level reactivated
        self.assertTrue(self.strategy.buy_levels[0].is_active)
    
    def test_risk_metrics(self):
        """Test risk metrics calculation."""
        # Add some positions and losses
        self.strategy.position_count = 3
        self.strategy.total_position_size = 0.06
        self.strategy.consecutive_losses = 2
        self.strategy.total_pnl = -500
        
        metrics = self.strategy.get_risk_metrics()
        
        self.assertEqual(metrics['active_positions'], 3)
        self.assertEqual(metrics['total_position_size'], 0.06)
        self.assertEqual(metrics['consecutive_losses'], 2)
        self.assertEqual(metrics['total_pnl'], -500)


class TestGridIntegration(unittest.TestCase):
    """Integration tests for grid strategy."""
    
    def test_full_grid_cycle(self):
        """Test complete grid trading cycle."""
        config = GridConfiguration(
            atr_multiplier=0.5,
            grid_levels=3,
            max_position_size=0.15
        )
        
        strategy = GridStrategyAggregate(
            strategy_id="test",
            symbol=Symbol("BTCUSDT"),
            config=config,
            initial_regime=MarketRegime.RANGE
        )
        
        # Initialize grid
        strategy.update_grid(50000, 1000)
        
        # Simulate price hitting buy level
        buy_signal = strategy.check_buy_signal(49000)
        self.assertIsNotNone(buy_signal)
        
        # Open position
        strategy.record_position_opened("pos_1", buy_signal, 0.05)
        
        # Check position tracking
        self.assertEqual(strategy.position_count, 1)
        
        # Simulate profitable exit
        strategy.record_position_closed("pos_1", 50000, 50)
        
        # Check final state
        self.assertEqual(strategy.position_count, 0)
        self.assertEqual(strategy.total_pnl, 50)
        
        # Level should be reactivated
        self.assertTrue(strategy.buy_levels[0].is_active)


if __name__ == '__main__':
    unittest.main()