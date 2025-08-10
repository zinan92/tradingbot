# Property-Based Testing with Hypothesis

This document describes the property-based testing implementation using Hypothesis for the trading system, ensuring critical invariants hold under all conditions.

## Overview

Property-based testing generates random test data to verify that system invariants are maintained. Unlike traditional unit tests with fixed inputs, property tests explore the edge cases automatically and provide minimal counterexamples when failures occur.

## Core Properties Tested

### 1. **Free Margin Invariant**
```python
free_margin >= 0 at all times
```
- Ensures account never goes into negative margin
- Tests with random order sequences and leverage levels
- Validates margin calculations remain consistent

### 2. **Risk Blocking Invariant**
```python
when Risk blocks, positions do not change
```
- Verifies risk manager prevents new positions when limits exceeded
- Tests that existing positions remain unchanged after block
- Validates risk thresholds are enforced

### 3. **Close All Invariant**
```python
after "close all", net position == 0 and PnL is finite
```
- Ensures all positions are properly closed
- Verifies PnL calculations produce finite values
- Tests that no positions remain after close all operation

### 4. **Exposure Limit Invariant**
```python
exposure never exceeds configured max
```
- Validates exposure limits are respected
- Tests with various account sizes and leverage
- Ensures position sizing adheres to limits

## Test Structure

```
tests/property/
├── test_trading_invariants.py      # Basic property tests
├── test_advanced_invariants.py     # Complex scenarios
└── run_property_tests.py          # Test runner with reporting
```

## Running Property Tests

### Quick Test
```bash
# Run basic property tests
python tests/property/run_property_tests.py
```

### Detailed Testing
```bash
# Run with verbose output
python -m pytest tests/property/ -v --hypothesis-show-statistics

# Run specific property
python -m pytest tests/property/test_trading_invariants.py::TradingProperties::test_free_margin_always_positive -v

# Run with specific seed for reproducibility
python -m pytest tests/property/ --hypothesis-seed=12345
```

### CI Testing
```bash
# Run with more examples for thorough testing
python -m pytest tests/property/ --hypothesis-profile=ci
```

## Custom Strategies

### Order Generation
```python
@st.composite
def order_strategy(draw, symbols: List[str]):
    """Generate random orders with realistic parameters."""
    return Order(
        symbol=draw(st.sampled_from(symbols)),
        side=draw(st.sampled_from([OrderSide.BUY, OrderSide.SELL])),
        quantity=draw(st.decimals(min_value='0.001', max_value='10')),
        price=draw(st.decimals(min_value='100', max_value='100000'))
    )
```

### Price Path Generation
```python
@st.composite
def price_path_strategy(draw, initial_price: Decimal):
    """Generate realistic price movements."""
    prices = [initial_price]
    for _ in range(draw(st.integers(10, 100))):
        change = draw(st.floats(-0.1, 0.1))
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, 1))  # Price floor
    return prices
```

## Stateful Testing

The `TradingStateMachine` models the complete trading lifecycle:

```python
class TradingStateMachine(RuleBasedStateMachine):
    @rule(symbol=st.sampled_from(['BTCUSDT', 'ETHUSDT']))
    def place_order(self, symbol):
        # Place random order
        
    @rule(price_change=st.floats(-0.1, 0.1))
    def update_price(self, price_change):
        # Update market prices
        
    @invariant()
    def free_margin_invariant(self):
        assert self.account.free_margin >= 0
```

## Minimal Counterexamples

When a test fails, Hypothesis automatically shrinks the input to find the minimal failing case:

### Example Output
```
Failed: test_margin_call_protection

Minimal Counterexample:
  Orders: 2
  Order 1: BTCUSDT BUY 1.0 @ 50000 (leverage: 100)
  Order 2: Price drops to 25000 (50% crash)
  Result: Account equity went negative: -500

To reproduce:
@reproduce_failure('6.137.1', b'AXicY2BgYGAAABYABg==')
```

### Shrinking Strategies

1. **Order Sequence Shrinking**
   - Remove orders from end
   - Remove orders from middle
   - Simplify parameters (single symbol, round numbers)
   - Reduce quantities to minimum

2. **Price Path Shrinking**
   - Shorten path length
   - Reduce volatility
   - Flatten to constant prices
   - Minimize number of changes

3. **Delta Debugging**
   - Binary search for minimal subset
   - Remove chunks systematically
   - Preserve failure condition

## Advanced Properties

### Margin Call Protection
```python
def test_margin_call_protection(self, scenario):
    """System must protect against margin calls."""
    # Tests sudden price drops
    # High leverage positions
    # Cascade liquidations
```

