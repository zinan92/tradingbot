"""
Trading API Router

Handles all trading-related endpoints including order management,
portfolio operations, and market data.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from decimal import Decimal
import logging

from src.application.trading.commands.place_order_command import (
    PlaceOrderCommand,
    PlaceOrderCommandHandler,
    PortfolioNotFoundError,
)
from src.application.trading.commands.cancel_order_command import (
    CancelOrderCommand,
    CancelOrderCommandHandler,
    BrokerCancellationError,
)
from src.domain.trading.aggregates.order import CannotCancelFilledOrderError
from src.domain.trading.repositories import OrderNotFoundError
from src.infrastructure.persistence.in_memory import (
    InMemoryOrderRepository,
    InMemoryPortfolioRepository,
)
from src.infrastructure.brokers.mock_broker import MockBrokerService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/orders",
    tags=["trading"],
    responses={404: {"description": "Not found"}},
)

# Dependencies (in production, use dependency injection)
def get_repositories():
    """Get repository instances"""
    return {
        "portfolio_repo": InMemoryPortfolioRepository(),
        "order_repo": InMemoryOrderRepository(),
    }

def get_infrastructure():
    """Get infrastructure services"""
    return {
        "broker_service": MockBrokerService(
            simulate_delay=False,
            cancellation_success_rate=0.9
        ),
        "event_bus": InMemoryEventBus(),
    }

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


class CancelOrderRequest(BaseModel):
    """DTO for cancel order request"""
    reason: str = Field(..., min_length=1, description="Reason for cancellation")
    
    class Config:
        schema_extra = {
            "example": {
                "reason": "User requested cancellation"
            }
        }


class CancelOrderResponse(BaseModel):
    """DTO for cancel order response"""
    status: str = Field(..., description="Order status after cancellation")
    order_id: UUID = Field(..., description="Order ID")
    message: str = Field(..., description="Response message")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "cancelled",
                "order_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Order cancellation requested"
            }
        }


class OrderStatusResponse(BaseModel):
    """DTO for order status response"""
    id: UUID
    symbol: str
    quantity: int
    order_type: str
    price: Optional[Decimal]
    status: str
    broker_order_id: Optional[str]
    created_at: Optional[str]
    filled_at: Optional[str]
    cancelled_at: Optional[str]


# Endpoints
@router.post("/", 
            response_model=PlaceOrderResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Place a new order",
            description="Submit a new trading order to the market")
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
    repos = get_repositories()
    infra = get_infrastructure()
    
    handler = PlaceOrderCommandHandler(
        portfolio_repo=repos["portfolio_repo"],
        order_repo=repos["order_repo"],
        broker_service=infra["broker_service"],
        event_bus=infra["event_bus"]
    )
    
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
        order_id = handler.handle(command)
        
        return PlaceOrderResponse(
            order_id=order_id,
            status="success",
            message=f"Order placed successfully for {request.quantity} shares of {request.symbol}"
        )
        
    except PortfolioNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        if "Insufficient funds" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient funds: {str(e)}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error placing order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/{order_id}",
              response_model=CancelOrderResponse,
              status_code=status.HTTP_200_OK,
              summary="Cancel an order",
              description="Request cancellation of an existing order",
              responses={
                  200: {
                      "description": "Order cancellation requested",
                      "model": CancelOrderResponse
                  },
                  404: {
                      "description": "Order not found"
                  },
                  409: {
                      "description": "Order cannot be cancelled (already filled)"
                  },
                  500: {
                      "description": "Broker error"
                  }
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
    
    Args:
        order_id: UUID of the order to cancel
        request: Cancellation request with reason
        
    Returns:
        CancelOrderResponse with status and message
        
    Raises:
        404: Order not found
        409: Order cannot be cancelled (already filled)
        500: Broker error
    """
    repos = get_repositories()
    infra = get_infrastructure()
    
    handler = CancelOrderCommandHandler(
        order_repo=repos["order_repo"],
        broker_service=infra["broker_service"],
        event_bus=infra["event_bus"]
    )
    
    try:
        # Create command
        command = CancelOrderCommand(
            order_id=order_id,
            reason=request.reason,
            cancelled_by=None  # Could be extracted from auth context
        )
        
        # Execute command
        result = handler.handle(command)
        
        if result.success:
            return CancelOrderResponse(
                status="cancelled",
                order_id=order_id,
                message="Order cancellation requested"
            )
        else:
            # This shouldn't happen with current implementation
            # but included for completeness
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel order"
            )
            
    except OrderNotFoundError as e:
        logger.warning(f"Order {order_id} not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
        
    except CannotCancelFilledOrderError as e:
        logger.warning(f"Cannot cancel filled order {order_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order cannot be cancelled (already filled)"
        )
        
    except BrokerCancellationError as e:
        logger.error(f"Broker error cancelling order {order_id}: {str(e)}")
        # Note: Order is still cancelled in our system
        # but broker notification failed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Broker error: {str(e)}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error cancelling order {order_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{order_id}",
           response_model=OrderStatusResponse,
           summary="Get order status",
           description="Retrieve the current status and details of an order")
