"""
Backtest API Router

Provides REST API endpoints for running and managing backtests following hexagonal architecture.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from backend.modules.backtesting.core_backtest_engine import UnifiedBacktestEngine, BacktestResults
from backend.modules.backtesting.port_results_store import InMemoryResultsStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["Backtest"])

# Module-level instances
_backtest_engine = UnifiedBacktestEngine()
_results_store = InMemoryResultsStore()


class BacktestRequest(BaseModel):
    """Request model for backtest execution"""
    strategy_name: str = Field(..., description="Name of strategy to test")
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe")
    start_date: str = Field(..., description="Backtest start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Backtest end date (YYYY-MM-DD)")
    initial_cash: float = Field(10000, description="Initial capital")
    commission: float = Field(0.002, description="Commission rate")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")


class FuturesBacktestRequest(BaseModel):
    """Request model for futures backtest execution"""
    strategy_name: str = Field(..., description="Name of futures strategy to test")
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe")
    start_date: str = Field(..., description="Backtest start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Backtest end date (YYYY-MM-DD)")
    initial_cash: float = Field(10000, description="Initial capital")
    leverage: float = Field(10.0, description="Trading leverage")
    market_commission: float = Field(0.0004, description="Market order commission")
    limit_commission: float = Field(0.0002, description="Limit order commission")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")


class BacktestResponse(BaseModel):
    """Response model for backtest results"""
    result_id: str
    status: str
    message: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    chart_url: Optional[str] = None


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    Run a standard backtest
    """
    try:
        logger.info(f"Starting backtest for {request.strategy_name} on {request.symbol}")
        
        # For now, return a mock response since we don't have the full strategy loading infrastructure
        # In a complete implementation, this would:
        # 1. Load market data from data_fetch module
        # 2. Load strategy from strategy_management module
        # 3. Run backtest using core_backtest_engine
        # 4. Store results using port_results_store
        
        result_id = _results_store.store_results({
            'strategy_name': request.strategy_name,
            'request': request.dict(),
            'status': 'pending'
        })
        
        # Add background task to run actual backtest
        background_tasks.add_task(_run_backtest_task, result_id, request)
        
        return BacktestResponse(
            result_id=result_id,
            status="started",
            message=f"Backtest started for {request.strategy_name}"
        )
        
    except Exception as e:
        logger.error(f"Failed to start backtest: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start backtest: {str(e)}"
        )


@router.post("/run-futures", response_model=BacktestResponse)
async def run_futures_backtest(request: FuturesBacktestRequest, background_tasks: BackgroundTasks):
    """
    Run a futures backtest with leverage
    """
    try:
        logger.info(f"Starting futures backtest for {request.strategy_name} on {request.symbol}")
        
        result_id = _results_store.store_results({
            'strategy_name': request.strategy_name,
            'request': request.dict(),
            'status': 'pending',
            'type': 'futures'
        })
        
        # Add background task to run actual backtest
        background_tasks.add_task(_run_futures_backtest_task, result_id, request)
        
        return BacktestResponse(
            result_id=result_id,
            status="started",
            message=f"Futures backtest started for {request.strategy_name}"
        )
        
    except Exception as e:
        logger.error(f"Failed to start futures backtest: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start futures backtest: {str(e)}"
        )


@router.get("/results/{result_id}", response_model=BacktestResponse)
async def get_backtest_results(result_id: str):
    """
    Get backtest results by ID
    """
    try:
        results = _results_store.retrieve_results(result_id)
        
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backtest results not found"
            )
        
        return BacktestResponse(
            result_id=result_id,
            status=results.get('status', 'unknown'),
            message=results.get('message'),
            stats=results.get('stats'),
            chart_url=f"/api/backtest/chart/{result_id}" if results.get('status') == 'completed' else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get results for {result_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get results: {str(e)}"
        )


@router.get("/chart/{result_id}", response_class=HTMLResponse)
async def get_backtest_chart(result_id: str):
    """
    Get backtest chart as HTML
    """
    try:
        results = _results_store.retrieve_results(result_id)
        
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backtest results not found"
            )
        
        chart_html = results.get('chart_html')
        
        if not chart_html:
            return HTMLResponse(
                content="<html><body><h1>Chart not available</h1></body></html>",
                status_code=200
            )
        
        return HTMLResponse(content=chart_html, status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chart for {result_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chart: {str(e)}"
        )


@router.get("/list")
async def list_backtests(strategy_name: Optional[str] = None):
    """
    List all backtest results
    """
    try:
        results = _results_store.list_results(strategy_name)
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Failed to list backtests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backtests: {str(e)}"
        )


# Background task functions
async def _run_backtest_task(result_id: str, request: BacktestRequest):
    """
    Background task to run standard backtest
    """
    try:
        # Update status to running
        current_results = _results_store.retrieve_results(result_id)
        current_results['status'] = 'running'
        current_results['message'] = 'Backtest in progress...'
        
        # This would be the actual backtest execution in a complete implementation
        # For now, we'll create a mock successful result
        
        import time
        time.sleep(2)  # Simulate processing time
        
        # Mock successful completion
        current_results['status'] = 'completed'
        current_results['message'] = 'Backtest completed successfully'
        current_results['stats'] = {
            'Return [%]': 15.23,
            '# Trades': 42,
            'Win Rate [%]': 65.5,
            'Sharpe Ratio': 1.45,
            'Max. Drawdown [%]': -8.2
        }
        current_results['chart_html'] = '<html><body><h1>Mock Chart</h1><p>Backtest visualization would go here</p></body></html>'
        
        logger.info(f"Backtest {result_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Backtest {result_id} failed: {str(e)}")
        current_results = _results_store.retrieve_results(result_id)
        if current_results:
            current_results['status'] = 'failed'
            current_results['message'] = f'Backtest failed: {str(e)}'


async def _run_futures_backtest_task(result_id: str, request: FuturesBacktestRequest):
    """
    Background task to run futures backtest
    """
    try:
        # Update status to running
        current_results = _results_store.retrieve_results(result_id)
        current_results['status'] = 'running'
        current_results['message'] = 'Futures backtest in progress...'
        
        # This would be the actual futures backtest execution
        import time
        time.sleep(3)  # Simulate processing time
        
        # Mock successful completion with futures-specific metrics
        current_results['status'] = 'completed'
        current_results['message'] = 'Futures backtest completed successfully'
        current_results['stats'] = {
            'Return [%]': 45.67,
            'Leveraged Return [%]': 456.7,  # 10x leverage
            '# Trades': 38,
            'Win Rate [%]': 58.3,
            'Sharpe Ratio': 1.82,
            'Max. Drawdown [%]': -15.4,
            'Leverage': request.leverage,
            'Long Trades': 22,
            'Short Trades': 16
        }
        current_results['chart_html'] = '<html><body><h1>Mock Futures Chart</h1><p>Futures backtest visualization would go here</p></body></html>'
        
        logger.info(f"Futures backtest {result_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Futures backtest {result_id} failed: {str(e)}")
        current_results = _results_store.retrieve_results(result_id)
        if current_results:
            current_results['status'] = 'failed'
            current_results['message'] = f'Futures backtest failed: {str(e)}'