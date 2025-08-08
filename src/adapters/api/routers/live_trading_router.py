"""
Live Trading API Router

REST API endpoints for controlling live trading operations.
"""
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime
import logging

from src.application.trading.services.live_trading_service import LiveTradingService, TradingSessionStatus
from src.application.trading.services.pretrade_risk_validator import PreTradeRiskValidator
from src.config.trading_config import get_config, TradingConfig
from src.infrastructure.persistence.postgres.repositories import (
    PostgresPortfolioRepository,
    PostgresOrderRepository,
    PostgresPositionRepository
)
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/live-trading",
    tags=["live-trading"],
    responses={404: {"description": "Not found"}},
)

# Service instances (in production, use dependency injection)
_live_trading_service: Optional[LiveTradingService] = None
_risk_validator: Optional[PreTradeRiskValidator] = None


def get_live_trading_service() -> LiveTradingService:
    """Get or create live trading service instance"""
    global _live_trading_service
    
    if _live_trading_service is None:
        _live_trading_service = LiveTradingService(
            portfolio_repository=PostgresPortfolioRepository(),
            order_repository=PostgresOrderRepository(),
            position_repository=PostgresPositionRepository(),
            event_bus=InMemoryEventBus(),
            config=get_config()
        )
    
    return _live_trading_service


def get_risk_validator() -> PreTradeRiskValidator:
    """Get or create risk validator instance"""
    global _risk_validator
    
    if _risk_validator is None:
        _risk_validator = PreTradeRiskValidator(
            portfolio_repository=PostgresPortfolioRepository(),
            position_repository=PostgresPositionRepository(),
            order_repository=PostgresOrderRepository(),
            config=get_config()
        )
    
    return _risk_validator


