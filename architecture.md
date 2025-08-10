# Architecture — Quant Trading Bot

## Goals
- Modular, hexagonal design: business logic in domain layer, infrastructure via adapters.
- Replaceable modules without breaking flows.
- High observability and testability.

## High-Level Structure

### Domains / Modules
1. **Data Fetching**
   - Port: `MarketDataPort`
   - Adapters: Binance REST/WS, CSV loader
2. **Indicator Calculation**
   - Port: `IndicatorPort`
   - Adapters: TA-Lib, custom calc
3. **Strategy Management**
   - Port: `StrategyRegistryPort`
   - Adapters: Postgres repo
4. **Backtesting**
   - Port: `BacktestPort`
   - Adapters: Vectorized engine, Futures simulation
5. **Live Trading**
   - Port: `ExecutionPort`, `EventBusPort`
   - Adapters: Binance broker, Redis/Kafka bus
6. **Risk Management**
   - Port: `RiskPort`
   - Adapters: In-memory / DB risk rules
7. **Monitoring**
   - Port: `TelemetryPort`
   - Adapters: Prometheus, Log store

### Adapters (Infrastructure Layer)
- API adapter (FastAPI) exposing `/health`, `/metrics`, UI endpoints.
- Broker adapters for Binance Futures.
- Event bus adapters for messaging.

### Ports (Interfaces)
- Each module’s public API defined in `domain/shared/ports`.
- Modules only depend on other modules via ports.

## Data Flow (Example: Live Trade)
1. Strategy signal → Strategy Service
2. Signal → RiskPort.validate_trade()
3. If pass → ExecutionPort.send_order()
4. Broker adapter sends to exchange
5. Event published via EventBusPort
6. Monitoring adapter records metrics

## Observability
- `/health`: status, last success, latency.
- `/metrics`: module-specific metrics (PnL, latency, error rate, exposure).
- Logs: structured, per-module, rotated.

## Testing
- **E2E approval tests**: run known scenarios, compare output to golden baseline.
- **Contract tests**: verify port <-> adapter compatibility.
- **Property tests**: enforce invariants (no negative sizes, no NaN PnL, exposure ≤ 100%).

## Deployment
- Containers per module (or monolith mode).
- CI: lint, unit, contract, E2E, acceptance backtests.
- CD: testnet → paper → mainnet promotion gated by metrics and approvals.
