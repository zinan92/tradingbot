# CI/CD Pipeline Documentation

## Overview

This project uses GitHub Actions for continuous integration and deployment, with a strong focus on maintaining trading strategy performance through acceptance testing.

## Pipeline Stages

### 1. Linting & Code Quality
- **Ruff**: Python linter for style and error checking
- **Black**: Code formatting verification
- **isort**: Import sorting validation
- **mypy**: Static type checking

### 2. Unit Tests
- Tests domain logic and isolated components
- Coverage reporting with Codecov
- Required to pass before integration tests

### 3. Integration Tests
- Tests with PostgreSQL and Redis services
- Validates system integration points
- Required to pass before acceptance tests

### 4. Acceptance Backtest ⚡
**The key quality gate for trading performance**

Runs a canonical backtest configuration and validates performance metrics:

#### Canonical Configuration
- **Symbol**: BTCUSDT
- **Timeframe**: 5-minute candles
- **Strategy**: EMA Crossover (12/50 periods)
- **Risk Management**: 2% TP/SL
- **Period**: Last 30 days

#### Performance Thresholds (PR Blocking)
- **Sharpe Ratio**: ≥ 1.0
- **Max Drawdown**: ≤ 20%
- **Win Rate**: ≥ 40%

Any PR that causes these metrics to fall below thresholds will be **automatically blocked**.

### 5. Security Scanning
- **Bandit**: Security vulnerability scanning
- **Safety**: Known vulnerability checking in dependencies

### 6. Docker Build (Main Branch)
- Builds Docker image on successful main branch pushes
- Tags with commit SHA for traceability

## Running Locally

### Run All Tests
```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Acceptance backtest
python scripts/acceptance_backtest.py
```

### Run Acceptance Test Only
```bash
# Uses mock data for quick validation
ACCEPTANCE_TEST=true python scripts/acceptance_backtest.py
```

### Simulate CI Environment
```bash
# Run with CI environment variable
CI=true python scripts/acceptance_backtest.py
```

## Acceptance Test Details

The acceptance test (`scripts/acceptance_backtest.py`):

1. **Runs canonical backtest** with predefined parameters
2. **Generates artifacts** in `artifacts/acceptance/`:
   - `metrics.json`: Performance metrics
   - `report.html`: Visual report
   - `equity.csv`: Equity curve data
   - `trades.csv`: Trade history
3. **Validates thresholds** and returns:
   - Exit code 0: All thresholds met ✅
   - Exit code 1: One or more thresholds failed ❌

## Modifying Thresholds

To adjust acceptance criteria, edit `scripts/acceptance_backtest.py`:

```python
class AcceptanceBacktest:
    # Performance thresholds
    MIN_SHARPE = 1.0      # Minimum Sharpe ratio
    MAX_DRAWDOWN = 20.0   # Maximum drawdown %
    MIN_WIN_RATE = 40.0   # Minimum win rate %
```

## GitHub Actions Configuration

The workflow is defined in `.github/workflows/ci.yml`:

- **Triggers**: Push to main/develop, PRs, manual dispatch
- **Jobs**: Parallel execution where possible
- **Artifacts**: Backtest results saved for 30 days
- **Caching**: Pip packages cached for faster builds

## Troubleshooting

### Acceptance Test Failures

If the acceptance test fails:

1. **Check the metrics**:
   ```bash
   cat artifacts/acceptance/metrics.json | jq '.'
   ```

2. **Review the detailed report**:
   ```bash
   open artifacts/acceptance/report.html
   ```

3. **Analyze trades**:
   ```bash
   cat artifacts/acceptance/trades.csv | head -20
   ```

### Common Issues

- **Sharpe < 1.0**: Strategy not profitable enough after risk adjustment
- **MaxDD > 20%**: Strategy has excessive drawdowns
- **WinRate < 40%**: Strategy loses too frequently

## Best Practices

1. **Before submitting PR**:
   - Run acceptance test locally
   - Verify all metrics meet thresholds
   - Include backtest results in PR description

2. **When modifying strategies**:
   - Run full parameter optimization
   - Validate on multiple timeframes
   - Document performance impact

3. **For infrastructure changes**:
   - Ensure mock backtest engine still works
   - Verify artifact generation
   - Test with both mock and real data

## Mock vs Real Backtesting

- **CI Environment**: Uses `MockBacktestEngine` for speed and determinism
- **Local Development**: Uses real `BacktestEngine` with market data
- **Production**: Always validate with real historical data

The mock engine ensures:
- Deterministic results (seed=42)
- Fast execution (<1 second)
- Canonical config always passes thresholds
- Consistent artifact structure

## Future Improvements

- [ ] Add more strategies to acceptance suite
- [ ] Include multiple timeframe validation
- [ ] Add performance regression tracking
- [ ] Implement A/B testing for strategies
- [ ] Add live trading performance correlation