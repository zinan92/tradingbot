from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

from src.application.trading.commands.place_order_command import (
    PlaceOrderCommand,
    PlaceOrderCommandHandler,
    PortfolioNotFoundError,
)
from src.application.trading.commands.cancel_order_command import (
    CancelOrderCommand,
    CancelOrderCommandHandler,
    CancelOrderResult,
    BrokerCancellationError,
)
from src.application.trading.events.order_filled_handler import OrderFilledEventHandler
from src.domain.trading.aggregates.order import CannotCancelFilledOrderError
from src.domain.trading.repositories import OrderNotFoundError
from src.infrastructure.persistence.in_memory import (
    InMemoryOrderRepository,
    InMemoryPortfolioRepository,
)
try:
    from src.infrastructure.persistence.postgres.repositories import (
        PostgresPortfolioRepository,
        PostgresPositionRepository,
    )
    from src.infrastructure.persistence.postgres.repositories.order_repository import (
        PostgresOrderRepository
    )
except ImportError:
    # Fallback if postgres is not configured
    PostgresOrderRepository = None
    PostgresPortfolioRepository = None
    PostgresPositionRepository = None
from src.infrastructure.brokers.mock_broker import MockBrokerService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from src.application.trading.services.live_trading_service import LiveTradingService
from src.application.trading.services.state_recovery_service import StateRecoveryService
from src.application.trading.services.strategy_bridge import StrategyBridge, OptimalGridStrategyLive
from src.config.trading_config import get_config
import os
from src.domain.trading.aggregates.portfolio import Portfolio

# Import routers
from src.adapters.api.routers import trading_router, backtest_router
from src.adapters.api.routers.live_trading_router import router as live_trading_router
from src.adapters.api.health_router import router as health_router
from src.adapters.api.metrics_router import router as metrics_router
from src.adapters.api.risk_router import router as risk_router

# Create FastAPI app
app = FastAPI(
    title="Quantitative Trading System",
    description="DDD-based trading system with hexagonal architecture",
    version="1.0.0"
)

# Include routers
app.include_router(trading_router)
app.include_router(backtest_router)
app.include_router(live_trading_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(risk_router)

# Initialize infrastructure based on environment
use_postgres = os.getenv("USE_POSTGRES", "false").lower() == "true"

if use_postgres:
    # Use PostgreSQL repositories for production
    portfolio_repo = PostgresPortfolioRepository()
    order_repo = PostgresOrderRepository()
    position_repo = PostgresPositionRepository()
else:
    # Use in-memory repositories for development
    portfolio_repo = InMemoryPortfolioRepository()
    order_repo = InMemoryOrderRepository()
    position_repo = None  # In-memory doesn't have separate position repo
event_bus = InMemoryEventBus()
# Configure broker with 90% cancellation success rate for realistic testing
broker_service = MockBrokerService(
    simulate_delay=False,  # Disable delay for API (enable for async testing)
    cancellation_success_rate=0.9,
    event_bus=event_bus
)

# Create command handlers
place_order_handler = PlaceOrderCommandHandler(
    portfolio_repo=portfolio_repo,
    order_repo=order_repo,
    broker_service=broker_service,
    event_bus=event_bus
)

cancel_order_handler = CancelOrderCommandHandler(
    order_repo=order_repo,
    broker_service=broker_service,
    event_bus=event_bus
)

# Create event handlers
order_filled_handler = OrderFilledEventHandler(
    order_repo=order_repo,
    portfolio_repo=portfolio_repo
)

# Subscribe event handlers to events
event_bus.subscribe("order.filled", order_filled_handler.handle)


# Request/Response DTOs
class PlaceOrderRequest(BaseModel):
    """DTO for place order request"""
    portfolio_id: UUID = Field(..., description="Portfolio ID")
    symbol: str = Field(..., min_length=1, max_length=5, description="Trading symbol")
    quantity: int = Field(..., gt=0, description="Number of shares")
    order_type: str = Field(..., pattern="^(MARKET|LIMIT)$", description="Order type")
    price: Optional[Decimal] = Field(None, gt=0, description="Limit price (required for LIMIT orders)")
    
    class Config:
        schema_extra = {
            "example": {
                "portfolio_id": "123e4567-e89b-12d3-a456-426614174000",
                "symbol": "AAPL",
                "quantity": 10,
                "order_type": "MARKET",
                "price": None
            }
        }


class PlaceOrderResponse(BaseModel):
    """DTO for place order response"""
    order_id: UUID
    status: str
    message: str
    
    class Config:
        schema_extra = {
            "example": {
                "order_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "success",
                "message": "Order placed successfully"
            }
        }


class PortfolioResponse(BaseModel):
    """DTO for portfolio response"""
    id: UUID
    name: str
    available_cash: Decimal
    reserved_cash: Decimal
    currency: str
    total_value: Decimal


class CancelOrderRequest(BaseModel):
    """DTO for cancel order request"""
    reason: Optional[str] = Field(None, description="Reason for cancellation")
    cancelled_by: Optional[UUID] = Field(None, description="User ID who is cancelling")
    
    class Config:
        schema_extra = {
            "example": {
                "reason": "User requested cancellation",
                "cancelled_by": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class CancelOrderResponse(BaseModel):
    """DTO for cancel order response"""
    success: bool
    order_id: UUID
    message: str
    cancelled_at: Optional[str]
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "order_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Order cancelled successfully",
                "cancelled_at": "2024-01-15T10:30:00"
            }
        }


class ErrorResponse(BaseModel):
    """DTO for error response"""
    error: str
    detail: str
    
    class Config:
        schema_extra = {
            "example": {
                "error": "ValidationError",
                "detail": "Invalid order parameters"
            }
        }


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Quantitative Trading System API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post("/api/v1/orders", 
         response_model=PlaceOrderResponse,
         responses={
             400: {"model": ErrorResponse},
             404: {"model": ErrorResponse},
             500: {"model": ErrorResponse}
         })
async def place_order(request: PlaceOrderRequest):
    """
    Place a new trading order
    
    This endpoint handles the complete order placement flow:
    1. Validates the request
    2. Checks portfolio funds
    3. Creates the order
    4. Submits to broker
    5. Publishes domain events
    """
    try:
        # Create command from request
        command = PlaceOrderCommand(
            portfolio_id=request.portfolio_id,
            symbol=request.symbol,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price
        )
        
        # Execute command
        order_id = place_order_handler.handle(command)
        
        return PlaceOrderResponse(
            order_id=order_id,
            status="success",
            message=f"Order placed successfully for {request.quantity} shares of {request.symbol}"
        )
        
    except PortfolioNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "PortfolioNotFound", "detail": str(e)}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "ValidationError", "detail": str(e)}
        )
    except Exception as e:
        # Check if it's an insufficient funds error
        if "Insufficient funds" in str(e):
            raise HTTPException(
                status_code=400,
                detail={"error": "InsufficientFunds", "detail": str(e)}
            )
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalError", "detail": str(e)}
        )


