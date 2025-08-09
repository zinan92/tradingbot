# Quantitative Trading System - Production-Ready Implementation

A comprehensive, end-to-end algorithmic trading platform for cryptocurrency futures markets with real-time data processing, backtesting, live trading, and risk management capabilities.

## 🚀 Overview

This is a production-ready quantitative trading system designed for 24/7 autonomous operation on Binance Futures markets. The system combines robust architecture with practical trading functionality, emphasizing stability and reliability over complexity.

### Key Features

- **Real-time Market Data**: WebSocket streaming with automatic reconnection and data validation
- **Technical Analysis**: 20+ built-in indicators with event-driven calculation pipeline
- **Backtesting Engine**: Historical simulation with realistic fee modeling and slippage
- **Live Trading**: Production-ready execution with state recovery and error handling
- **Risk Management**: Pre-trade validation, position limits, and portfolio protection
- **Web Dashboard**: Real-time monitoring with portfolio analytics and trade history
- **Data Persistence**: PostgreSQL storage with optimized schemas for time-series data

## 🏗️ System Architecture

### High-Level Design

The system follows a modular, event-driven architecture that ensures reliability and maintainability:

```
┌─────────────────────────────────────────────────────────────┐
│                        Web Dashboard                         │
│                    (React + TypeScript)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API / WebSocket
┌──────────────────────▼──────────────────────────────────────┐
│                      API Gateway                             │
│                      (FastAPI)                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  Application Layer                           │
│  ┌──────────────┬──────────────┬──────────────┬──────────┐ │
│  │   Trading    │  Backtesting │   Strategy   │   Risk    │ │
│  │   Commands   │   Services   │   Bridge     │   Mgmt    │ │
│  └──────────────┴──────────────┴──────────────┴──────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │ Events
┌──────────────────────▼──────────────────────────────────────┐
│                    Domain Layer                              │
│  ┌──────────────┬──────────────┬──────────────┬──────────┐ │
│  │    Orders    │  Portfolios  │  Strategies  │   Risk    │ │
│  │  Aggregates  │  Aggregates  │  Aggregates  │  Rules    │ │
│  └──────────────┴──────────────┴──────────────┴──────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 Infrastructure Layer                         │
│  ┌──────────────┬──────────────┬──────────────┬──────────┐ │
│  │   Binance    │  PostgreSQL  │   Market     │  Event    │ │
│  │    Broker    │ Repositories │   Data WS    │   Bus     │ │
│  └──────────────┴──────────────┴──────────────┴──────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Design Principles

- **Domain-Driven Design**: Core business logic isolated from external dependencies
- **Hexagonal Architecture**: Ports and adapters for flexible integration
- **Event-Driven**: Loose coupling between components via domain events
- **Fault Tolerance**: Automatic recovery, circuit breakers, and graceful degradation

## 📦 Implemented Modules

### ✅ Complete Modules

#### 1. Market Data Infrastructure (`src/infrastructure/market_data/`)
- **Binance Integration**: REST API and WebSocket streaming
- **Data Types**: Klines, order books, trades, funding rates
- **Storage**: Optimized PostgreSQL schemas with indexing
- **Features**:
  - Automatic reconnection on disconnect
  - Rate limit handling
  - Data validation and normalization
  - Gap detection and backfilling

#### 2. Technical Indicators (`src/infrastructure/indicators/`)
- **Trend Indicators**: SMA, EMA, MACD, Ichimoku
- **Momentum**: RSI, Stochastic, Williams %R, CCI
- **Volatility**: Bollinger Bands, ATR, Standard Deviation
- **Volume**: OBV, VWAP, Volume Profile
- **Features**:
  - Real-time calculation on new data
  - Batch historical calculation
  - Event publishing for strategy consumption

#### 3. Backtesting Engine (`src/infrastructure/backtesting/`)
- **Strategy Types**: Grid, SMA Cross, EMA Cross, RSI, MACD
- **Futures Support**: Leverage, funding fees, liquidation
- **Performance Metrics**:
  - Sharpe ratio, max drawdown, win rate
  - Trade-by-trade analysis
  - HTML report generation with charts
- **Features**:
  - Realistic fee modeling
  - Slippage simulation
  - Multi-timeframe support

#### 4. Live Trading System (`src/application/trading/`)
- **Order Management**: Place, cancel, modify orders
- **Execution**: Market and limit orders with smart routing
- **State Management**: Persistent state with recovery
- **Features**:
  - WebSocket order updates
  - Position tracking
  - P&L calculation in real-time

#### 5. Web Dashboard (`web/`)
- **Portfolio View**: Balance, P&L, positions, performance
- **Trade Monitor**: Recent trades, order status, execution history
- **Strategy Control**: Start/stop strategies, parameter adjustment
- **Analytics**: Win rate, average return, risk metrics
- **Tech Stack**: React, TypeScript, Tailwind CSS

### 🚧 Partial Implementation

#### Risk Management (`src/application/trading/risk_management.py`)
- ✅ Pre-trade validation
- ✅ Position size limits
- ⚠️ Portfolio-level limits (needs enhancement)
- ⚠️ Correlation-based sizing (planned)
- ⚠️ Dynamic stop-loss (planned)

## 🔧 Installation & Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 14+
- Node.js 18+ (for web dashboard)
- Binance account (testnet for development)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/tradingbot_v2.git
cd tradingbot_v2
```

