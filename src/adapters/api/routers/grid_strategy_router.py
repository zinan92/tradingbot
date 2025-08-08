"""
Grid Strategy API Router

REST API endpoints for grid strategy management.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

from src.application.strategy.commands.start_grid_strategy_command import (
    StartGridStrategyCommand,
    StartGridStrategyCommandHandler,
    StopGridStrategyCommand,
    StopGridStrategyCommandHandler,
    UpdateGridRegimeCommand,
    UpdateGridRegimeCommandHandler
)
from src.application.strategy.services.grid_strategy_service import GridStrategyService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from src.domain.strategy.regime.regime_manager import RegimeManager


# Create router
router = APIRouter(prefix="/api/grid", tags=["grid_strategy"])


# Request/Response models
class StartGridRequest(BaseModel):
    """Request to start a grid strategy."""
    symbol: str
    atr_multiplier: float = 0.75
    grid_levels: int = 5
    max_position_size: float = 0.1
    stop_loss_atr_multiplier: float = 2.0
    recalculation_threshold: float = 0.5


class StopGridRequest(BaseModel):
    """Request to stop a grid strategy."""
    strategy_id: str


class UpdateRegimeRequest(BaseModel):
    """Request to update market regime."""
    regime: str  # 'bullish', 'bearish', 'range', 'none'


class GridStrategyResponse(BaseModel):
    """Response for grid strategy operations."""
    success: bool
    message: str = ""
    data: Dict[str, Any] = {}


# Dependency injection
def get_grid_service():
    """Get grid strategy service instance."""
    # This should be properly configured with dependencies
    # For now, returning a placeholder
    return None


@router.post("/start", response_model=GridStrategyResponse)
async def start_grid_strategy(
    request: StartGridRequest,
    grid_service: GridStrategyService = Depends(get_grid_service)
):
    """
    Start a new grid trading strategy.
    
    Args:
        request: Start grid request with parameters
        grid_service: Grid strategy service
        
    Returns:
        GridStrategyResponse with strategy_id
    """
    try:
        # Create command
        command = StartGridStrategyCommand(
            symbol=request.symbol,
            atr_multiplier=request.atr_multiplier,
            grid_levels=request.grid_levels,
            max_position_size=request.max_position_size,
            stop_loss_atr_multiplier=request.stop_loss_atr_multiplier,
            recalculation_threshold=request.recalculation_threshold
        )
        
        # Handle command
        handler = StartGridStrategyCommandHandler(grid_service)
        result = await handler.handle(command)
        
        if result['success']:
            return GridStrategyResponse(
                success=True,
                message=result['message'],
                data={'strategy_id': result['strategy_id']}
            )
        else:
            raise HTTPException(status_code=400, detail=result['error'])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=GridStrategyResponse)
async def stop_grid_strategy(
    request: StopGridRequest,
    grid_service: GridStrategyService = Depends(get_grid_service)
):
    """
    Stop an active grid strategy.
    
    Args:
        request: Stop grid request with strategy_id
        grid_service: Grid strategy service
        
    Returns:
        GridStrategyResponse
    """
    try:
        # Create command
        command = StopGridStrategyCommand(strategy_id=request.strategy_id)
        
        # Handle command
        handler = StopGridStrategyCommandHandler(grid_service)
        result = await handler.handle(command)
        
        if result['success']:
            return GridStrategyResponse(
                success=True,
                message=result['message']
            )
        else:
            raise HTTPException(status_code=404, detail=result['error'])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/regime", response_model=GridStrategyResponse)
async def update_regime(
    request: UpdateRegimeRequest,
    grid_service: GridStrategyService = Depends(get_grid_service)
):
    """
    Update market regime for all grid strategies.
    
    Args:
        request: Update regime request
        grid_service: Grid strategy service
        
    Returns:
        GridStrategyResponse
    """
    try:
        # Validate regime
        valid_regimes = ['bullish', 'bearish', 'range', 'none']
        if request.regime not in valid_regimes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid regime. Must be one of: {valid_regimes}"
            )
        
        # Create command
        command = UpdateGridRegimeCommand(new_regime=request.regime)
        
        # Handle command
        handler = UpdateGridRegimeCommandHandler(grid_service)
        result = await handler.handle(command)
        
        if result['success']:
            return GridStrategyResponse(
                success=True,
                message=result['message']
            )
        else:
            raise HTTPException(status_code=400, detail=result['error'])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{strategy_id}", response_model=GridStrategyResponse)
async def get_strategy_status(
    strategy_id: str,
    grid_service: GridStrategyService = Depends(get_grid_service)
):
    """
    Get status of a specific grid strategy.
    
    Args:
        strategy_id: Strategy identifier
        grid_service: Grid strategy service
        
    Returns:
        GridStrategyResponse with strategy status
    """
    try:
        status = grid_service.get_strategy_status(strategy_id)
        
        if 'error' in status:
            raise HTTPException(status_code=404, detail=status['error'])
        
        return GridStrategyResponse(
            success=True,
            message="Strategy status retrieved",
            data=status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies", response_model=GridStrategyResponse)
async def list_strategies(
    grid_service: GridStrategyService = Depends(get_grid_service)
):
    """
    List all active grid strategies.
    
    Args:
        grid_service: Grid strategy service
        
    Returns:
        GridStrategyResponse with list of strategies
    """
    try:
        strategies = grid_service.get_all_strategies()
        
        return GridStrategyResponse(
            success=True,
            message=f"Found {len(strategies)} active strategies",
            data={'strategies': strategies}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime", response_model=GridStrategyResponse)
async def get_current_regime(
    grid_service: GridStrategyService = Depends(get_grid_service)
):
    """
    Get current market regime setting.
    
    Args:
        grid_service: Grid strategy service
        
    Returns:
        GridStrategyResponse with current regime
    """
    try:
        # Get regime from regime manager
        regime_info = grid_service.regime_manager.get_regime_info()
        
        return GridStrategyResponse(
            success=True,
            message="Current regime retrieved",
            data=regime_info
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/{strategy_id}")
async def strategy_websocket(websocket, strategy_id: str):
    """
    WebSocket endpoint for real-time strategy updates.
    
    Args:
        websocket: WebSocket connection
        strategy_id: Strategy to monitor
    """
    await websocket.accept()
    
    try:
        # TODO: Implement real-time strategy monitoring
        # Subscribe to strategy events and stream to websocket
        
        while True:
            # Send periodic updates
            await asyncio.sleep(1)
            
            # Get strategy status
            # Send to websocket
            pass
            
    except Exception as e:
        await websocket.close()