quant-trading-system/
├── src/
│   ├── domain/           
│   │   ├── trading/      # ✅ CORE DOMAIN - Your trading business logic
│   │   │   ├── aggregates/
│   │   │   │   ├── order.py          # Order rules
│   │   │   │   └── portfolio.py      # Portfolio rules
│   │   │   ├── entities/
│   │   │   │   └── position.py       # Position entity
│   │   │   ├── value_objects/
│   │   │   │   ├── money.py          
│   │   │   │   ├── symbol.py         
│   │   │   │   └── order_type.py     
│   │   │   ├── events/
│   │   │   │   └── order_events.py   # OrderPlaced, OrderFilled
│   │   │   └── repositories/
│   │   │       └── order_repository.py  # Interface only!
│   │   │
│   │   ├── strategy/     # ✅ CORE DOMAIN - Strategy logic
│   │   │   ├── aggregates/
│   │   │   │   └── strategy.py
│   │   │   └── services/
│   │   │       └── signal_generator.py
│   │   │
│   │   └── risk/         # ✅ CORE DOMAIN - Risk rules
│   │       ├── aggregates/
│   │       │   └── risk_profile.py
│   │       └── services/
│   │           └── position_sizer.py
│   │
│   ├── application/      # ✅ Use case orchestration
│   │   ├── trading/
│   │   │   └── commands/
│   │   │       ├── place_order_command.py
│   │   │       └── cancel_order_command.py
│   │   ├── strategy/
│   │   └── risk/
│   │
│   └── infrastructure/   
│       ├── brokers/      # ⚠️ ONLY EXTERNAL BROKER ADAPTERS
│       │   ├── ccxt_adapter.py      # HOW to talk to crypto exchanges
│       │   ├── ib_adapter.py        # HOW to talk to Interactive Brokers
│       │   └── alpaca_adapter.py    # HOW to talk to Alpaca
│       │
│       ├── market_data/  
│       │   ├── yfinance_adapter.py
│       │   └── polygon_adapter.py
│       │
│       ├── indicators/   
│       │   └── talib_adapter.py
│       │
│       └── backtesting/  
│           └── backtesting_py_adapter.py


┌──────────────────────────────────────────────────┐
│                   API Layer                       │
│              FastAPI / WebSocket                  │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────┐
│              Application Layer                    │
│        Command Handlers / Query Handlers          │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────┐
│                Domain Layer                       │
│   Strategy (Core)  │  Risk (Core)  │  Trading    │
│   - Custom Logic   │  - Risk Rules │  - Order     │
│   - Your IP        │  - Limits     │  - Portfolio │
└──────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────┐
│            Infrastructure Layer                   │
│  ┌────────────────────────────────────────────┐  │
│  │ Libraries as Adapters:                     │  │
│  │ - CCXT (Brokers)                          │  │
│  │ - backtesting.py (Backtesting)            │  │
│  │ - yfinance (Market Data)                  │  │
│  │ - TA-Lib (Indicators)                     │  │
│  │ - PostgreSQL (Persistence)                │  │
│  │ - Redis (Cache)                           │  │
│  │ - Kafka (Messaging)                       │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