@app.post("/api/v1/orders/{order_id}/cancel",
         response_model=CancelOrderResponse,
         responses={
             400: {"model": ErrorResponse},
             404: {"model": ErrorResponse},
             500: {"model": ErrorResponse}
         })
async def cancel_order(order_id: UUID, request: CancelOrderRequest):
    """
    Cancel an existing order
    
    This endpoint handles the order cancellation flow:
    1. Validates the order exists
    2. Checks if order can be cancelled (not filled)
    3. Cancels the order in the system
    4. Notifies the broker
    5. Publishes cancellation events
    """
    try:
        # Create command
        command = CancelOrderCommand(
            order_id=order_id,
            reason=request.reason,
            cancelled_by=request.cancelled_by
        )
        
        # Execute command
        result = cancel_order_handler.handle(command)
        
        return CancelOrderResponse(
            success=result.success,
            order_id=result.order_id,
            message=result.message,
            cancelled_at=result.cancelled_at
        )
        
    except OrderNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "OrderNotFound", "detail": str(e)}
        )
    except CannotCancelFilledOrderError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "CannotCancelFilledOrder", "detail": str(e)}
        )
    except BrokerCancellationError as e:
        # Note: Order is still cancelled in our system
        # Return success with a warning message
        return CancelOrderResponse(
            success=True,
            order_id=order_id,
            message=f"Order cancelled locally but broker notification failed: {str(e)}",
            cancelled_at=None
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "InternalError", "detail": str(e)}
        )


@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: UUID):
    """Get order details by ID"""
    order = order_repo.get(order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail={"error": "OrderNotFound", "detail": f"Order {order_id} not found"}
        )
    
    return {
        "id": order.id,
        "symbol": order.symbol,
        "quantity": order.quantity,
        "order_type": order.order_type,
        "price": order.price,
        "status": order.status.value,
        "broker_order_id": order.broker_order_id,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None
    }


@app.post("/api/v1/portfolios", response_model=PortfolioResponse)
async def create_portfolio(name: str, initial_cash: Decimal = Decimal("10000.00")):
    """Create a new portfolio"""
    portfolio = Portfolio.create(
        name=name,
        initial_cash=initial_cash,
        currency="USD"
    )
    portfolio_repo.save(portfolio)
    
    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        available_cash=portfolio.available_cash,
        reserved_cash=portfolio.reserved_cash,
        currency=portfolio.currency,
        total_value=portfolio.get_total_value()
    )


