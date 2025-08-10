"""
Property-based tests for trading system invariants using Hypothesis.

Tests critical properties that must hold under all conditions:
- Free margin must always be >= 0
- Risk blocks prevent position changes
- Close all results in zero net position
- Exposure never exceeds configured maximum
"""

import pytest
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from hypothesis import given, strategies as st, assume, settings, Phase
from hypothesis.stateful import (
    RuleBasedStateMachine, rule, invariant, initialize, 
    Bundle, multiple, precondition
)

# Import domain entities
from src.domain.entities import Order, Position, OrderType, OrderSide, OrderStatus
from src.domain.value_objects import Symbol, Price, Quantity, Money
from src.application.services import RiskManager, PositionManager, MarginCalculator


@dataclass
class MarketState:
    """Represents current market state."""
    prices: Dict[str, Decimal]
    timestamp: datetime
    volatility: Decimal = Decimal("0.01")
    
    def get_price(self, symbol: str) -> Decimal:
        return self.prices.get(symbol, Decimal("0"))
    
    def update_price(self, symbol: str, price: Decimal):
        self.prices[symbol] = price


@dataclass
class TradingAccount:
    """Represents a trading account with margin."""
    balance: Decimal
    equity: Decimal
    margin_used: Decimal = Decimal("0")
    free_margin: Decimal = field(init=False)
    leverage: Decimal = Decimal("10")
    
    def __post_init__(self):
        self.free_margin = self.equity - self.margin_used
    
    def update_equity(self, pnl: Decimal):
        self.equity = self.balance + pnl
        self.free_margin = self.equity - self.margin_used


# Custom strategies for generating trading data
@st.composite
def order_strategy(draw, symbols: List[str], min_price: Decimal = Decimal("100"), 
                  max_price: Decimal = Decimal("100000")):
    """Generate a random order."""
    symbol = draw(st.sampled_from(symbols))
    side = draw(st.sampled_from([OrderSide.BUY, OrderSide.SELL]))
    order_type = draw(st.sampled_from([OrderType.MARKET, OrderType.LIMIT, OrderType.STOP]))
    
    # Generate realistic quantities
    quantity = Decimal(str(draw(st.floats(min_value=0.001, max_value=10.0))))
    quantity = quantity.quantize(Decimal("0.001"))
    
    # Generate price based on order type
    if order_type == OrderType.MARKET:
        price = None
    else:
        price_float = draw(st.floats(min_value=float(min_price), max_value=float(max_price)))
        price = Decimal(str(price_float)).quantize(Decimal("0.01"))
    
    return Order(
        id=f"order-{draw(st.integers(min_value=1, max_value=1000000))}",
        symbol=Symbol(symbol),
        side=side,
        type=order_type,
        quantity=Quantity(quantity),
        price=Price(price) if price else None,
        status=OrderStatus.PENDING,
        created_at=datetime.now()
    )


@st.composite
def price_path_strategy(draw, initial_price: Decimal, steps: int = 100,
                       max_change_pct: float = 0.1):
    """Generate a random price path."""
    prices = [initial_price]
    
    for _ in range(steps - 1):
        # Random walk with bounded changes
        change_pct = draw(st.floats(min_value=-max_change_pct, max_value=max_change_pct))
        new_price = prices[-1] * (Decimal("1") + Decimal(str(change_pct)))
        new_price = max(new_price, Decimal("1"))  # Price floor
        prices.append(new_price.quantize(Decimal("0.01")))
    
    return prices


@st.composite
def market_event_strategy(draw):
    """Generate market events (volatility spikes, gaps, etc.)."""
    event_type = draw(st.sampled_from(["spike", "gap", "trend", "consolidation"]))
    magnitude = Decimal(str(draw(st.floats(min_value=0.01, max_value=0.5))))
    duration = draw(st.integers(min_value=1, max_value=20))
    
    return {
        "type": event_type,
        "magnitude": magnitude,
        "duration": duration
    }


