"""
Backtest API Router

Provides REST API endpoints for running and managing backtests.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
import logging

from src.application.backtesting.commands.run_backtest_command import RunBacktestCommand
from src.application.backtesting.services.backtest_service import BacktestService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/backtests",
    tags=["backtesting"],
    responses={404: {"description": "Not found"}},
)

# Initialize service (in production, use dependency injection)
backtest_service = BacktestService()


# Request/Response DTOs
class RunBacktestRequest(BaseModel):
    """DTO for run backtest request"""
    strategy: str = Field(..., description="Strategy name (e.g., 'SmaCross')")
    symbol: str = Field(..., description="Trading symbol (e.g., 'BTCUSDT')")
    start_date: datetime = Field(..., description="Start date for backtest")
    end_date: datetime = Field(..., description="End date for backtest")
    initial_capital: float = Field(default=10000, gt=0, description="Starting capital")
    commission: float = Field(default=0.002, ge=0, le=1, description="Commission rate")
    interval: str = Field(default='1h', description="Data interval (1m, 5m, 1h, 1d)")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
    async_execution: bool = Field(default=False, description="Run asynchronously")
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "strategy": "SmaCross",
                "symbol": "BTCUSDT",
                "start_date": "2023-01-01T00:00:00",
                "end_date": "2023-12-31T23:59:59",
                "initial_capital": 10000,
                "commission": 0.002,
                "interval": "1h",
                "strategy_params": {
                    "n1": 10,
                    "n2": 20
                },
                "async_execution": False
            }
        }


class BacktestResponse(BaseModel):
    """DTO for backtest response"""
    job_id: UUID = Field(..., description="Backtest job ID")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Response message")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "running",
                "message": "Backtest started successfully"
            }
        }


class BacktestResultsResponse(BaseModel):
    """DTO for backtest results"""
    job_id: UUID
    status: str
    stats: Optional[Dict[str, Any]] = None
    trades: Optional[List[Dict[str, Any]]] = None
    chart_url: Optional[str] = None
    error: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "completed",
                "stats": {
                    "Return [%]": 25.42,
                    "Sharpe Ratio": 0.66,
                    "Max. Drawdown [%]": -33.08,
                    "# Trades": 93
                },
                "trades": [],
                "chart_url": "/api/v1/backtests/123e4567-e89b-12d3-a456-426614174000/chart"
            }
        }


class OptimizeStrategyRequest(BaseModel):
    """DTO for strategy optimization request"""
    strategy: str = Field(..., description="Strategy name")
    symbol: str = Field(..., description="Trading symbol")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    param_ranges: Dict[str, List[Any]] = Field(..., description="Parameter ranges to optimize")
    maximize: str = Field(default="Sharpe Ratio", description="Metric to maximize")
    
    class Config:
        schema_extra = {
            "example": {
                "strategy": "SmaCross",
                "symbol": "BTCUSDT",
                "start_date": "2023-01-01T00:00:00",
                "end_date": "2023-12-31T23:59:59",
                "param_ranges": {
                    "n1": [5, 10, 15, 20],
                    "n2": [20, 30, 40, 50]
                },
                "maximize": "Sharpe Ratio"
            }
        }


# Endpoints
@router.post("/run",
            response_model=BacktestResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Run a backtest",
            description="Execute a backtest with specified strategy and parameters")
async def run_backtest(request: RunBacktestRequest, background_tasks: BackgroundTasks):
    """
    Run a backtest
    
    This endpoint executes a backtest with the specified strategy and parameters.
    Can run synchronously or asynchronously based on the async_execution flag.
    """
    try:
        # Create command
        command = RunBacktestCommand(
            strategy_name=request.strategy,
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            commission=request.commission,
            interval=request.interval,
            strategy_params=request.strategy_params
        )
        
        if request.async_execution:
            # Run asynchronously
            job_id = await backtest_service.run_backtest_async(command)
            
            return BacktestResponse(
                job_id=job_id,
                status="running",
                message="Backtest started in background"
            )
        else:
            # Run synchronously
            job = backtest_service.run_backtest(command)
            
            return BacktestResponse(
                job_id=job.job_id,
                status=job.status,
                message="Backtest completed" if job.status == "completed" else f"Backtest failed: {job.error}"
            )
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{job_id}",
           response_model=BacktestResultsResponse,
           summary="Get backtest results",
           description="Retrieve results of a completed backtest")
async def get_backtest_results(job_id: UUID):
    """
    Get backtest results by job ID
    
    Returns the complete results including statistics, trades, and chart URL.
    """
    job = backtest_service.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest job {job_id} not found"
        )
    
    response = BacktestResultsResponse(
        job_id=job.job_id,
        status=job.status,
        error=job.error
    )
    
    if job.status == 'completed' and job.results:
        # Convert results to dictionary format
        results_dict = job.results.to_dict()
        response.stats = results_dict['stats']
        response.trades = results_dict['trades']
        response.chart_url = f"/api/v1/backtests/{job_id}/chart"
    
    return response


@router.get("/{job_id}/chart",
           response_class=HTMLResponse,
           summary="Get backtest chart",
           description="Retrieve interactive HTML chart for backtest")
async def get_backtest_chart(job_id: UUID):
    """
    Get interactive chart for backtest
    
    Returns an HTML page with the interactive backtest chart.
    """
    job = backtest_service.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest job {job_id} not found"
        )
    
    if job.status != 'completed' or not job.results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backtest not completed or no results available"
        )
    
    # Return the HTML chart
    return HTMLResponse(content=job.results.chart_html)


@router.get("/{job_id}/trades",
           summary="Get trade history",
           description="Retrieve detailed trade history from backtest")
async def get_backtest_trades(job_id: UUID):
    """
    Get trade history for a backtest
    
    Returns detailed information about all trades executed during the backtest.
    """
    job = backtest_service.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest job {job_id} not found"
        )
    
    if job.status != 'completed' or not job.results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backtest not completed or no results available"
        )
    
    # Get trades from results
    trades = job.results.trades
    
    if trades.empty:
        return {"trades": [], "total": 0}
    
    # Format trades for response
    from src.infrastructure.backtesting.results_formatter import ResultsFormatter
    formatter = ResultsFormatter()
    formatted_trades = formatter.format_trades_table(trades)
    
    return {
        "trades": formatted_trades.to_dict('records'),
        "total": len(formatted_trades)
    }


@router.get("/{job_id}/status",
           summary="Get backtest status",
           description="Check the status of a backtest job")
async def get_backtest_status(job_id: UUID):
    """
    Get the status of a backtest job
    
    Returns the current status and progress information.
    """
    job = backtest_service.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest job {job_id} not found"
        )
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error": job.error
    }


@router.get("/",
           summary="List backtest jobs",
           description="List all backtest jobs with optional status filter")
async def list_backtests(status: Optional[str] = None):
    """
    List all backtest jobs
    
    Returns a list of all backtest jobs, optionally filtered by status.
    """
    jobs = backtest_service.list_jobs(status=status)
    
    return {
        "jobs": [job.to_dict() for job in jobs],
        "total": len(jobs)
    }


@router.delete("/{job_id}",
              summary="Cancel backtest",
              description="Cancel a pending or running backtest")
async def cancel_backtest(job_id: UUID):
    """
    Cancel a backtest job
    
    Cancels a pending or running backtest. Completed backtests cannot be cancelled.
    """
    success = backtest_service.cancel_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not found or already completed"
        )
    
    return {
        "job_id": job_id,
        "status": "cancelled",
        "message": "Backtest cancelled successfully"
    }


@router.post("/optimize",
            summary="Optimize strategy parameters",
            description="Find optimal strategy parameters using grid search")
async def optimize_strategy(request: OptimizeStrategyRequest):
    """
    Optimize strategy parameters
    
    Performs parameter optimization to find the best strategy configuration.
    """
    try:
        # Convert list ranges to actual ranges
        param_ranges = {}
        for key, values in request.param_ranges.items():
            if isinstance(values, list) and len(values) == 3:
                # Assume [start, stop, step]
                param_ranges[key] = range(values[0], values[1], values[2])
            else:
                param_ranges[key] = values
        
        # Run optimization
        results = backtest_service.optimize_strategy(
            strategy_name=request.strategy,
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            param_ranges=param_ranges,
            maximize=request.maximize
        )
        
        return results
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error optimizing strategy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )