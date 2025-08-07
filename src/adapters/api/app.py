from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from uuid import UUID

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
from src.infrastructure.brokers.mock_broker import MockBrokerService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from src.domain.trading.aggregates.portfolio import Portfolio

# Import routers
from src.adapters.api.routers import trading_router, backtest_router

# Create FastAPI app
app = FastAPI(
    title="Quantitative Trading System",
    description="DDD-based trading system with hexagonal architecture",
    version="1.0.0"
)

# Include routers
app.include_router(trading_router.router)
app.include_router(backtest_router.router)

# Initialize infrastructure (in production, use dependency injection)
portfolio_repo = InMemoryPortfolioRepository()
order_repo = InMemoryOrderRepository()
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


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "trading-api",
        "repositories": {
            "portfolios": portfolio_repo.count(),
            "orders": order_repo.count()
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)