### 2. Python Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Setup

```bash
# Create database
createdb tradingbot

# Run migrations
psql -d tradingbot -f src/infrastructure/persistence/postgres/migrations/001_initial_schema.sql
psql -d tradingbot -f src/infrastructure/persistence/postgres/migrations/002_market_data.sql
psql -d tradingbot -f src/infrastructure/persistence/postgres/migrations/003_create_backtest_results.sql
```

### 4. Environment Configuration

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/tradingbot

# Binance Testnet (Start here!)
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_API_SECRET=your_testnet_api_secret

# Binance Production (Only after thorough testing)
BINANCE_API_KEY=your_production_api_key
BINANCE_API_SECRET=your_production_api_secret

# Application
ENVIRONMENT=testnet  # or production
DRY_RUN=true  # Set to false for real trading
LOG_LEVEL=INFO
```

### 5. Verify Setup

```bash
# Test database connection
python -c "from src.infrastructure.persistence.postgres import engine; print('DB connected!')"

# Test Binance connection
python scripts/test_binance_connection.py --testnet

# Run tests
pytest tests/
```

## 📊 Usage Examples

### 1. Download Historical Data

```bash
# Download recent data for backtesting
python scripts/data_download/quick_download.py --symbols BTCUSDT ETHUSDT --days 30

# Download specific date range
python scripts/data_download/start_full_download.py \
    --symbols BTCUSDT \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --intervals 1h 4h 1d
```

### 2. Run Backtests

```bash
# Simple SMA crossover backtest
python scripts/backtesting/demo_backtest.py

# Grid strategy backtest
python scripts/backtesting/run_grid_strategy_backtest.py \
    --symbol BTCUSDT \
    --interval 1h \
    --start-date 2024-01-01 \
    --end-date 2024-02-01

# Compare multiple strategies
python scripts/backtesting/run_all_strategies_comparison.py
```

### 3. Start Live Trading

```bash
# Start with paper trading (testnet)
python scripts/start_live_trading.py --paper-trade --testnet

# Monitor live performance
python scripts/monitor_live_updates.py

# Production trading (after thorough testing!)
python scripts/start_live_trading.py --config config/live_trading_config.yaml
```

### 4. Launch Web Dashboard

```bash
# Quick start (automatic setup)
cd web
./start.sh

# Manual start
cd web/backend
python api_server.py &
cd ../frontend
npm install
npm run dev
# Open http://localhost:5174
```

### 5. Data Analysis

```bash
# Check data integrity
python scripts/data_validation_tests.py

# Calculate missing indicators
python scripts/indicators/calculate_missing_indicators.py

