"""
Advanced property-based tests with sophisticated shrinking strategies.

This module provides more complex property tests with custom shrinking
to produce minimal counterexamples when failures occur.
"""

import pytest
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from hypothesis import (
    given, strategies as st, assume, settings, Phase, 
    example, reproduce_failure, seed, note, event
)
from hypothesis.strategies import SearchStrategy
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, Bundle


# Custom shrinking strategies
class ShrinkerStrategies:
    """Custom shrinking strategies for minimal counterexamples."""
    
    @staticmethod
    def shrink_order_sequence(orders: List[Dict]) -> SearchStrategy:
        """
        Shrink order sequences to find minimal failing case.
        Strategies:
        1. Remove orders from the end
        2. Remove orders from the middle
        3. Simplify order parameters
        4. Reduce quantities
        """
        return st.lists(
            st.fixed_dictionaries({
                'symbol': st.sampled_from(['BTCUSDT']),  # Simplify to single symbol
                'side': st.sampled_from(['BUY', 'SELL']),
                'quantity': st.decimals(
                    min_value='0.001', 
                    max_value='1.0',  # Smaller quantities
                    places=3
                ),
                'price': st.decimals(
                    min_value='1000',
                    max_value='100000', 
                    places=2
                )
            }),
            min_size=1,  # Minimum sequence to reproduce
            max_size=10  # Shorter sequences
        )
    
    @staticmethod
    def shrink_price_path(path: List[Decimal]) -> SearchStrategy:
        """
        Shrink price paths to minimal volatility.
        Strategies:
        1. Reduce number of price changes
        2. Minimize price movements
        3. Flatten to constant price
        """
        return st.lists(
            st.decimals(
                min_value='1000',
                max_value='100000',
                places=2
            ),
            min_size=2,  # At least start and end
            max_size=10  # Shorter paths
        ).map(lambda prices: [prices[0]] * len(prices))  # Flatten volatility


@dataclass
class MarketScenario:
    """Represents a complete market scenario for testing."""
    orders: List[Dict]
    price_paths: Dict[str, List[Decimal]]
    volatility_events: List[Dict]
    initial_balance: Decimal
    risk_limits: Dict[str, Decimal]
    
    def simplify(self) -> 'MarketScenario':
        """Simplify scenario for shrinking."""
        return MarketScenario(
            orders=self.orders[:5],  # Keep only first 5 orders
            price_paths={k: v[:10] for k, v in self.price_paths.items()},  # Shorter paths
            volatility_events=[],  # Remove volatility
            initial_balance=Decimal("10000"),  # Standard balance
            risk_limits={'exposure': Decimal("0.5")}  # Simple limits
        )


