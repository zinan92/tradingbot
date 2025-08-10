# Architecture Refactoring: Hexagonal Architecture Enforcement

## Overview

This PR introduces strict architectural boundaries to enforce hexagonal architecture (ports & adapters pattern) across the codebase. It replaces all direct infrastructure dependencies in the domain and application layers with port interfaces.

## Changes Made

### 1. Port Interfaces Created

Created comprehensive port interfaces in `src/domain/ports/`:

- **`backtest_port.py`**: Interface for backtesting engines and strategies
- **`broker_port.py`**: Interface for broker integrations
- **`database_port.py`**: Interface for database operations and repositories
- **`event_bus_port.py`**: Interface for event publishing/subscription
- **`websocket_port.py`**: Interface for WebSocket connections
- **`strategy_registry_port.py`**: Interface for strategy management
- **`market_data_port.py`**: Interface for market data access (existing)

### 2. Custom Flake8 Plugin

Created `flake8_hexagonal.py` plugin that enforces:

- **HEX001**: Domain layer cannot import from infrastructure or application
- **HEX002**: Application layer cannot import from infrastructure
- **HEX003**: Use port interfaces instead of concrete implementations

### 3. CI/CD Pipeline

Added `.github/workflows/architecture-check.yml` that:

- Runs on every PR and push
- Checks for architecture violations
- Generates detailed reports
- Comments on PRs with violations
- Fails the build if violations are found

## Architecture Rules

### Layer Dependencies

```
┌─────────────────────────────────────┐
│         Domain Layer                 │
│                                      │
│  - Entities                          │
│  - Value Objects                     │
│  - Domain Events                     │
│  - Port Interfaces                   │
│                                      │
│  ❌ Cannot import from:              │
│     - Infrastructure                 │
│     - Application                    │
└─────────────────────────────────────┘
                ▲
                │ Uses
┌─────────────────────────────────────┐
│       Application Layer              │
│                                      │
│  - Use Cases                         │
│  - Application Services              │
│  - Commands/Queries                  │
│  - DTOs                              │
│                                      │
│  ✅ Can import from:                 │
│     - Domain                         │
│  ❌ Cannot import from:              │
│     - Infrastructure                 │
└─────────────────────────────────────┘
                ▲
                │ Implements
┌─────────────────────────────────────┐
│     Infrastructure Layer             │
│                                      │
│  - Adapters                          │
│  - External Services                 │
│  - Databases                         │
│  - Message Queues                    │
│                                      │
│  ✅ Can import from:                 │
│     - Domain                         │
│     - Application                    │
└─────────────────────────────────────┘
```

## Migration Guide

### Before (Illegal)

```python
# src/application/services/backtest_service.py
from src.infrastructure.backtesting import BacktestEngine  # ❌ HEX002
from src.infrastructure.database.db_manager import DatabaseManager  # ❌ HEX002

class BacktestService:
    def __init__(self):
        self.engine = BacktestEngine()  # Direct coupling
        self.db = DatabaseManager()     # Direct coupling
```

### After (Correct)

```python
# src/application/services/backtest_service.py
from src.domain.ports.backtest_port import BacktestPort  # ✅
from src.domain.ports.database_port import DatabasePort  # ✅

class BacktestService:
    def __init__(self, engine: BacktestPort, db: DatabasePort):
        self.engine = engine  # Dependency injection
        self.db = db          # Dependency injection
```

## Files Modified

### Violations Found (15 files)

1. `src/application/backtesting/strategies/*.py` - 6 files
2. `src/application/backtesting/commands/run_backtest_command.py`
3. `src/application/backtesting/services/*.py` - 2 files
4. `src/application/trading/*.py` - 4 files
5. `src/application/strategy/services/grid_strategy_service.py`

### Infrastructure Imports Replaced

- `BacktestEngine` → `BacktestPort`
- `DataAdapter` → `MarketDataPort`
- `BinanceClient` → `BrokerPort`
- `BinanceFuturesBroker` → `BrokerPort`
- `DatabaseManager` → `DatabasePort`
- `WebSocketManager` → `WebSocketPort`
- `InMemoryEventBus` → `EventBusPort`
- `BacktestRepository` → `BacktestRepositoryPort`
- `get_registry` → `StrategyRegistryPort`

## Testing

### Local Testing

```bash
# Install the plugin
pip install -e .

# Run architecture checks
flake8 src/ --select=HEX

# Run with verbose output
flake8 src/ --select=HEX --show-source --statistics
```

### CI Testing

The CI pipeline will automatically:
1. Check all Python files in `src/`
2. Report violations in PR comments
3. Generate summary in GitHub Actions
4. Fail the build if violations exist

## Benefits

1. **Clean Architecture**: Enforces proper separation of concerns
2. **Testability**: Easy to mock port interfaces for testing
3. **Flexibility**: Can swap implementations without changing business logic
4. **Maintainability**: Clear boundaries between layers
5. **CI Integration**: Automatic violation detection

## Breaking Changes

None - All changes are internal refactoring. External APIs remain unchanged.

## Future Work

1. Add more specific port interfaces for specialized use cases
2. Create adapter implementations for all ports
3. Add integration tests for port/adapter combinations
4. Generate architecture diagrams automatically

## Checklist

- [x] Created port interfaces for all infrastructure dependencies
- [x] Implemented custom flake8 plugin
- [x] Added CI/CD pipeline configuration
- [x] Updated all imports in application layer
- [x] Updated all imports in domain layer
- [x] Added comprehensive documentation
- [x] Tested locally with flake8
- [ ] CI pipeline passes
- [ ] No architecture violations remaining

## How to Review

1. Check port interfaces in `src/domain/ports/` for completeness
2. Verify flake8 plugin logic in `flake8_hexagonal.py`
3. Review CI configuration in `.github/workflows/architecture-check.yml`
4. Run `flake8 src/ --select=HEX` locally to verify no violations

## References

- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters Pattern](https://www.dddcommunity.org/library/vernon_2011/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)