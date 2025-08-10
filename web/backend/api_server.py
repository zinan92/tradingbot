#!/usr/bin/env python3
"""
Trading Bot Web UI - Backend API Server
Provides REST API endpoints for the React frontend
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from decimal import Decimal
import json
import sys
import asyncio
from uuid import UUID

# Add parent directories to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.application.backtesting.services.backtest_service import BacktestService
from src.application.backtesting.commands.run_backtest_command import RunBacktestCommand

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Trading Bot API", version="1.0.0")

# Initialize backtest service
backtest_service = BacktestService()

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:3000"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'tradingbot'),
    'user': os.getenv('DB_USER', None),
    'password': os.getenv('DB_PASSWORD', None)
}

# Pydantic models for API responses
class Position(BaseModel):
    id: Optional[int]
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: Optional[float]
    pnl: Optional[float]
    pnl_percent: Optional[float]
    unrealized_pnl: Optional[float]
    status: str
    created_at: Optional[datetime]

class Trade(BaseModel):
    id: Optional[int]
    symbol: str
    side: str
    quantity: float
    price: float
    pnl: Optional[float]
    timestamp: datetime
    strategy: Optional[str]
    status: str

class Strategy(BaseModel):
    id: str
    name: str
    status: str
    total_pnl: float
    win_rate: float
    trades: int
    sharpe_ratio: Optional[float]

class PortfolioMetrics(BaseModel):
    total_balance: float
    daily_pnl: float
    total_trades: int
    win_rate: float
    open_positions: int
    total_pnl: float

class PerformanceData(BaseModel):
    date: str
    pnl: float
    cumulative_pnl: float
    trades: int
    win_rate: float

class BacktestResult(BaseModel):
    id: Optional[int]
    strategy: str
    symbol: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    profit_factor: float
    created_at: datetime

class BacktestConfig(BaseModel):
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float = 10000
    leverage: float = 1.0
    commission: float = 0.002
    interval: str = '1h'
    strategy_params: Optional[Dict[str, Any]] = None

class BacktestJobStatus(BaseModel):
    job_id: str
    status: str
    strategy: str
    symbol: str
    start_date: str
    end_date: str
    created_at: str
    completed_at: Optional[str]
    error: Optional[str]

class BacktestJobResult(BaseModel):
    job_id: str
    status: str
    results: Optional[Dict[str, Any]]
    stats: Optional[Dict[str, Any]]
    trades: Optional[List[Dict[str, Any]]]
    equity_curve: Optional[List[Dict[str, Any]]]

# Decimal JSON encoder
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# Database connection helper
def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg2.connect(**{k: v for k, v in DB_CONFIG.items() if v is not None})
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

# API Endpoints

@app.get("/")
def root():
    """Root endpoint"""
    return {"message": "Trading Bot API", "status": "running"}

@app.get("/api/positions", response_model=List[Position])
def get_positions():
    """Get all open positions"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id,
                    symbol,
                    side,
                    quantity,
                    entry_price,
                    current_price,
                    unrealized_pnl,
                    CASE 
                        WHEN entry_price > 0 THEN 
                            (unrealized_pnl / (quantity * entry_price)) * 100
                        ELSE 0 
                    END as pnl_percent,
                    status,
                    created_at
                FROM positions
                WHERE status = 'OPEN'
                ORDER BY created_at DESC
            """)
            positions = cur.fetchall()
            
            # Convert Decimal to float for JSON serialization
            for pos in positions:
                for key in ['quantity', 'entry_price', 'current_price', 'unrealized_pnl', 'pnl_percent']:
                    if key in pos and pos[key] is not None:
                        pos[key] = float(pos[key])
                pos['pnl'] = pos.get('unrealized_pnl', 0)
            
            return positions
    finally:
        conn.close()

@app.get("/api/trades", response_model=List[Trade])
def get_trades(limit: int = 50):
    """Get recent trades"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id,
                    symbol,
                    side,
                    quantity,
                    COALESCE(filled_price, price) as price,
                    status,
                    created_at as timestamp
                FROM orders
                WHERE status IN ('FILLED', 'PARTIALLY_FILLED')
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            trades = cur.fetchall()
            
            # Convert and add calculated fields
            for trade in trades:
                for key in ['quantity', 'price']:
                    if key in trade and trade[key] is not None:
                        trade[key] = float(trade[key])
                trade['pnl'] = 0  # Calculate from position close if available
                trade['strategy'] = 'Grid Trading'  # Default strategy
            
            return trades
    finally:
        conn.close()