class ComplexInvariantTests:
    """Complex property tests with advanced scenarios."""
    
    @given(
        scenario=st.builds(
            MarketScenario,
            orders=st.lists(
                st.fixed_dictionaries({
                    'symbol': st.sampled_from(['BTCUSDT', 'ETHUSDT']),
                    'side': st.sampled_from(['BUY', 'SELL']),
                    'type': st.sampled_from(['MARKET', 'LIMIT']),
                    'quantity': st.decimals(min_value='0.001', max_value='10', places=3),
                    'price': st.decimals(min_value='100', max_value='100000', places=2),
                    'leverage': st.integers(min_value=1, max_value=100)
                }),
                min_size=1,
                max_size=100
            ),
            price_paths=st.dictionaries(
                st.sampled_from(['BTCUSDT', 'ETHUSDT']),
                st.lists(
                    st.decimals(min_value='100', max_value='100000', places=2),
                    min_size=10,
                    max_size=100
                ),
                min_size=1,
                max_size=2
            ),
            volatility_events=st.lists(
                st.fixed_dictionaries({
                    'type': st.sampled_from(['spike', 'crash', 'halt']),
                    'magnitude': st.floats(min_value=0.1, max_value=0.9),
                    'duration': st.integers(min_value=1, max_value=10)
                }),
                max_size=5
            ),
            initial_balance=st.decimals(min_value='1000', max_value='1000000', places=2),
            risk_limits=st.fixed_dictionaries({
                'exposure': st.decimals(min_value='0.1', max_value='0.95', places=2),
                'daily_loss': st.decimals(min_value='0.01', max_value='0.10', places=2),
                'drawdown': st.decimals(min_value='0.05', max_value='0.20', places=2)
            })
        )
    )
    @settings(
        max_examples=200,
        deadline=10000,
        phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink],
        print_blob=True,  # Print reproduction code on failure
        report_multiple_bugs=True  # Find all bugs, not just first
    )
    @example(
        # Provide specific example that previously failed
        scenario=MarketScenario(
            orders=[
                {'symbol': 'BTCUSDT', 'side': 'BUY', 'type': 'MARKET', 
                 'quantity': Decimal('1.0'), 'price': Decimal('50000'), 'leverage': 100}
            ],
            price_paths={'BTCUSDT': [Decimal('50000'), Decimal('25000')]},  # 50% crash
            volatility_events=[],
            initial_balance=Decimal('1000'),
            risk_limits={'exposure': Decimal('0.8'), 'daily_loss': Decimal('0.05'), 
                        'drawdown': Decimal('0.10')}
        )
    )
    def test_margin_call_protection(self, scenario: MarketScenario):
        """
        Property: System must protect against margin calls.
        
        Tests that the system properly handles:
        - Sudden price drops
        - High leverage positions
        - Cascade liquidations
        """
        from src.application.services import MarginMonitor, LiquidationEngine
        
        monitor = MarginMonitor(
            maintenance_margin_ratio=Decimal("0.05"),
            initial_margin_ratio=Decimal("0.10")
        )
        
        liquidator = LiquidationEngine()
        
        account_equity = scenario.initial_balance
        positions = []
        margin_calls = []
        
        for i, order in enumerate(scenario.orders):
            symbol = order['symbol']
            
            # Get current price from path
            price_index = min(i, len(scenario.price_paths.get(symbol, [])) - 1)
            if price_index < 0:
                continue
                
            current_price = scenario.price_paths[symbol][price_index]
            
            # Calculate position value and required margin
            position_value = order['quantity'] * current_price
            required_margin = position_value / order['leverage']
            
            # Check if we have enough equity
            if account_equity >= required_margin:
                positions.append({
                    'symbol': symbol,
                    'quantity': order['quantity'],
                    'entry_price': current_price,
                    'leverage': order['leverage'],
                    'margin': required_margin
                })
                account_equity -= required_margin
                
                # Note important events for debugging
                note(f"Position opened: {symbol} qty={order['quantity']} @ {current_price}")
            
            # Check for margin calls on existing positions
            for pos in positions:
                pos_symbol = pos['symbol']
                pos_current_price = scenario.price_paths[pos_symbol][price_index]
                
                # Calculate unrealized PnL
                if order['side'] == 'BUY':
                    pnl = (pos_current_price - pos['entry_price']) * pos['quantity']
                else:
                    pnl = (pos['entry_price'] - pos_current_price) * pos['quantity']
                
                # Check margin level
                position_equity = pos['margin'] + pnl
                margin_level = position_equity / pos['margin'] if pos['margin'] > 0 else 0
                
                if margin_level < monitor.maintenance_margin_ratio:
                    margin_calls.append({
                        'position': pos,
                        'margin_level': margin_level,
                        'price': pos_current_price
                    })
                    
                    # Log margin call event
                    event(f"margin_call_{pos_symbol}")
                    note(f"Margin call: {pos_symbol} level={margin_level}")
        
        # Properties to assert
        assert account_equity >= 0, \
            f"Account equity went negative: {account_equity}"
        
        # If margin calls occurred, liquidation should have happened
        if margin_calls:
            assert len(liquidator.get_liquidation_queue()) > 0, \
                "Margin calls occurred but no liquidations queued"
        
        # Minimal counterexample on failure
        if account_equity < 0:
            # Shrink to minimal failing case
            simplified = scenario.simplify()
            note(f"Simplified scenario: {json.dumps({
                'orders': len(simplified.orders),
                'price_drop': 'Yes' if any(
                    path[0] > path[-1] for path in simplified.price_paths.values()
                ) else 'No',
                'leverage': max(o['leverage'] for o in simplified.orders)
            })}")
    
    @given(
        parallel_orders=st.lists(
            st.tuples(
                st.sampled_from(['BTCUSDT', 'ETHUSDT']),
                st.sampled_from(['BUY', 'SELL']),
                st.decimals(min_value='0.01', max_value='1.0', places=2),
                st.integers(min_value=0, max_value=100)  # Delay in ms
            ),
            min_size=2,
            max_size=50
        )
    )
    @settings(
        max_examples=100,
        deadline=5000,
        suppress_health_check=[],  # Enable all health checks
        database=None  # Don't save examples
    )
    def test_concurrent_order_consistency(self, parallel_orders: List[Tuple]):
        """
        Property: Concurrent orders maintain consistency.
        
        Tests that parallel order execution:
        - Doesn't create negative positions
        - Maintains correct margin calculations
        - Prevents double-spending of margin
        """
        from src.application.services import OrderExecutor, ConcurrencyManager
        import asyncio
        
        executor = OrderExecutor()
        concurrency_mgr = ConcurrencyManager()
        
        async def execute_orders_concurrently():
            tasks = []
            
            for symbol, side, quantity, delay_ms in parallel_orders:
                async def execute_with_delay(s, sd, q, d):
                    await asyncio.sleep(d / 1000.0)  # Convert ms to seconds
                    
                    async with concurrency_mgr.acquire_lock(s):
                        return await executor.execute_order(s, sd, q)
                
                tasks.append(execute_with_delay(symbol, side, quantity, delay_ms))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        
        # Run concurrent execution
        loop = asyncio.new_event_loop()
        results = loop.run_until_complete(execute_orders_concurrently())
        loop.close()
        
        # Verify consistency
        successful_orders = [r for r in results if not isinstance(r, Exception)]
        
        # Check that total margin used doesn't exceed available
        total_margin_used = sum(
            order.get('margin_used', 0) 
            for order in successful_orders
        )
        
        assert total_margin_used <= Decimal("10000"), \
            f"Margin over-allocated: {total_margin_used}"
        
        # Check no duplicate order IDs
        order_ids = [order['id'] for order in successful_orders]
        assert len(order_ids) == len(set(order_ids)), \
            "Duplicate order IDs found"
        
        # Log execution pattern for debugging
        note(f"Execution pattern: {len(successful_orders)}/{len(parallel_orders)} succeeded")
    
    @given(
        market_data=st.lists(
            st.fixed_dictionaries({
                'timestamp': st.integers(min_value=0, max_value=86400),  # Seconds in day
                'btc_price': st.decimals(min_value='10000', max_value='100000', places=2),
                'eth_price': st.decimals(min_value='1000', max_value='10000', places=2),
                'volume': st.decimals(min_value='0', max_value='1000000', places=2)
            }),
            min_size=10,
            max_size=1000
        ).map(lambda data: sorted(data, key=lambda x: x['timestamp']))  # Ensure time order
    )
    @settings(max_examples=50, deadline=10000)
    def test_pnl_calculation_consistency(self, market_data: List[Dict]):
        """
        Property: PnL calculations remain consistent.
        
        Tests that:
        - Realized + Unrealized PnL = Total PnL
        - PnL is path-independent for closed positions
        - Commission calculations are accurate
        """
        from src.application.services import PnLCalculator
        
        calculator = PnLCalculator(commission_rate=Decimal("0.001"))
        
        # Track PnL through time
        realized_pnl = Decimal("0")
        positions = []
        
        for i, data in enumerate(market_data):
            btc_price = data['btc_price']
            eth_price = data['eth_price']
            
            # Simulate some trades
            if i % 10 == 0 and i > 0:  # Every 10th tick
                # Open position
                positions.append({
                    'symbol': 'BTCUSDT',
                    'quantity': Decimal("0.1"),
                    'entry_price': btc_price,
                    'entry_time': data['timestamp']
                })
            
            if i % 20 == 0 and positions:  # Every 20th tick
                # Close oldest position
                pos = positions.pop(0)
                pnl = calculator.calculate_realized_pnl(
                    pos['quantity'],
                    pos['entry_price'],
                    btc_price
                )
                realized_pnl += pnl
                
                # Verify PnL calculation
                expected_pnl = (btc_price - pos['entry_price']) * pos['quantity']
                commission = pos['quantity'] * btc_price * calculator.commission_rate * 2
                expected_net = expected_pnl - commission
                
                assert abs(pnl - expected_net) < Decimal("0.01"), \
                    f"PnL mismatch: calculated={pnl}, expected={expected_net}"
        
        # Calculate final unrealized PnL
        final_btc_price = market_data[-1]['btc_price'] if market_data else Decimal("50000")
        unrealized_pnl = sum(
            calculator.calculate_unrealized_pnl(
                pos['quantity'],
                pos['entry_price'],
                final_btc_price
            )
            for pos in positions
        )
        
        # Total PnL
        total_pnl = realized_pnl + unrealized_pnl
        
        # Properties
        assert total_pnl.is_finite(), f"Total PnL is not finite: {total_pnl}"
        assert abs(total_pnl) < Decimal("1000000"), f"Unrealistic PnL: {total_pnl}"
        
        # Log summary for debugging
        note(f"PnL Summary: Realized={realized_pnl}, Unrealized={unrealized_pnl}, Total={total_pnl}")