async def get_order(order_id: UUID):
    """
    Get order details by ID
    
    Args:
        order_id: UUID of the order
        
    Returns:
        OrderStatusResponse with order details
        
    Raises:
        404: Order not found
    """
    repos = get_repositories()
    order_repo = repos["order_repo"]
    
    order = order_repo.get(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    
    return OrderStatusResponse(
        id=order.id,
        symbol=order.symbol,
        quantity=order.quantity,
        order_type=order.order_type,
        price=order.price,
        status=order.status.value,
        broker_order_id=order.broker_order_id,
        created_at=order.created_at.isoformat() if order.created_at else None,
        filled_at=order.filled_at.isoformat() if order.filled_at else None,
        cancelled_at=order.cancelled_at.isoformat() if order.cancelled_at else None
    )


class FillOrderRequest(BaseModel):
    """DTO for fill order request"""
    fill_price: Optional[Decimal] = Field(None, gt=0, description="Fill price (optional, will use market price if not provided)")
    
    class Config:
        schema_extra = {
            "example": {
                "fill_price": 150.50
            }
        }


class FillOrderResponse(BaseModel):
    """DTO for fill order response"""
    status: str
    message: str
    fill_price: Decimal
    
    class Config:
        schema_extra = {
            "example": {
                "status": "filled",
                "message": "Order filled successfully",
                "fill_price": 150.50
            }
        }


@router.post("/{order_id}/fill",
            response_model=FillOrderResponse,
            status_code=status.HTTP_200_OK,
            summary="Fill an order (Testing)",
            description="Manually trigger order fill for testing purposes",
            responses={
                200: {
                    "description": "Order filled successfully",
                    "model": FillOrderResponse
                },
                404: {
                    "description": "Order not found"
                },
                409: {
                    "description": "Order cannot be filled (not pending)"
                }
            })
async def fill_order(order_id: UUID, request: FillOrderRequest):
    """
    Fill an order (for testing/simulation)
    
    This endpoint simulates broker order execution for testing.
    It triggers the complete fill flow:
    1. Marks order as filled in broker
    2. Publishes OrderFilled event
    3. Updates portfolio positions
    4. Adjusts portfolio cash
    
    Args:
        order_id: UUID of the order to fill
        request: Fill request with optional price
        
    Returns:
        FillOrderResponse with status and fill price
        
    Raises:
        404: Order not found
        409: Order cannot be filled
    """
    repos = get_repositories()
    infra = get_infrastructure()
    
    # Get the order
    order = repos["order_repo"].get(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    
    # Check if order can be filled
    if not order.is_pending():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order cannot be filled (status: {order.status.value})"
        )
    
    # Check if order has a broker ID
    if not order.broker_order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has not been submitted to broker yet"
        )
    
    # Trigger fill in broker
    broker = infra["broker_service"]
    fill_price = float(request.fill_price) if request.fill_price else None
    
    success = broker.fill_order(order.broker_order_id, fill_price)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fill order in broker"
        )
    
    # The broker will publish OrderFilled event, which will be handled
    # by OrderFilledEventHandler to update portfolio
    
    # Get the actual fill price from broker
    if fill_price is None:
        # If no price provided, broker used a random/market price
        # We can get it from the broker's orders dict
        broker_data = broker.orders.get(order.broker_order_id, {})
        fill_price = broker_data.get("fill_price", 100.0)
    
    return FillOrderResponse(
        status="filled",
        message=f"Order filled: {order.quantity} shares of {order.symbol} @ ${fill_price}",
        fill_price=Decimal(str(fill_price))
    )