@app.get("/api/v1/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(portfolio_id: UUID):
    """Get portfolio details by ID"""
    portfolio = portfolio_repo.get(portfolio_id)
    if not portfolio:
        raise HTTPException(
            status_code=404,
            detail={"error": "PortfolioNotFound", "detail": f"Portfolio {portfolio_id} not found"}
        )
    
    return PortfolioResponse(
        id=portfolio.id,
        name=portfolio.name,
        available_cash=portfolio.available_cash,
        reserved_cash=portfolio.reserved_cash,
        currency=portfolio.currency,
        total_value=portfolio.get_total_value()
    )


@app.get("/api/v1/portfolios")
async def list_portfolios():
    """List all portfolios"""
    portfolios = portfolio_repo.get_all()
    return [
        PortfolioResponse(
            id=p.id,
            name=p.name,
            available_cash=p.available_cash,
            reserved_cash=p.reserved_cash,
            currency=p.currency,
            total_value=p.get_total_value()
        )
        for p in portfolios
    ]


# Global instances for live trading
live_trading_service: Optional[LiveTradingService] = None
state_recovery_service: Optional[StateRecoveryService] = None
strategy_bridge: Optional[StrategyBridge] = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global live_trading_service, state_recovery_service, strategy_bridge
    
    config = get_config()
    
    if config.enabled:
        # Initialize state recovery
        state_recovery_service = StateRecoveryService(
            state_dir="./trading_state",
            snapshot_interval_seconds=60,
            max_snapshots=100,
            retention_days=7
        )
        
        # Try to recover previous state
        recovered_state = await state_recovery_service.recover_state()
        
        if use_postgres and position_repo:
            # Initialize live trading service
            live_trading_service = LiveTradingService(
                portfolio_repository=portfolio_repo,
                order_repository=order_repo,
                position_repository=position_repo,
                event_bus=event_bus,
                config=config
            )
            
            # Initialize strategy bridge
            strategy_bridge = StrategyBridge(
                event_bus=event_bus,
                broker=None  # Will be set when session starts
            )
            
            # Add configured strategy (OptimalGridStrategy)
            if config.signal.auto_execute:
                # Get strategy parameters from config
                grid_config = {
                    'atr_period': int(os.getenv('GRID_ATR_PERIOD', '14')),
                    'grid_levels': int(os.getenv('GRID_LEVELS', '5')),
                    'atr_multiplier': float(os.getenv('GRID_ATR_MULTIPLIER', '1.0')),
                    'take_profit_pct': float(os.getenv('GRID_TAKE_PROFIT_PCT', '0.02')),
                    'stop_loss_pct': float(os.getenv('GRID_STOP_LOSS_PCT', '0.05'))
                }
                
                # Add strategy for configured symbols (default to BTCUSDT)
                symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
                for symbol in symbols:
                    strategy = OptimalGridStrategyLive(
                        symbol=symbol.strip(),
                        **grid_config
                    )
                    strategy_bridge.add_strategy(symbol.strip(), strategy)
            
            # If there was a recovered session, try to resume
            if recovered_state and recovered_state.session:
                if recovered_state.session.status.value == "RUNNING":
                    try:
                        await live_trading_service.start_session(
                            recovered_state.session.portfolio_id
                        )
                        logger.info("Resumed previous trading session")
                    except Exception as e:
                        logger.error(f"Failed to resume session: {e}")
        
        logger.info("Live trading services initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global live_trading_service, state_recovery_service, strategy_bridge
    
    if strategy_bridge:
        await strategy_bridge.stop()
    
    if live_trading_service and live_trading_service.current_session:
        # Save critical state before shutdown
        if state_recovery_service:
            await state_recovery_service.save_critical_state(
                session=live_trading_service.current_session,
                reason="Application shutdown",
                additional_data={
                    "active_orders": len(live_trading_service.active_orders),
                    "active_positions": len(live_trading_service.active_positions)
                }
            )
        
        # Stop trading session
        await live_trading_service.stop_session("Application shutdown")
    
    logger.info("Live trading services shut down")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_data = {
        "status": "healthy",
        "service": "trading-api",
        "repositories": {
            "portfolios": portfolio_repo.count() if hasattr(portfolio_repo, 'count') else "N/A",
            "orders": order_repo.count() if hasattr(order_repo, 'count') else "N/A"
        }
    }
    
    # Add live trading status if available
    if live_trading_service:
        status = live_trading_service.get_session_status()
        health_data["live_trading"] = status if status else {"status": "no_session"}
    
    return health_data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)