@app.get("/api/strategies", response_model=List[Strategy])
def get_strategies():
    """Get strategy status and performance"""
    # For now, return mock data based on config
    # In production, this would query strategy performance tables
    strategies = [
        {
            "id": "1",
            "name": "Grid Trading",
            "status": "running",
            "total_pnl": 0,
            "win_rate": 0,
            "trades": 0,
            "sharpe_ratio": 0
        },
        {
            "id": "2", 
            "name": "Momentum",
            "status": "paused",
            "total_pnl": 0,
            "win_rate": 0,
            "trades": 0,
            "sharpe_ratio": 0
        }
    ]
    
    # Try to get real data from performance history
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get aggregated performance data
            cur.execute("""
                SELECT 
                    SUM(daily_pnl) as total_pnl,
                    AVG(win_rate) as win_rate,
                    SUM(total_trades) as trades
                FROM performance_history
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            """)
            perf = cur.fetchone()
            
            if perf and perf['total_pnl'] is not None:
                strategies[0]['total_pnl'] = float(perf['total_pnl'])
                strategies[0]['win_rate'] = float(perf['win_rate'] or 0)
                strategies[0]['trades'] = int(perf['trades'] or 0)
    except:
        pass  # Use mock data if query fails
    finally:
        conn.close()
    
    return strategies

@app.get("/api/portfolio", response_model=PortfolioMetrics)
def get_portfolio_metrics():
    """Get portfolio overview metrics"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get total balance (sum of position values)
            cur.execute("""
                SELECT 
                    SUM(quantity * COALESCE(current_price, entry_price)) as total_value,
                    SUM(unrealized_pnl) as total_unrealized_pnl,
                    COUNT(*) as open_positions
                FROM positions
                WHERE status = 'OPEN'
            """)
            portfolio = cur.fetchone()
            
            # Get today's P&L
            cur.execute("""
                SELECT 
                    COALESCE(SUM(daily_pnl), 0) as daily_pnl,
                    COALESCE(AVG(win_rate), 0) as win_rate,
                    COALESCE(SUM(total_trades), 0) as total_trades
                FROM performance_history
                WHERE date = CURRENT_DATE
            """)
            today = cur.fetchone()
            
            # Get total P&L for the month
            cur.execute("""
                SELECT COALESCE(SUM(daily_pnl), 0) as total_pnl
                FROM performance_history
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            """)
            month = cur.fetchone()
            
            return {
                "total_balance": float(portfolio['total_value'] or 10000),  # Default 10k
                "daily_pnl": float(today['daily_pnl'] if today else 0),
                "total_trades": int(today['total_trades'] if today else 0),
                "win_rate": float(today['win_rate'] if today else 0),
                "open_positions": int(portfolio['open_positions'] or 0),
                "total_pnl": float(month['total_pnl'] if month else 0)
            }
    finally:
        conn.close()

@app.get("/api/performance", response_model=List[PerformanceData])
def get_performance_history(days: int = 30):
    """Get historical performance data"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    date::text as date,
                    daily_pnl as pnl,
                    cumulative_pnl,
                    total_trades as trades,
                    win_rate
                FROM performance_history
                WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date ASC
            """, (days,))
            performance = cur.fetchall()
            
            # Convert Decimal to float
            for perf in performance:
                for key in ['pnl', 'cumulative_pnl', 'win_rate']:
                    if key in perf and perf[key] is not None:
                        perf[key] = float(perf[key])
            
            return performance
    finally:
        conn.close()

@app.get("/api/backtest", response_model=List[BacktestResult])
def get_backtest_results(limit: int = 10):
    """Get recent backtest results"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id,
                    strategy_name as strategy,
                    symbol,
                    total_return,
                    sharpe_ratio,
                    max_drawdown,
                    win_rate,
                    total_trades,
                    profit_factor,
                    created_at
                FROM backtest_results
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            results = cur.fetchall()
            
            # Convert Decimal to float
            for result in results:
                for key in ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'profit_factor']:
                    if key in result and result[key] is not None:
                        result[key] = float(result[key])
            
            return results
    except Exception as e:
        # Table might not exist yet, return empty list
        return []
    finally:
        conn.close()