### Concurrent Order Consistency
```python
def test_concurrent_order_consistency(self, parallel_orders):
    """Concurrent orders maintain consistency."""
    # No negative positions
    # Correct margin calculations
    # No double-spending of margin
```

### PnL Calculation Consistency
```python
def test_pnl_calculation_consistency(self, market_data):
    """PnL calculations remain consistent."""
    # Realized + Unrealized = Total
    # Path-independent for closed positions
    # Accurate commission calculations
```

## Configuration

### Hypothesis Settings

```python
settings.register_profile(
    "dev",
    max_examples=50,           # Number of test cases
    deadline=10000,            # Timeout in ms
    verbosity=Verbosity.verbose,
    phases=[                   # Test phases
        Phase.explicit,        # Run @example decorators
        Phase.reuse,          # Reuse previous failures
        Phase.generate,       # Generate new examples
        Phase.shrink          # Shrink failures
    ]
)
```

### Health Checks

Suppress slow test warnings:
```python
suppress_health_check=[
    HealthCheck.too_slow,
    HealthCheck.data_too_large
]
```

## Debugging Failed Tests

### 1. Reproduce Specific Failure
```python
# Add this decorator to reproduce
@reproduce_failure('6.137.1', b'AXicY2BgYGAAABYABg==')
def test_something():
    pass
```

### 2. Increase Verbosity
```python
@settings(verbosity=Verbosity.debug)
def test_with_details():
    pass
```

### 3. Add Notes for Debugging
```python
from hypothesis import note

def test_with_notes(data):
    note(f"Processing {len(data)} items")
    # Test logic
```

### 4. Track Events
```python
from hypothesis import event

def test_with_events(orders):
    for order in orders:
        if order.quantity > 5:
            event("large_order")
    # Test logic
```

## Best Practices

1. **Keep Properties Simple**
   - One property per test
   - Clear assertion messages
   - Avoid complex logic in properties

2. **Use Appropriate Strategies**
   - Realistic value ranges
   - Domain-specific constraints
   - Proper type annotations

3. **Handle Assumptions**
   ```python
   assume(price > 0)  # Skip invalid cases
   ```

4. **Profile-Based Testing**
   - Fast profile for development
   - Thorough profile for CI
   - Custom profiles for specific scenarios

5. **Database for Regression**
   ```python
   database=DirectoryBasedExampleDatabase(".hypothesis")
   ```

## Common Issues and Solutions

### Issue: Tests Too Slow
**Solution:** Adjust deadline or reduce max_examples
```python
@settings(deadline=30000, max_examples=10)
```

### Issue: Flaky Tests
**Solution:** Use deterministic strategies
```python
@seed(12345)  # Fixed seed for debugging
```

### Issue: Memory Usage
**Solution:** Limit data size
```python
st.lists(..., max_size=100)
```

### Issue: Complex Failures
**Solution:** Add intermediate assertions
```python
assert step1_result, "Step 1 failed"
assert step2_result, "Step 2 failed"
```

## Integration with CI/CD

### GitHub Actions
```yaml
- name: Run Property Tests
  run: |
    python -m pytest tests/property/ \
      --hypothesis-profile=ci \
      --hypothesis-show-statistics \
      --junit-xml=property-test-results.xml
```

### Coverage Report
```bash
pytest tests/property/ --cov=src --cov-report=html
```

## Performance Considerations

1. **Parallel Execution**
   ```bash
   pytest tests/property/ -n auto
   ```

2. **Caching Examples**
   - Hypothesis caches interesting examples
   - Reuses them in future runs
   - Speeds up regression testing

3. **Shrinking Optimization**
   - Custom shrink functions for domain objects
   - Limit shrinking passes for complex data
   - Use simpler strategies when possible

## Extending Property Tests

### Adding New Properties
1. Identify invariant to test
2. Create appropriate data generators
3. Implement property function
4. Add shrinking strategy
5. Document expected behavior

### Custom Strategies
```python
@st.composite
def custom_strategy(draw):
    # Generate complex domain object
    return DomainObject(...)
```

### Stateful Rules
```python
@rule(target=orders, value=order_strategy())
def place_order(self, value):
    # Add to bundle for later use
    return value
```

## Success Metrics

Property tests are successful when:
- ✅ All invariants hold under random testing
- ✅ Failures produce minimal counterexamples
- ✅ Tests complete within time limits
- ✅ Coverage includes edge cases
- ✅ Shrinking produces understandable failures

## Resources

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing Guide](https://hypothesis.works/articles/what-is-property-based-testing/)
- [Stateful Testing](https://hypothesis.readthedocs.io/en/latest/stateful.html)
- [Shrinking Explained](https://hypothesis.works/articles/shrinking/)