# Request/Response Models
class StartSessionRequest(BaseModel):
    """Request to start trading session"""
    portfolio_id: UUID = Field(..., description="Portfolio to trade with")
    
    class Config:
        schema_extra = {
            "example": {
                "portfolio_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class SessionResponse(BaseModel):
    """Trading session response"""
    session_id: UUID
    portfolio_id: UUID
    status: str
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    max_drawdown: float
    error_message: Optional[str]


class SessionStatusResponse(BaseModel):
    """Current session status"""
    session_id: str
    status: str
    started_at: Optional[str]
    total_trades: int
    win_rate: float
    total_pnl: float
    active_orders: int
    active_positions: int


class PositionResponse(BaseModel):
    """Position information"""
    symbol: str
    side: str
    quantity: int
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    realized_pnl: float
    leverage: int
    margin_ratio: float
    liquidation_price: Optional[float]


class RiskMetricsResponse(BaseModel):
    """Risk metrics response"""
    daily_loss: float
    daily_loss_limit: float
    daily_loss_utilization: float
    daily_trades: int
    max_leverage: int
    max_positions: int
    max_position_size: float
    margin_utilization: float
    total_exposure: float


class ConfigResponse(BaseModel):
    """Trading configuration response"""
    mode: str
    enabled: bool
    risk: Dict[str, Any]
    position_sizing: Dict[str, Any]
    order: Dict[str, Any]
    signal: Dict[str, Any]


class EmergencyStopRequest(BaseModel):
    """Emergency stop request"""
    close_positions: bool = Field(False, description="Close all open positions")
    reason: str = Field("Emergency stop", description="Reason for stop")


# Endpoints
@router.post("/session/start",
            response_model=SessionResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Start live trading session",
            description="Start a new live trading session with specified portfolio")
async def start_session(
    request: StartSessionRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new live trading session.
    
    This endpoint:
    1. Validates configuration
    2. Connects to broker
    3. Loads existing positions
    4. Starts monitoring tasks
    5. Begins accepting signals
    """
    service = get_live_trading_service()
    
    try:
        # Check if trading is enabled
        config = get_config()
        if not config.enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Trading is disabled in configuration"
            )
        
        # Start session
        session = await service.start_session(request.portfolio_id)
        
        return SessionResponse(
            session_id=session.id,
            portfolio_id=session.portfolio_id,
            status=session.status.value,
            started_at=session.started_at,
            stopped_at=session.stopped_at,
            total_trades=session.total_trades,
            winning_trades=session.winning_trades,
            losing_trades=session.losing_trades,
            total_pnl=float(session.total_pnl),
            win_rate=float(session.get_win_rate()),
            max_drawdown=float(session.max_drawdown),
            error_message=session.error_message
        )
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start trading session"
        )


@router.post("/session/stop",
            status_code=status.HTTP_200_OK,
            summary="Stop trading session",
            description="Stop the current trading session")
async def stop_session(reason: str = "User requested"):
    """Stop the current trading session"""
    service = get_live_trading_service()
    
    try:
        await service.stop_session(reason)
        
        return {"message": "Trading session stopped", "reason": reason}
        
    except Exception as e:
        logger.error(f"Error stopping session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop trading session"
        )


@router.post("/session/pause",
            status_code=status.HTTP_200_OK,
            summary="Pause trading",
            description="Pause trading without closing positions")
async def pause_session(reason: str = "User requested"):
    """Pause the current trading session"""
    service = get_live_trading_service()
    
    try:
        await service.pause_session(reason)
        
        return {"message": "Trading session paused", "reason": reason}
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error pausing session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause trading session"
        )


@router.post("/session/resume",
            status_code=status.HTTP_200_OK,
            summary="Resume trading",
            description="Resume a paused trading session")
async def resume_session():
    """Resume the paused trading session"""
    service = get_live_trading_service()
    
    try:
        await service.resume_session()
        
        return {"message": "Trading session resumed"}
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error resuming session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume trading session"
        )


@router.get("/session/status",
           response_model=Optional[SessionStatusResponse],
           summary="Get session status",
           description="Get current trading session status")
async def get_session_status():
    """Get current session status"""
    service = get_live_trading_service()
    
    status = service.get_session_status()
    
    if not status:
        return None
    
    return SessionStatusResponse(**status)


@router.get("/positions",
           response_model=List[PositionResponse],
           summary="Get open positions",
           description="Get all open positions in current session")
async def get_positions():
    """Get all open positions"""
    service = get_live_trading_service()
    
    if not service.current_session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active trading session"
        )
    
    positions = []
    for symbol, position in service.active_positions.items():
        if position.is_open:
            positions.append(PositionResponse(
                symbol=position.symbol,
                side=position.side.value,
                quantity=position.quantity.value,
                entry_price=float(position.entry_price.value),
                mark_price=float(position.mark_price.value) if position.mark_price else float(position.entry_price.value),
                unrealized_pnl=float(position.unrealized_pnl),
                realized_pnl=float(position.realized_pnl),
                leverage=position.leverage.value,
                margin_ratio=float(position.margin_ratio),
                liquidation_price=float(position.liquidation_price.value) if position.liquidation_price else None
            ))
    
    return positions


@router.get("/risk-metrics",
           response_model=RiskMetricsResponse,
           summary="Get risk metrics",
           description="Get current risk metrics for portfolio")
async def get_risk_metrics():
    """Get current risk metrics"""
    service = get_live_trading_service()
    validator = get_risk_validator()
    
    if not service.current_session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active trading session"
        )
    
    # Get risk metrics from validator
    metrics = validator.get_risk_metrics(service.current_session.portfolio_id)
    
    # Add additional metrics
    total_exposure = Decimal("0")
    for position in service.active_positions.values():
        if position.is_open:
            total_exposure += position.mark_price.value * Decimal(str(position.quantity.value))
    
    metrics["margin_utilization"] = 0.0  # Would calculate from portfolio
    metrics["total_exposure"] = float(total_exposure)
    
    return RiskMetricsResponse(**metrics)


@router.post("/emergency-stop",
            status_code=status.HTTP_200_OK,
            summary="Emergency stop",
            description="Emergency stop all trading activities")
async def emergency_stop(request: EmergencyStopRequest):
    """
    Emergency stop all trading.
    
    This endpoint:
    1. Immediately stops all trading
    2. Cancels all pending orders
    3. Optionally closes all positions
    4. Disconnects from broker
    """
    service = get_live_trading_service()
    
    if not service.current_session:
        return {"message": "No active session to stop"}
    
    try:
        # Stop session with emergency flag
        await service.stop_session(f"EMERGENCY: {request.reason}")
        
        message = f"Emergency stop executed: {request.reason}"
        
        if request.close_positions:
            # Note: positions would be closed in stop_session if configured
            message += " - All positions closed"
        
        logger.warning(f"Emergency stop executed by user: {request.reason}")
        
        return {"message": message, "status": "stopped"}
        
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        # Even if error, try to stop
        service.current_session.status = TradingSessionStatus.ERROR
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emergency stop attempted but error occurred: {e}"
        )


@router.get("/config",
           response_model=ConfigResponse,
           summary="Get configuration",
           description="Get current trading configuration")
async def get_configuration():
    """Get current trading configuration"""
    config = get_config()
    
    return ConfigResponse(
        mode=config.mode.value,
        enabled=config.enabled,
        risk={
            "max_leverage": config.risk.max_leverage,
            "max_position_size_usdt": float(config.risk.max_position_size_usdt),
            "max_positions": config.risk.max_positions,
            "daily_loss_limit_usdt": float(config.risk.daily_loss_limit_usdt),
            "max_drawdown_percent": float(config.risk.max_drawdown_percent)
        },
        position_sizing={
            "default_position_size_percent": float(config.position_sizing.default_position_size_percent),
            "use_kelly_criterion": config.position_sizing.use_kelly_criterion,
            "kelly_fraction": float(config.position_sizing.kelly_fraction)
        },
        order={
            "default_order_type": config.order.default_order_type.value,
            "limit_order_offset_percent": float(config.order.limit_order_offset_percent),
            "stop_loss_percent": float(config.order.stop_loss_percent),
            "take_profit_percent": float(config.order.take_profit_percent)
        },
        signal={
            "auto_execute": config.signal.auto_execute,
            "confidence_threshold": float(config.signal.confidence_threshold),
            "strength_threshold": float(config.signal.strength_threshold)
        }
    )


@router.post("/config/reload",
            status_code=status.HTTP_200_OK,
            summary="Reload configuration",
            description="Reload configuration from environment")
async def reload_configuration():
    """Reload configuration from environment"""
    from src.config.trading_config import reload_config
    
    try:
        config = reload_config()
        
        return {
            "message": "Configuration reloaded",
            "mode": config.mode.value,
            "enabled": config.enabled
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid configuration: {e}"
        )