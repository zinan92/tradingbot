# Quantitative Trading System - DDD Project Brief for Claude Code

## Project Overview
We are building an automated trading system using Domain-Driven Design (DDD) principles and Hexagonal Architecture. The system executes trading strategies, manages risk, and monitors performance across financial markets. This is a learning project to properly implement DDD patterns.

## Architecture Principles

### Domain-Driven Design
- **Bounded Contexts**: Separate business domains with clear boundaries
- **Aggregates**: Clusters of objects that maintain consistency
- **Value Objects**: Immutable objects without identity
- **Domain Events**: Communication between contexts
- **Repository Pattern**: Abstractions for persistence

### Hexagonal Architecture (Ports & Adapters)
- **Core (Center)**: Pure domain logic with no external dependencies
- **Ports**: Interfaces that define contracts
- **Adapters**: Implementations of external integrations
- **Dependency Rule**: Dependencies point inward (Infrastructure → Application → Domain)

## Bounded Contexts

### 1. Trading Context (Core Domain)
**Purpose**: Execute trades and manage portfolios
**Key Aggregates**:
- `Portfolio`: Manages positions and cash balance
- `Order`: Represents trading orders with lifecycle

### 2. Strategy Context (Core Domain)
**Purpose**: Generate trading signals and manage strategies
**Key Aggregates**:
- `Strategy`: Trading strategy configuration and lifecycle

### 3. Risk Context (Supporting Domain)
**Purpose**: Monitor and enforce risk limits
**Key Aggregates**:
- `RiskProfile`: Risk limits and metrics

### 4. Market Data Context (Generic Domain)
**Purpose**: Fetch and distribute market data
**Key Components**:
- Data fetchers and normalizers

## Folder Structure
```
quant-trading-system/
├── src/
│   ├── domain/                    # Pure business logic
│   │   ├── trading/
│   │   │   ├── aggregates/       # Order, Portfolio
│   │   │   ├── entities/         # Position
│   │   │   ├── value_objects/    # Money, Symbol
│   │   │   ├── events/           # OrderPlaced, OrderFilled
│   │   │   ├── repositories/     # Interfaces only
│   │   │   └── services/         # Domain services
│   │   ├── strategy/
│   │   └── risk/
│   ├── application/               # Use case orchestration
│   │   ├── trading/
│   │   │   ├── commands/         # PlaceOrderCommand
│   │   │   └── queries/          # GetPortfolioQuery
│   │   └── strategy/
│   ├── infrastructure/            # External implementations
│   │   ├── persistence/          # PostgreSQL repositories
│   │   ├── brokers/              # IB, Alpaca adapters
│   │   └── messaging/            # Event bus
│   └── adapters/                  # Entry points
│       ├── api/                   # FastAPI REST
│       └── websocket/             # Real-time feeds
└── tests/
```

## Development Approach: Outside-In

We follow an **outside-in** development approach:
1. Start with a use case (user story)
2. Write the command handler showing the complete flow
3. Build only the domain objects needed for that use case
4. Implement infrastructure last
5. Test each layer independently

## Technology Stack
- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy
- **Message Bus**: In-memory for MVP, Kafka later
- **Testing**: pytest
- **Validation**: Pydantic

## Key Design Patterns to Follow

### 1. Aggregate Pattern
```python
class Order:  # Aggregate Root
    def __init__(self, order_id: OrderId, symbol: Symbol, quantity: Quantity):
        self._id = order_id
        self._symbol = symbol
        self._quantity = quantity
        self._status = OrderStatus.PENDING
    
    def cancel(self) -> OrderCancelled:
        # Business rule enforcement
        if self._status == OrderStatus.FILLED:
            raise CannotCancelFilledOrder()
        self._status = OrderStatus.CANCELLED
        return OrderCancelled(self._id)
```

### 2. Value Object Pattern
```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)  # Immutable
class Money:
    amount: Decimal
    currency: str
    
    def add(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise CurrencyMismatchError()
        return Money(self.amount + other.amount, self.currency)
```

### 3. Repository Pattern
```python
from abc import ABC, abstractmethod

class IOrderRepository(ABC):  # Port (Interface)
    @abstractmethod
    def get(self, order_id: OrderId) -> Order:
        pass
    
    @abstractmethod
    def save(self, order: Order) -> None:
        pass
```

### 4. Command Handler Pattern
```python
class PlaceOrderCommandHandler:
    def __init__(self, 
                 portfolio_repo: IPortfolioRepository,
                 order_repo: IOrderRepository,
                 event_bus: IEventBus):
        self._portfolio_repo = portfolio_repo
        self._order_repo = order_repo
        self._event_bus = event_bus
    
    def handle(self, command: PlaceOrderCommand) -> OrderId:
        # Orchestrate the use case
        portfolio = self._portfolio_repo.get(command.portfolio_id)
        order = portfolio.place_order(command.symbol, command.quantity)
        self._order_repo.save(order)
        self._event_bus.publish(order.pull_events())
        return order.id
```

## Development Rules

### DO:
- Start with use cases, not database schemas
- Keep domain logic in aggregates
- Use value objects for concepts without identity
- Define repository interfaces in domain layer
- Implement repositories in infrastructure layer
- Use domain events for cross-context communication
- Write tests for domain logic first

### DON'T:
- Put business logic in command handlers (only orchestration)
- Use domain entities as API DTOs
- Let infrastructure concerns leak into domain
- Create anemic domain models (all data, no behavior)
- Skip value objects (use them liberally)
- Access child entities directly (go through aggregate root)

## First Use Case to Implement

**User Story**: "As a trader, I want to place a market order so that I can buy stocks"

**Acceptance Criteria**:
1. Trader can specify symbol and quantity
2. System checks portfolio has sufficient funds
3. Order is created with PENDING status
4. Order is saved to database
5. Order is sent to broker
6. OrderPlaced event is published

**Required Components**:
- Command: `PlaceOrderCommand`
- Command Handler: `PlaceOrderCommandHandler`
- Aggregates: `Order`, `Portfolio`
- Value Objects: `Money`, `Symbol`, `Quantity`, `OrderType`
- Event: `OrderPlaced`
- Repository Interfaces: `IOrderRepository`, `IPortfolioRepository`

## Getting Started Instructions

When implementing the first use case, follow this sequence:

1. **Create the command handler skeleton** showing the complete flow
2. **Identify required domain objects** from the handler
3. **Build domain objects** with business rules
4. **Define repository interfaces** in domain layer
5. **Implement repositories** in infrastructure layer
6. **Create API endpoint** in adapters layer
7. **Write tests** for each layer

## Success Metrics
- Clean separation between layers (domain has no external dependencies)
- All business rules enforced in aggregates
- 100% test coverage on domain logic
- Repository interfaces defined in domain, implemented in infrastructure
- Commands and queries properly separated

## Important Notes
- This is a learning project focused on proper DDD implementation
- Start simple with one use case, build incrementally
- Focus on modeling the domain correctly before optimization
- Use in-memory implementations for rapid prototyping
- Replace with real infrastructure incrementally