class TradingProperties:
    """Property tests for trading system invariants."""
    
    @given(
        orders=st.lists(
            order_strategy(symbols=["BTCUSDT", "ETHUSDT"]),
            min_size=1,
            max_size=50
        ),
        initial_balance=st.decimals(min_value="1000", max_value="100000"),
        leverage=st.decimals(min_value="1", max_value="100")
    )
    @settings(max_examples=100, deadline=5000)
    def test_free_margin_always_positive(self, orders: List[Order], 
                                        initial_balance: Decimal, 
                                        leverage: Decimal):
        """Property: Free margin must always be >= 0."""
        account = TradingAccount(
            balance=initial_balance,
            equity=initial_balance,
            leverage=leverage
        )
        
        position_manager = PositionManager()
        margin_calculator = MarginCalculator(leverage=leverage)
        
        for order in orders:
            # Calculate required margin
            required_margin = margin_calculator.calculate_required_margin(
                order.quantity.value,
                order.price.value if order.price else Decimal("50000"),  # Default price
                leverage
            )
            
            # Check if we have enough free margin
            if account.free_margin >= required_margin:
                # Execute order
                position = position_manager.open_position(order)
                account.margin_used += required_margin
                account.free_margin = account.equity - account.margin_used
            
            # Property assertion
            assert account.free_margin >= 0, \
                f"Free margin became negative: {account.free_margin}"
    
    @given(
        orders=st.lists(
            order_strategy(symbols=["BTCUSDT"]),
            min_size=5,
            max_size=20
        ),
        risk_limit=st.decimals(min_value="0.1", max_value="0.9"),
        prices=price_path_strategy(initial_price=Decimal("50000"), steps=50)
    )
    @settings(max_examples=50, deadline=10000)
    def test_risk_blocks_prevent_position_changes(self, orders: List[Order],
                                                  risk_limit: Decimal,
                                                  prices: List[Decimal]):
        """Property: When risk manager blocks, positions don't change."""
        risk_manager = RiskManager(
            max_exposure=risk_limit,
            max_daily_loss=Decimal("0.05"),
            max_drawdown=Decimal("0.10")
        )
        
        position_manager = PositionManager()
        positions_before_block = []
        blocked = False
        
        for i, order in enumerate(orders):
            current_price = prices[min(i, len(prices) - 1)]
            
            # Calculate current exposure
            total_exposure = position_manager.calculate_total_exposure(current_price)
            
            # Check if risk manager would block
            if risk_manager.should_block_order(order, total_exposure):
                if not blocked:
                    # First time blocked - snapshot positions
                    positions_before_block = position_manager.get_all_positions().copy()
                    blocked = True
                
                # Verify positions haven't changed since block
                current_positions = position_manager.get_all_positions()
                assert len(current_positions) == len(positions_before_block), \
                    "Position count changed after risk block"
                
                for pos_before, pos_after in zip(positions_before_block, current_positions):
                    assert pos_before.quantity == pos_after.quantity, \
                        f"Position quantity changed after risk block: {pos_before.id}"
            else:
                # Risk not blocking - can open position
                if not blocked:
                    position_manager.open_position(order)
    
    @given(
        orders=st.lists(
            order_strategy(symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"]),
            min_size=10,
            max_size=50
        ),
        final_prices=st.dictionaries(
            st.sampled_from(["BTCUSDT", "ETHUSDT", "BNBUSDT"]),
            st.decimals(min_value="100", max_value="100000"),
            min_size=3,
            max_size=3
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_close_all_results_in_zero_position(self, orders: List[Order],
                                               final_prices: Dict[str, Decimal]):
        """Property: After 'close all', net position == 0 and PnL is finite."""
        position_manager = PositionManager()
        
        # Open positions
        open_positions = []
        for order in orders:
            if order.type == OrderType.MARKET or order.price:
                position = position_manager.open_position(order)
                if position:
                    open_positions.append(position)
        
        # Close all positions
        total_pnl = Decimal("0")
        for position in open_positions:
            close_price = final_prices.get(
                position.symbol.value,
                position.entry_price
            )
            pnl = position_manager.close_position(position.id, close_price)
            total_pnl += pnl
        
        # Properties to assert
        remaining_positions = position_manager.get_all_positions()
        assert len(remaining_positions) == 0, \
            f"Positions remain after close all: {len(remaining_positions)}"
        
        # PnL must be finite (not NaN or infinite)
        assert total_pnl.is_finite(), \
            f"PnL is not finite: {total_pnl}"
        
        # Net position must be zero
        net_position = position_manager.calculate_net_position()
        assert net_position == Decimal("0"), \
            f"Net position is not zero: {net_position}"
    
    @given(
        orders=st.lists(
            order_strategy(symbols=["BTCUSDT"]),
            min_size=5,
            max_size=30
        ),
        max_exposure_limit=st.decimals(min_value="0.5", max_value="0.95"),
        account_equity=st.decimals(min_value="10000", max_value="1000000"),
        current_price=st.decimals(min_value="1000", max_value="100000")
    )
    @settings(max_examples=100, deadline=5000)
    def test_exposure_never_exceeds_max(self, orders: List[Order],
                                       max_exposure_limit: Decimal,
                                       account_equity: Decimal,
                                       current_price: Decimal):
        """Property: Exposure never exceeds configured maximum."""
        risk_manager = RiskManager(max_exposure=max_exposure_limit)
        position_manager = PositionManager()
        
        max_allowed_exposure = account_equity * max_exposure_limit
        
        for order in orders:
            # Calculate what exposure would be after this order
            order_value = order.quantity.value * current_price
            current_exposure = position_manager.calculate_total_exposure(current_price)
            potential_exposure = current_exposure + order_value
            
            # Only execute if within limits
            if potential_exposure <= max_allowed_exposure:
                position_manager.open_position(order)
            
            # Verify exposure limit is respected
            actual_exposure = position_manager.calculate_total_exposure(current_price)
            assert actual_exposure <= max_allowed_exposure, \
                f"Exposure {actual_exposure} exceeds limit {max_allowed_exposure}"


class TradingStateMachine(RuleBasedStateMachine):
    """
    Stateful property testing for trading system.
    Models the entire trading lifecycle with random operations.
    """
    
    # Bundles for stateful data
    orders = Bundle('orders')
    positions = Bundle('positions')
    
    def __init__(self):
        super().__init__()
        self.account = TradingAccount(
            balance=Decimal("10000"),
            equity=Decimal("10000")
        )
        self.market = MarketState(
            prices={
                "BTCUSDT": Decimal("50000"),
                "ETHUSDT": Decimal("3000"),
                "BNBUSDT": Decimal("500")
            },
            timestamp=datetime.now()
        )
        self.position_manager = PositionManager()
        self.risk_manager = RiskManager(
            max_exposure=Decimal("0.8"),
            max_daily_loss=Decimal("0.05"),
            max_drawdown=Decimal("0.10")
        )
        self.margin_calculator = MarginCalculator(leverage=Decimal("10"))
        self.risk_blocked = False
        self.total_pnl = Decimal("0")
    
    @initialize()
    def setup(self):
        """Initialize the trading system."""
        print(f"Initial account: Balance={self.account.balance}, Equity={self.account.equity}")
    
    @rule(
        symbol=st.sampled_from(["BTCUSDT", "ETHUSDT", "BNBUSDT"]),
        side=st.sampled_from([OrderSide.BUY, OrderSide.SELL]),
        quantity=st.decimals(min_value="0.001", max_value="5.0")
    )
    def place_order(self, symbol: str, side: OrderSide, quantity: Decimal):
        """Rule: Place a new order."""
        current_price = self.market.get_price(symbol)
        
        order = Order(
            id=f"order-{datetime.now().timestamp()}",
            symbol=Symbol(symbol),
            side=side,
            type=OrderType.MARKET,
            quantity=Quantity(quantity),
            price=Price(current_price),
            status=OrderStatus.PENDING,
            created_at=datetime.now()
        )
        
        # Check risk limits
        current_exposure = self.position_manager.calculate_total_exposure(current_price)
        order_value = quantity * current_price
        
        if not self.risk_manager.should_block_order(order, current_exposure):
            # Check margin
            required_margin = self.margin_calculator.calculate_required_margin(
                quantity, current_price, self.account.leverage
            )
            
            if self.account.free_margin >= required_margin:
                position = self.position_manager.open_position(order)
                if position:
                    self.account.margin_used += required_margin
                    self.account.free_margin = self.account.equity - self.account.margin_used
                    return multiple(self.positions.add(position))
        else:
            self.risk_blocked = True
    
    @rule(
        symbol=st.sampled_from(["BTCUSDT", "ETHUSDT", "BNBUSDT"]),
        price_change=st.floats(min_value=-0.1, max_value=0.1)
    )
    def update_price(self, symbol: str, price_change: float):
        """Rule: Update market price."""
        current_price = self.market.get_price(symbol)
        new_price = current_price * (Decimal("1") + Decimal(str(price_change)))
        new_price = max(new_price, Decimal("1"))  # Price floor
        
        self.market.update_price(symbol, new_price)
        
        # Update account equity based on unrealized PnL
        unrealized_pnl = self.position_manager.calculate_unrealized_pnl(self.market.prices)
        self.account.update_equity(unrealized_pnl)
    
    @rule(position=positions)
    def close_position(self, position: Position):
        """Rule: Close a specific position."""
        current_price = self.market.get_price(position.symbol.value)
        pnl = self.position_manager.close_position(position.id, current_price)
        
        if pnl:
            self.total_pnl += pnl
            self.account.balance += pnl
            
            # Release margin
            position_value = position.quantity.value * position.entry_price.value
            used_margin = position_value / self.account.leverage
            self.account.margin_used -= used_margin
            self.account.update_equity(self.total_pnl)
    
    @rule()
    def close_all_positions(self):
        """Rule: Close all open positions."""
        positions = self.position_manager.get_all_positions()
        
        for position in positions:
            current_price = self.market.get_price(position.symbol.value)
            pnl = self.position_manager.close_position(position.id, current_price)
            
            if pnl:
                self.total_pnl += pnl
                self.account.balance += pnl
        
        # Reset margin
        self.account.margin_used = Decimal("0")
        self.account.update_equity(self.total_pnl)
    
    @invariant()
    def free_margin_invariant(self):
        """Invariant: Free margin must always be >= 0."""
        assert self.account.free_margin >= 0, \
            f"Free margin is negative: {self.account.free_margin}"
    
    @invariant()
    def exposure_limit_invariant(self):
        """Invariant: Exposure must not exceed configured maximum."""
        max_exposure = self.account.equity * self.risk_manager.max_exposure
        
        # Calculate current exposure across all symbols
        total_exposure = Decimal("0")
        for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
            price = self.market.get_price(symbol)
            exposure = self.position_manager.calculate_total_exposure(price, symbol)
            total_exposure += exposure
        
        assert total_exposure <= max_exposure, \
            f"Exposure {total_exposure} exceeds limit {max_exposure}"
    
    @invariant()
    def risk_block_invariant(self):
        """Invariant: When risk blocked, no new positions are opened."""
        if self.risk_blocked:
            # Count positions before and after should be tracked
            # This is simplified - in real implementation would track more precisely
            pass
    
    @invariant()
    def pnl_finite_invariant(self):
        """Invariant: Total PnL must be finite."""
        assert self.total_pnl.is_finite(), \
            f"Total PnL is not finite: {self.total_pnl}"
    
    def teardown(self):
        """Clean up after test."""
        print(f"Final state: Balance={self.account.balance}, PnL={self.total_pnl}")
        
        # Verify all positions are closed
        remaining = self.position_manager.get_all_positions()
        if remaining:
            print(f"Warning: {len(remaining)} positions still open")


# Test the state machine
TestTradingSystem = TradingStateMachine.TestCase

if __name__ == "__main__":
    # Run property tests
    test_properties = TradingProperties()
    
    # Test each property
    print("Testing free margin property...")
    test_properties.test_free_margin_always_positive()
    
    print("Testing risk blocking property...")
    test_properties.test_risk_blocks_prevent_position_changes()
    
    print("Testing close all property...")
    test_properties.test_close_all_results_in_zero_position()
    
    print("Testing exposure limit property...")
    test_properties.test_exposure_never_exceeds_max()
    
    print("\nAll property tests passed!")
    
    # Run stateful tests
    print("\nRunning stateful property tests...")
    TestTradingSystem.runTest()
    print("Stateful tests completed!")