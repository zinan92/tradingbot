# Quantitative Trading System - DDD Implementation

A Domain-Driven Design implementation of a quantitative trading system using hexagonal architecture.

## Architecture

This project follows Domain-Driven Design principles with:
- **Hexagonal Architecture** (Ports & Adapters)
- **Bounded Contexts** for separation of concerns
- **Aggregates** for business logic encapsulation
- **Value Objects** for immutable domain concepts
- **Repository Pattern** for persistence abstraction
- **Domain Events** for cross-boundary communication

## Project Structure

```
src/
├── domain/                 # Pure business logic (no dependencies)
│   └── trading/
│       ├── aggregates/    # Order, Portfolio
│       ├── value_objects/ # Money, Symbol
│       ├── events/        # OrderPlaced, OrderFilled
│       └── repositories/  # Repository interfaces (ports)
├── application/           # Use case orchestration
│   └── trading/
│       └── commands/      # PlaceOrderCommand & Handler
├── infrastructure/        # External implementations
│   ├── persistence/       # In-memory repositories
│   ├── brokers/          # Broker service
│   └── messaging/        # In-memory event bus
└── adapters/             # Entry points
    └── api/              # FastAPI REST endpoints
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the Application

```bash
# Start the API server
python run_api.py

# API will be available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

## API Usage

### 1. Create a Portfolio

```bash
curl -X POST "http://localhost:8000/api/v1/portfolios?name=MyPortfolio&initial_cash=10000" \
  -H "accept: application/json"
```

### 2. Place an Order

```bash
curl -X POST "http://localhost:8000/api/v1/orders" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": "YOUR_PORTFOLIO_ID",
    "symbol": "AAPL",
    "quantity": 10,
    "order_type": "MARKET"
  }'
```

### 3. Cancel an Order

```bash
curl -X POST "http://localhost:8000/api/v1/orders/YOUR_ORDER_ID/cancel" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "User requested cancellation"
  }'
```

### 4. Fill an Order (Testing/Simulation)

```bash
curl -X POST "http://localhost:8000/api/v1/orders/YOUR_ORDER_ID/fill" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "fill_price": 150.50
  }'
```

### 5. Get Order Status

```bash
curl -X GET "http://localhost:8000/api/v1/orders/YOUR_ORDER_ID" \
  -H "accept: application/json"
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/domain/test_order_aggregate.py
pytest tests/integration/test_place_order_use_case.py
```

## Key Design Patterns Implemented

### 1. Aggregate Pattern
- `Order` and `Portfolio` aggregates enforce business rules
- All modifications go through aggregate methods

### 2. Value Object Pattern
- `Money` and `Symbol` are immutable value objects
- Encapsulate validation and business logic

### 3. Repository Pattern
- Interfaces defined in domain layer
- Implementations in infrastructure layer

### 4. Command Handler Pattern
- `PlaceOrderCommandHandler` orchestrates the use case
- Keeps domain logic in aggregates

## Business Rules Enforced

1. **Order Rules**:
   - Cannot cancel filled orders
   - Cannot fill cancelled orders
   - Orders track their complete lifecycle (PENDING → FILLED/CANCELLED)
   - Broker confirmations tracked asynchronously

2. **Portfolio Rules**:
   - Cannot place orders without sufficient funds
   - Funds are reserved when orders are placed
   - Reserved funds are released when orders are cancelled
   - Positions are created when orders are filled
   - Cash is adjusted based on actual fill prices
   - Multiple orders for same symbol accumulate positions

## Next Steps

- [ ] Implement PostgreSQL repositories
- [ ] Add real broker integration (Interactive Brokers, Alpaca)
- [ ] Implement strategy context
- [ ] Add risk management context
- [ ] Implement event sourcing
- [ ] Add CQRS for read models
- [ ] Implement authentication/authorization
- [ ] Add WebSocket support for real-time updates