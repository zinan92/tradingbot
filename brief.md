# Quant Trading Bot — Brief

## Purpose
Provide a unified web interface and robust backend to monitor, manage, and operate a multi-module algorithmic trading system — covering:
1. Data Fetching
2. Indicator Calculation
3. Strategy Management
4. Backtesting
5. Live Trading
6. Risk Management
7. Monitoring & Observability

Current CLI-based workflows limit real-time visibility and require manual intervention for safety checks. This project’s goal is to deliver:
- **Visibility**: Always know the status and health of each module.
- **Safety**: Embed risk checks before execution and enforce a testnet→paper→mainnet ladder.
- **Repeatability**: Define strategy acceptance by quantitative backtest metrics.
- **Extensibility**: Modular, hexagonal architecture to swap components without breaking flows.

## Scope (MVP)
- Web dashboard with module-level status indicators (green/yellow/red), metrics, and drill-down views.
- Ability to deploy, pause, stop, and close strategies via UI, with pre-trade risk validation.
- Standardized backtest runner producing HTML reports and metrics.
- CI-enforced acceptance gates for strategy approval.
- Observability endpoints (`/health`, `/metrics`) per module.

## Success Criteria
- All modules report health within < 2 min of status change.
- Live risk panel reflects exposure, drawdown, daily PnL vs limits in real time.
- Strategy deployment blocked if backtest fails Sharpe/MaxDD/WinRate thresholds.
- 100% pass rate on E2E golden-case scenarios before deployment.
