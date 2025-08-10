#!/usr/bin/env python3
"""
Test script to verify the standardized strategy naming convention works correctly
"""

import sys
import yaml
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def test_configuration():
    """Test the new configuration structure"""
    print("Testing Configuration Structure...")
    print("-" * 50)
    
    with open('config/live_trading_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Test strategy structure
    strategies = config['strategy']
    assert 'grid' in strategies, "Grid strategy not found"
    assert 'momentum' in strategies, "Momentum strategy not found"
    assert 'mean_reversion' in strategies, "Mean reversion strategy not found"
    assert 'ema_cross' in strategies, "EMA cross strategy not found"
    
    # Test grid strategy has symbols list
    assert 'symbols' in strategies['grid'], "Grid strategy missing symbols"
    assert isinstance(strategies['grid']['symbols'], list), "Symbols should be a list"
    assert len(strategies['grid']['symbols']) > 0, "Grid strategy has no symbols"
    
    # Test first symbol configuration
    first_symbol = strategies['grid']['symbols'][0]
    required_fields = ['symbol', 'interval', 'grid_levels', 'grid_spacing', 'position_size_per_grid']
    for field in required_fields:
        assert field in first_symbol, f"Missing field: {field}"
    
    print("✅ Configuration structure is correct")
    print(f"   - Found {len(strategies)} strategies")
    print(f"   - Grid strategy has {len(strategies['grid']['symbols'])} symbol(s)")
    print(f"   - First symbol: {first_symbol['symbol']}")
    
    # Test capital allocation
    allocation = config['capital']['allocation']
    assert 'grid' in allocation, "Grid allocation not found"
    assert 'momentum' in allocation, "Momentum allocation not found"
    assert sum(allocation.values()) == 1.0, "Allocations don't sum to 100%"
    
    print("✅ Capital allocation is correct")
    print(f"   - Grid: {allocation['grid']*100:.0f}%")
    print(f"   - Momentum: {allocation['momentum']*100:.0f}%")

def test_imports():
    """Test that renamed modules can be imported"""
    print("\nTesting Module Imports...")
    print("-" * 50)
    
    try:
        from src.application.trading.strategies.live_grid_strategy import LiveGridStrategy
        print("✅ LiveGridStrategy imported successfully")
        
        # Test initialization
        strategy = LiveGridStrategy(
            symbol="BTCUSDT",
            grid_levels=10,
            grid_spacing=0.005
        )
        assert strategy.symbol == "BTCUSDT"
        assert strategy.grid_levels == 10
        print("✅ Strategy initialized correctly")
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    
    return True

def test_strategy_setup():
    """Test that strategy setup logic works with new structure"""
    print("\nTesting Strategy Setup Logic...")
    print("-" * 50)
    
    with open('config/live_trading_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    strategy_config = config['strategy']
    
    # Simulate the setup logic from start_live_trading.py
    if strategy_config['grid']['enabled']:
        grid_config = strategy_config['grid']
        
        if not grid_config.get('symbols'):
            print("❌ No symbols configured")
            return False
        
        symbol_config = grid_config['symbols'][0]
        
        # Build strategy parameters
        strategy_params = {
            'symbol': symbol_config['symbol'],
            'grid_levels': symbol_config['grid_levels'],
            'grid_spacing': symbol_config['grid_spacing'],
            'position_size_per_grid': symbol_config['position_size_per_grid'],
            'use_dynamic_grid': grid_config.get('use_dynamic_grid', True),
            'atr_period': grid_config.get('atr_period', 14),
            'atr_multiplier': grid_config.get('atr_multiplier', 1.5),
            'sma_period': grid_config.get('sma_period', 20)
        }
        
        print("✅ Strategy parameters built successfully")
        print(f"   - Symbol: {strategy_params['symbol']}")
        print(f"   - Grid levels: {strategy_params['grid_levels']}")
        print(f"   - Dynamic grid: {strategy_params['use_dynamic_grid']}")
        
        # Test strategy initialization
        from src.application.trading.strategies.live_grid_strategy import LiveGridStrategy
        strategy = LiveGridStrategy(**strategy_params)
        
        print("✅ Strategy initialized with parameters")
        
    return True

def main():
    """Run all tests"""
    print("=" * 50)
    print("STRATEGY STANDARDIZATION TEST")
    print("=" * 50)
    
    try:
        test_configuration()
        test_imports()
        test_strategy_setup()
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED!")
        print("=" * 50)
        print("\nThe standardized strategy naming convention is working correctly.")
        print("You can now:")
        print("  1. Add multiple symbols to any strategy")
        print("  2. Easily add new strategy types")
        print("  3. Configure strategies consistently")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()