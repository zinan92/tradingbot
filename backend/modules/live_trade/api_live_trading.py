"""
Live Trading API Router

Provides REST API endpoints for live trading operations following hexagonal architecture.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from decimal import Decimal
import logging

from backend.modules.live_trade.service_live_trading import (
    LiveTradingService,
    CreateSessionRequest,
    SignalRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live-trading", tags=["Live Trading"])

# Module-level service instance (would be injected in real implementation)
_live_trading_service: Optional[LiveTradingService] = None


def set_live_trading_service(service: LiveTradingService):
    """Set the live trading service instance"""
    global _live_trading_service
    _live_trading_service = service


class CreateSessionAPIRequest(BaseModel):
    """API request to create trading session"""
    strategy_name: str = Field(..., description="Name of trading strategy")
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    initial_balance: Decimal = Field(..., description="Initial balance for trading")
    risk_config: Optional[Dict[str, Any]] = Field(default=None, description="Risk management configuration")
    strategy_params: Optional[Dict[str, Any]] = Field(default=None, description="Strategy parameters")


class SignalAPIRequest(BaseModel):
    """API request to submit trading signal"""
    side: str = Field(..., description="Order side: BUY or SELL")
    quantity: Optional[Decimal] = Field(default=None, description="Order quantity")
    price: Optional[Decimal] = Field(default=None, description="Order price (for limit orders)")
    order_type: str = Field(default="MARKET", description="Order type: MARKET or LIMIT")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional signal metadata")


class SessionResponse(BaseModel):
    """Response model for session operations"""
    session_id: str
    status: str
    message: Optional[str] = None


class SessionStatusResponse(BaseModel):
    """Response model for session status"""
    session_id: str
    strategy_id: str
    portfolio_id: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    error_message: Optional[str] = None
    config: Dict[str, Any]


class PortfolioStatusResponse(BaseModel):
    """Response model for portfolio status"""
    portfolio_id: str
    total_balance: float
    available_balance: float
    unrealized_pnl: float
    realized_pnl: float
    open_positions: int
    pending_orders: int
    updated_at: str


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionAPIRequest):
    """
    Create a new live trading session
    """
    if not _live_trading_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live trading service not available"
        )
    
    try:
        service_request = CreateSessionRequest(
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            initial_balance=request.initial_balance,
            risk_config=request.risk_config,
            strategy_params=request.strategy_params
        )
        
        session_id = await _live_trading_service.create_trading_session(service_request)
        
        return SessionResponse(
            session_id=session_id,
            status="created",
            message=f"Created trading session for {request.strategy_name}"
        )
        
    except Exception as e:
        logger.error(f"Failed to create trading session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.post("/sessions/{session_id}/start", response_model=SessionResponse)
async def start_session(session_id: str):
    """
    Start a trading session
    """
    if not _live_trading_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live trading service not available"
        )
    
    try:
        success = await _live_trading_service.start_session(session_id)
        
        if success:
            return SessionResponse(
                session_id=session_id,
                status="started",
                message="Trading session started successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to start trading session"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}"
        )


@router.post("/sessions/{session_id}/stop", response_model=SessionResponse)
async def stop_session(session_id: str):
    """
    Stop a trading session
    """
    if not _live_trading_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live trading service not available"
        )
    
    try:
        success = await _live_trading_service.stop_session(session_id)
        
        if success:
            return SessionResponse(
                session_id=session_id,
                status="stopped",
                message="Trading session stopped successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to stop trading session"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop session: {str(e)}"
        )


@router.post("/sessions/{session_id}/signals")
async def submit_signal(session_id: str, request: SignalAPIRequest):
    """
    Submit a trading signal to a session
    """
    if not _live_trading_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live trading service not available"
        )
    
    try:
        service_request = SignalRequest(
            session_id=session_id,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            order_type=request.order_type,
            metadata=request.metadata
        )
        
        order_id = await _live_trading_service.submit_signal(service_request)
        
        return {
            "session_id": session_id,
            "order_id": order_id,
            "status": "submitted" if order_id else "rejected",
            "message": "Signal processed successfully" if order_id else "Signal was rejected"
        }
        
    except Exception as e:
        logger.error(f"Failed to submit signal to session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit signal: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """
    Get trading session status
    """
    if not _live_trading_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live trading service not available"
        )
    
    try:
        status_info = await _live_trading_service.get_session_status(session_id)
        
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trading session not found"
            )
        
        return SessionStatusResponse(**status_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session status: {str(e)}"
        )


@router.get("/sessions")
async def list_sessions():
    """
    List all trading sessions
    """
    if not _live_trading_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live trading service not available"
        )
    
    try:
        sessions = await _live_trading_service.list_sessions()
        return {"sessions": sessions}
        
    except Exception as e:
        logger.error(f"Failed to list sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}/portfolio", response_model=PortfolioStatusResponse)
async def get_portfolio_status(session_id: str):
    """
    Get portfolio status for a trading session
    """
    if not _live_trading_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live trading service not available"
        )
    
    try:
        portfolio_info = await _live_trading_service.get_portfolio_status(session_id)
        
        if not portfolio_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found for session"
            )
        
        return PortfolioStatusResponse(**portfolio_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get portfolio status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio status: {str(e)}"
        )


@router.post("/emergency-stop")
async def emergency_stop():
    """
    Emergency stop all trading sessions
    """
    if not _live_trading_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live trading service not available"
        )
    
    try:
        success = await _live_trading_service.emergency_stop()
        
        return {
            "status": "success" if success else "failed",
            "message": "Emergency stop completed" if success else "Emergency stop failed"
        }
        
    except Exception as e:
        logger.error(f"Emergency stop failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emergency stop failed: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for live trading service
    """
    if not _live_trading_service:
        return {
            "status": "unhealthy",
            "message": "Live trading service not available"
        }
    
    try:
        sessions = await _live_trading_service.list_sessions()
        running_sessions = [s for s in sessions if s['status'] == 'RUNNING']
        
        return {
            "status": "healthy",
            "total_sessions": len(sessions),
            "running_sessions": len(running_sessions),
            "timestamp": "2025-01-10T00:00:00Z"  # Would use actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}"
        }