@app.post("/api/strategies/{strategy_id}/toggle")
def toggle_strategy(strategy_id: str):
    """Toggle strategy status (start/stop)"""
    # This would integrate with your actual strategy management
    # For now, just return success
    return {"message": f"Strategy {strategy_id} toggled", "status": "success"}

@app.get("/api/risk-metrics")
def get_risk_metrics():
    """Get risk management metrics"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Calculate portfolio risk metrics
            cur.execute("""
                SELECT 
                    COUNT(*) as total_positions,
                    SUM(CASE WHEN side = 'LONG' THEN quantity * entry_price ELSE 0 END) as long_exposure,
                    SUM(CASE WHEN side = 'SHORT' THEN quantity * entry_price ELSE 0 END) as short_exposure,
                    MAX(unrealized_pnl) as max_profit,
                    MIN(unrealized_pnl) as max_loss
                FROM positions
                WHERE status = 'OPEN'
            """)
            risk = cur.fetchone()
            
            # Calculate historical metrics
            cur.execute("""
                SELECT 
                    MIN(cumulative_pnl) as max_drawdown,
                    STDDEV(daily_pnl) as volatility
                FROM performance_history
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            """)
            hist = cur.fetchone()
            
            total_exposure = float(risk['long_exposure'] or 0) + float(risk['short_exposure'] or 0)
            
            return {
                "var_95": float(hist['volatility'] or 0) * 1.65 if hist else 0,  # Simple VaR calculation
                "beta": 0.85,  # Mock value
                "alpha": 0.052,  # Mock value
                "correlation": 0.72,  # Mock value
                "long_exposure_pct": float(risk['long_exposure'] or 0) / total_exposure * 100 if total_exposure > 0 else 0,
                "short_exposure_pct": float(risk['short_exposure'] or 0) / total_exposure * 100 if total_exposure > 0 else 0,
                "max_drawdown": float(hist['max_drawdown'] or 0) if hist else 0,
                "volatility": float(hist['volatility'] or 0) if hist else 0
            }
    finally:
        conn.close()

@app.post("/api/backtest/run", response_model=BacktestJobStatus)
async def run_backtest(config: BacktestConfig):
    """Run a new backtest"""
    try:
        # Create backtest command
        command = RunBacktestCommand(
            strategy_name=config.strategy,
            symbol=config.symbol,
            start_date=datetime.fromisoformat(config.start_date),
            end_date=datetime.fromisoformat(config.end_date),
            initial_capital=config.initial_capital,
            commission=config.commission,
            interval=config.interval,
            strategy_params=config.strategy_params or {}
        )
        
        # Run backtest asynchronously
        job_id = await backtest_service.run_backtest_async(command)
        
        # Get job status
        job = backtest_service.get_job(job_id)
        
        return BacktestJobStatus(
            job_id=str(job_id),
            status=job.status,
            strategy=job.command.strategy_name,
            symbol=job.command.symbol,
            start_date=job.command.start_date.isoformat(),
            end_date=job.command.end_date.isoformat(),
            created_at=job.created_at.isoformat(),
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error=job.error
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/backtest/job/{job_id}", response_model=BacktestJobResult)
def get_backtest_job(job_id: str):
    """Get backtest job status and results"""
    try:
        job_uuid = UUID(job_id)
        job = backtest_service.get_job(job_uuid)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        result = BacktestJobResult(
            job_id=str(job.job_id),
            status=job.status,
            results=None,
            stats=None,
            trades=None,
            equity_curve=None
        )
        
        # If job is completed, include results
        if job.status == 'completed' and job.results:
            result.stats = job.results.stats
            
            # Extract trades if available
            if hasattr(job.results, 'trades') and job.results.trades is not None:
                result.trades = [
                    {
                        'entry_time': trade.get('EntryTime', ''),
                        'exit_time': trade.get('ExitTime', ''),
                        'entry_price': trade.get('EntryPrice', 0),
                        'exit_price': trade.get('ExitPrice', 0),
                        'size': trade.get('Size', 0),
                        'pnl': trade.get('PnL', 0),
                        'pnl_pct': trade.get('ReturnPct', 0),
                        'duration': trade.get('Duration', '')
                    }
                    for trade in job.results.trades.to_dict('records')
                ] if hasattr(job.results.trades, 'to_dict') else []
            
            # Extract equity curve if available
            if hasattr(job.results, 'equity_curve'):
                # This would need to be implemented based on actual data structure
                result.equity_curve = []
        
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/jobs", response_model=List[BacktestJobStatus])
def list_backtest_jobs(status: Optional[str] = None):
    """List all backtest jobs"""
    try:
        jobs = backtest_service.list_jobs(status)
        
        return [
            BacktestJobStatus(
                job_id=str(job.job_id),
                status=job.status,
                strategy=job.command.strategy_name,
                symbol=job.command.symbol,
                start_date=job.command.start_date.isoformat(),
                end_date=job.command.end_date.isoformat(),
                created_at=job.created_at.isoformat(),
                completed_at=job.completed_at.isoformat() if job.completed_at else None,
                error=job.error
            )
            for job in jobs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/backtest/job/{job_id}")
def cancel_backtest_job(job_id: str):
    """Cancel a running backtest job"""
    try:
        job_uuid = UUID(job_id)
        success = backtest_service.cancel_job(job_uuid)
        
        if not success:
            raise HTTPException(status_code=404, detail="Job not found or already completed")
        
        return {"message": "Job cancelled successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/strategies")
def get_available_strategies():
    """Get list of available backtest strategies"""
    strategies = [
        {
            "name": "SmaCross",
            "description": "Simple Moving Average Crossover",
            "parameters": {
                "fast_period": {"type": "int", "default": 10, "min": 5, "max": 50},
                "slow_period": {"type": "int", "default": 20, "min": 10, "max": 200}
            }
        },
        {
            "name": "EnhancedSmaCross",
            "description": "Enhanced SMA with volume filter",
            "parameters": {
                "fast_period": {"type": "int", "default": 10, "min": 5, "max": 50},
                "slow_period": {"type": "int", "default": 20, "min": 10, "max": 200},
                "volume_threshold": {"type": "float", "default": 1.5, "min": 1.0, "max": 3.0}
            }
        },
        {
            "name": "RSI",
            "description": "Relative Strength Index Strategy",
            "parameters": {
                "period": {"type": "int", "default": 14, "min": 5, "max": 30},
                "oversold": {"type": "int", "default": 30, "min": 20, "max": 40},
                "overbought": {"type": "int", "default": 70, "min": 60, "max": 80}
            }
        },
        {
            "name": "MACD",
            "description": "MACD Strategy",
            "parameters": {
                "fast_period": {"type": "int", "default": 12, "min": 5, "max": 20},
                "slow_period": {"type": "int", "default": 26, "min": 20, "max": 40},
                "signal_period": {"type": "int", "default": 9, "min": 5, "max": 15}
            }
        },
        {
            "name": "GridTrading",
            "description": "Grid Trading Strategy",
            "parameters": {
                "grid_levels": {"type": "int", "default": 10, "min": 5, "max": 20},
                "grid_spacing": {"type": "float", "default": 0.01, "min": 0.005, "max": 0.05}
            }
        }
    ]
    return strategies

@app.get("/api/backtest/symbols")
def get_available_symbols():
    """Get list of available symbols for backtesting"""
    symbols = [
        {"symbol": "BTCUSDT", "name": "Bitcoin/USDT"},
        {"symbol": "ETHUSDT", "name": "Ethereum/USDT"},
        {"symbol": "BNBUSDT", "name": "BNB/USDT"},
        {"symbol": "ADAUSDT", "name": "Cardano/USDT"},
        {"symbol": "DOGEUSDT", "name": "Dogecoin/USDT"},
        {"symbol": "XRPUSDT", "name": "Ripple/USDT"},
        {"symbol": "DOTUSDT", "name": "Polkadot/USDT"},
        {"symbol": "UNIUSDT", "name": "Uniswap/USDT"},
        {"symbol": "SOLUSDT", "name": "Solana/USDT"},
        {"symbol": "LINKUSDT", "name": "Chainlink/USDT"}
    ]
    return symbols

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except:
        return {"status": "unhealthy", "database": "disconnected"}

if __name__ == "__main__":
    import uvicorn
    print("Starting Trading Bot API Server...")
    print("API will be available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)