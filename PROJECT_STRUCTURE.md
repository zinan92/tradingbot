# Trading Bot v2 - Project Structure

## Overview
A module-driven trading bot architecture following hexagonal principles.

## Directory Structure

```
tradingbot_v2/
├── backend/                 # Main backend application
│   ├── app.py              # FastAPI application entry point
│   ├── boot/               # Configuration and dependency injection
│   │   ├── container.py    # DI container with service factories
│   │   └── settings.py     # Environment-based configuration
│   └── modules/            # Business modules (hexagonal architecture)
│       ├── backtesting/    # Strategy testing and validation
│       ├── data_analysis/  # Technical indicators and analysis
│       ├── data_fetch/     # Market data fetching and storage
│       ├── live_trade/     # Live trading execution
│       ├── monitoring/     # Metrics and system monitoring
│       ├── risk/           # Risk management and controls
│       └── strategy_management/ # Strategy handling (to be completed)
│
├── tests/                  # All test files
│   ├── api/               # API endpoint tests
│   ├── application/       # Application layer tests
│   ├── domain/            # Domain logic tests
│   ├── e2e/               # End-to-end tests
│   ├── infrastructure/    # Infrastructure tests
│   ├── integration/       # Integration tests
│   └── unit/              # Unit tests
│
├── scripts/               # Utility and operational scripts
│   ├── analysis/          # Data analysis scripts
│   ├── backtesting/       # Backtesting utilities
│   ├── data_download/     # Data downloading tools
│   └── indicators/        # Indicator calculation scripts
│
├── docs/                  # Documentation
│   ├── architecture/      # Architecture documentation
│   ├── guides/            # User guides
│   └── modules/           # Module-specific docs
│
├── configs/               # Configuration files
│   ├── feature_flags.json
│   ├── live_trading_config.yaml
│   └── market_data_config.yaml
│
├── dashboard/             # Trading dashboard (Streamlit)
├── web/                   # Web frontend (React/Next.js)
├── data/                  # Data storage
├── logs/                  # Application logs
├── outputs/               # Generated outputs
└── artifacts/             # Build and test artifacts
```

## Module Architecture

Each module follows the hexagonal architecture pattern with 5 distinct roles:

### File Naming Convention
- `core_*.py` - Pure business logic, no external dependencies
- `service_*.py` - Application services orchestrating use cases
- `port_*.py` - Interface definitions (Protocol classes)
- `adapter_*.py` - External system implementations
- `api_*.py` - REST API endpoints

### Example: data_fetch module
```
data_fetch/
├── core_fetch_planner.py        # Business logic for planning fetches
├── core_merge_candles.py        # Logic for merging candle data
├── service_fetch_klines.py      # Service for real-time fetching
├── service_backfill_klines.py   # Service for historical backfilling
├── port_market_data.py          # Interface definitions
├── adapter_marketdata_binance.py # Binance implementation
├── adapter_marketdata_postgres.py # PostgreSQL storage
└── adapter_marketdata_replay.py  # Replay adapter for testing
```

## Key Features

### 1. Clean Architecture
- **Dependency Inversion**: All dependencies point inward
- **Port/Adapter Pattern**: External systems accessed through interfaces
- **Single Responsibility**: Each module has one well-defined purpose

### 2. Configuration Management
- Environment-based settings via Pydantic
- Feature flags for module activation
- Centralized configuration in `boot/settings.py`

### 3. Dependency Injection
- Factory pattern in `boot/container.py`
- Easy mocking for testing
- Clear service dependencies

### 4. API Structure
- FastAPI with automatic documentation
- Health checks and metrics endpoints
- Module-based router organization

## Running the Application

### Start the Backend
```bash
# Development mode
python3 -m uvicorn backend.app:app --reload --port 8000

# Production mode
python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### API Endpoints
- `GET /` - Root endpoint with API info
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
- `GET /docs` - Interactive API documentation

### Module-Specific Endpoints
- `/api/backtest/*` - Backtesting operations
- `/api/live/*` - Live trading operations
- `/api/risk/*` - Risk assessment
- `/api/data/*` - Market data operations

## Environment Variables

Create a `.env` file with:
```bash
# Environment
ENVIRONMENT=development

# Database
DATABASE_URL=postgresql://user:pass@localhost/tradingbot

# Exchange API
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# Feature Flags
ENABLE_BACKTESTING=true
ENABLE_LIVE_TRADING=false
ENABLE_RISK_MANAGEMENT=true
ENABLE_MONITORING=true
```

## Testing

```bash
# Run all tests
pytest

# Run specific module tests
pytest tests/unit/backend/modules/data_fetch/

# Run with coverage
pytest --cov=backend --cov-report=html
```

## Next Steps

1. Complete `strategy_management` module implementation
2. Add more comprehensive tests
3. Set up CI/CD pipeline
4. Deploy to production environment
5. Add monitoring and alerting