# Generate performance report
python scripts/generate_backtest_summary.py
```

## 🛡️ Development Roadmap - Stability & Robustness Focus

### Phase 1: Core Stability (Immediate)

#### Error Handling & Recovery
- [ ] WebSocket auto-reconnection with exponential backoff
- [ ] API rate limit detection and queue management
- [ ] Database connection pooling with retry logic
- [ ] Order execution failure recovery procedures
- [ ] Circuit breaker pattern for external services

#### System Monitoring
- [ ] Health check endpoints for all services
- [ ] Prometheus metrics integration
- [ ] Centralized logging with log aggregation
- [ ] Resource usage monitoring (CPU, memory, network)
- [ ] Alert system for critical failures

#### Data Integrity
- [ ] Continuous data validation pipeline
- [ ] Duplicate detection and handling
- [ ] Missing data gap detection and alerting
- [ ] Indicator calculation verification
- [ ] Data reconciliation procedures

### Phase 2: Production Readiness

#### Testing & Quality
- [ ] Increase unit test coverage to 80%+
- [ ] Integration tests for critical trading paths
- [ ] End-to-end testing suite
- [ ] Performance regression tests
- [ ] Continuous Integration (CI) pipeline

#### Risk Management Completion
- [ ] Portfolio-level position limits
- [ ] Maximum drawdown protection
- [ ] Correlation-based position sizing
- [ ] Dynamic stop-loss adjustment
- [ ] Emergency shutdown procedures

#### Operational Excellence
- [ ] Automated backup and restore
- [ ] Blue-green deployment support
- [ ] Configuration management system
- [ ] Audit logging for all trades
- [ ] Disaster recovery procedures

### Phase 3: Enhanced Reliability

#### Performance Optimization
- [ ] Query optimization for large datasets
- [ ] Caching layer for frequently accessed data
- [ ] Batch processing for indicator calculations
- [ ] Memory usage optimization
- [ ] Network bandwidth optimization

#### Documentation & Knowledge
- [ ] Complete API documentation
- [ ] Troubleshooting guide
- [ ] Runbook for common issues
- [ ] Performance tuning guide
- [ ] Video tutorials for setup

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test categories
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests
pytest tests/domain/        # Domain logic tests

# Run with verbose output
pytest -v tests/
```

### Test Coverage Status

- Domain Layer: ~75% coverage
- Application Layer: ~60% coverage
- Infrastructure Layer: ~50% coverage
- API Endpoints: ~70% coverage

## 🔍 Troubleshooting

### Common Issues

1. **WebSocket Disconnections**
   - Check internet connectivity
   - Verify API keys are valid
   - Monitor rate limits in logs

2. **Database Connection Errors**
   - Verify PostgreSQL is running
   - Check connection string in .env
   - Ensure database exists

3. **Indicator Calculation Errors**
   - Verify sufficient historical data
   - Check for data gaps
   - Run data validation script

4. **Order Execution Failures**
   - Check account balance
   - Verify API permissions
   - Monitor position limits

### Debug Commands

```bash
# Check system status
python scripts/utils/check_system_health.py

# Verify data integrity
python scripts/data_validation_tests.py

# Test exchange connectivity
python scripts/test_binance_connection.py

# View recent logs
tail -f logs/trading.log
```

## 📚 Documentation

- [Binance API Setup Guide](BINANCE_API_SETUP.md)
- [Web Dashboard Documentation](web/README.md)
- [Market Data Infrastructure](src/infrastructure/market_data/README.md)
- [API Documentation](http://localhost:8000/docs) (when running)

## 🤝 Contributing

We welcome contributions that improve system stability and reliability. Please focus on:

1. Bug fixes and error handling improvements
2. Test coverage increases
3. Documentation improvements
4. Performance optimizations

Before submitting PRs:
- Run all tests: `pytest`
- Check code style: `black src/ tests/`
- Update relevant documentation

## 📄 License

This project is proprietary software. All rights reserved.

## ⚠️ Disclaimer

This software is for educational and research purposes. Trading cryptocurrencies carries significant risk. Always test thoroughly on testnet before using real funds. The authors are not responsible for any financial losses.

## 🆘 Support

For issues and questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review existing issues on GitHub
- Contact the development team

---

**Remember**: The goal is a trading system that runs 24/7 without manual intervention. Stability and reliability are more important than features.