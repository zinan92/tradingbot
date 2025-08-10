"""
Live Trading API Router

Endpoints for managing live trading sessions including emergency stop.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
import logging

from src.application.trading.services.live_trading_service_refactored import (
    LiveTradingService,
    TradingSessionStatus
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/live", tags=["live-trading"])


class EmergencyStopRequest(BaseModel):
    """Request model for emergency stop"""
    reason: str
    close_positions: bool = True


class SessionResponse(BaseModel):
    """Response model for session status"""
    session_id: str
    status: str
    message: Optional[str] = None
    error: Optional[str] = None


# Dependency injection placeholder
async def get_trading_service() -> LiveTradingService:
    """Get the trading service instance"""
    # In a real implementation, this would be properly injected
    raise NotImplementedError("Dependency injection not configured")


@router.post("/emergency-stop", response_model=SessionResponse)
async def emergency_stop(
    request: EmergencyStopRequest,
    service: LiveTradingService = Depends(get_trading_service)
):
    """
    Trigger emergency stop - immediately halt all trading
    
    This will:
    1. Cancel all open orders
    2. Optionally close all positions
    3. Lock the trading session (requires manual unlock)
    4. Publish CRITICAL event
    
    Returns:
        Session status after emergency stop
    """
    try:
        logger.warning(f"Emergency stop requested: {request.reason}")
        
        # Execute emergency stop
        await service.emergency_stop(
            reason=request.reason,
            close_positions=request.close_positions
        )
        
        # Get current session status
        if service.current_session:
            return SessionResponse(
                session_id=str(service.current_session.id),
                status=service.current_session.status.value,
                message=f"Emergency stop executed: {request.reason}",
                error=service.current_session.error_message
            )
        else:
            return SessionResponse(
                session_id="none",
                status="NO_SESSION",
                message="No active session"
            )
            
    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unlock", response_model=SessionResponse)
async def unlock_session(
    service: LiveTradingService = Depends(get_trading_service)
):
    """
    Manually unlock a session after emergency stop
    
    Returns:
        Session status after unlock
    """
    try:
        success = await service.unlock_session()
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to unlock session - session may not be locked"
            )
        
        if service.current_session:
            return SessionResponse(
                session_id=str(service.current_session.id),
                status=service.current_session.status.value,
                message="Session unlocked successfully"
            )
        else:
            return SessionResponse(
                session_id="none",
                status="NO_SESSION",
                message="No active session"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unlock failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SessionResponse)
async def get_session_status(
    service: LiveTradingService = Depends(get_trading_service)
):
    """
    Get current trading session status
    
    Returns:
        Current session status
    """
    try:
        if service.current_session:
            return SessionResponse(
                session_id=str(service.current_session.id),
                status=service.current_session.status.value,
                error=service.current_session.error_message
            )
        else:
            return SessionResponse(
                session_id="none",
                status="NO_SESSION",
                message="No active trading session"
            )
            
    except Exception as e:
        logger.error(f"Failed to get session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start/{portfolio_id}")
async def start_session(
    portfolio_id: UUID,
    service: LiveTradingService = Depends(get_trading_service)
):
    """Start a new trading session"""
    try:
        # Check if session is locked
        if service.current_session and service.current_session.status == TradingSessionStatus.LOCKED:
            raise HTTPException(
                status_code=409,
                detail="Session is locked due to emergency stop. Unlock required."
            )
        
        session = await service.start_session(portfolio_id)
        
        return SessionResponse(
            session_id=str(session.id),
            status=session.status.value,
            message="Trading session started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_session(
    reason: str = "User requested",
    service: LiveTradingService = Depends(get_trading_service)
):
    """Stop the current trading session gracefully"""
    try:
        await service.stop_session(reason=reason)
        
        return SessionResponse(
            session_id=str(service.current_session.id) if service.current_session else "none",
            status=service.current_session.status.value if service.current_session else "STOPPED",
            message=f"Session stopped: {reason}"
        )
        
    except Exception as e:
        logger.error(f"Failed to stop session: {e}")
        raise HTTPException(status_code=500, detail=str(e))