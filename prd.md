# Product Requirements Document (PRD)

## Overview
Enable operators and strategists to interactively control and observe the trading bot’s full lifecycle through a web UI, with embedded safety and performance gates.

## Users
- **Operator**: Monitors system, manages live strategies, responds to alerts.
- **Strategist**: Develops, tests, and deploys new strategies.

## Core User Stories & Acceptance Criteria

### Story 1 — Monitor Module Health
**As an** Operator  
**I want** to see the health of each module at a glance  
**So that** I can detect and address failures quickly.

**Acceptance Criteria:**
- Dashboard displays module name, status color, last update timestamp.
- Status turns red if health check fails or data latency exceeds 2 minutes.
- Clicking module opens detail view with logs, metrics, and recent events.

### Story 2 — Deploy Strategy with Risk Validation
**As a** Strategist  
**I want** to deploy a strategy only if it passes pre-trade risk checks  
**So that** live trades do not violate risk limits.

**Acceptance Criteria:**
- UI form to select strategy from registry, configure parameters, and choose account (testnet/paper/mainnet).
- Deployment blocked if: size > max, exposure > limit, daily loss % exceeded, leverage/margin invalid, correlation > limit.
- Risk validation result displayed in UI.

### Story 3 — Run and Review Backtest
**As a** Strategist  
**I want** to run a backtest and review standardized results  
**So that** I can decide if the strategy is worth deploying.

**Acceptance Criteria:**
- Backtest runner accepts symbol(s), timeframe, parameters.
- Outputs HTML report with Sharpe, Profit Factor, MaxDD, Win Rate, PnL curve, and trades list.
- Pass/fail shown in UI based on thresholds: Sharpe ≥ 1.0, MaxDD ≤ 20%, WinRate ≥ 40%.

### Story 4 — Emergency Stop
**As an** Operator  
**I want** to stop all live trading and close positions instantly  
**So that** I can protect capital during abnormal events.

**Acceptance Criteria:**
- "Emergency Stop" button cancels orders, closes positions, logs CRITICAL, and sets system state to locked.
- UI shows reason and timestamp.
- Action auditable in logs.

### Story 5 — Risk Panel & Alerts
**As an** Operator  
**I want** to see live exposure, drawdown, daily PnL vs limits  
**So that** I can respond to risks proactively.

**Acceptance Criteria:**
- Risk panel updates at least every 10 seconds.
- Alerts trigger when thresholds breached (color change + notification).
- CSV export of current positions, PnL, and risk stats.

## Constraints & Assumptions
- Backend follows Ports & Adapters architecture.
- Observability endpoints implemented for all modules.
- UI built on React + Tailwind + shadcn components.
- CI/CD runs acceptance backtest tests before deploy.

## Dependencies
- Market data provider (Binance).
- Postgres for persistence.
- Event bus for intra-module messaging.