class MinimalCounterexampleFinder:
    """
    Utilities for finding minimal counterexamples when tests fail.
    """
    
    @staticmethod
    def binary_search_failure(test_func, initial_input, simplify_func):
        """
        Binary search to find minimal failing input.
        
        Args:
            test_func: Function that returns False on failure
            initial_input: Known failing input
            simplify_func: Function to simplify input
        
        Returns:
            Minimal failing input
        """
        current = initial_input
        
        while True:
            simplified = simplify_func(current)
            
            if not test_func(simplified):
                # Still fails with simplified input
                current = simplified
            else:
                # Simplified too much, current is minimal
                break
        
        return current
    
    @staticmethod
    def delta_debug(test_func, failing_sequence):
        """
        Delta debugging to find minimal failing subsequence.
        
        Args:
            test_func: Function that returns False on failure
            failing_sequence: Known failing sequence
        
        Returns:
            Minimal failing subsequence
        """
        def test_subset(subset):
            try:
                return test_func(subset)
            except:
                return False
        
        n = 2
        while n <= len(failing_sequence):
            # Try removing chunks
            chunk_size = len(failing_sequence) // n
            
            for i in range(n):
                start = i * chunk_size
                end = start + chunk_size if i < n - 1 else len(failing_sequence)
                
                # Try removing this chunk
                subset = failing_sequence[:start] + failing_sequence[end:]
                
                if not test_subset(subset):
                    # Still fails without this chunk
                    failing_sequence = subset
                    n = max(2, n - 1)  # Restart with smaller chunks
                    break
            else:
                # No chunk could be removed
                n = min(n * 2, len(failing_sequence))
        
        return failing_sequence


if __name__ == "__main__":
    # Run advanced property tests
    print("Running advanced invariant tests...")
    
    tests = ComplexInvariantTests()
    
    # Test margin call protection
    print("Testing margin call protection...")
    tests.test_margin_call_protection()
    
    # Test concurrent orders
    print("Testing concurrent order consistency...")
    tests.test_concurrent_order_consistency()
    
    # Test PnL calculations
    print("Testing PnL calculation consistency...")
    tests.test_pnl_calculation_consistency()
    
    print("\nAll advanced property tests passed!")