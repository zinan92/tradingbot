"""
Backtest Contracts

Pydantic models for backtest-related data transfer objects.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class BacktestInput(BaseModel):
    """Backtest input configuration"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    strategy_name: str = Field(..., description="Strategy name or identifier")
    strategy_config: Dict[str, Any] = Field(..., description="Strategy configuration parameters")
    symbol: str = Field(..., description="Trading pair symbol")
    interval: str = Field("1h", description="Data interval (1m, 5m, 1h, 1d, etc.)")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_capital: Decimal = Field(..., gt=0, description="Starting capital")
    commission: Decimal = Field(Decimal("0.001"), description="Trading commission rate")
    slippage: Decimal = Field(Decimal("0.0001"), description="Slippage rate")
    leverage: Decimal = Field(Decimal("1"), ge=1, description="Maximum leverage")
    position_sizing: str = Field("fixed", description="Position sizing method")
    risk_per_trade: Optional[Decimal] = Field(None, description="Risk per trade (for risk-based sizing)")
    max_positions: int = Field(1, ge=1, description="Maximum concurrent positions")
    use_stops: bool = Field(True, description="Enable stop-loss orders")
    use_limits: bool = Field(True, description="Enable take-profit orders")
    reinvest_profits: bool = Field(False, description="Reinvest profits in position sizing")


class BacktestMetrics(BaseModel):
    """Backtest performance metrics"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Returns
    total_return: Decimal = Field(..., description="Total return percentage")
    annualized_return: Decimal = Field(..., description="Annualized return percentage")
    
    # Risk metrics
    max_drawdown: Decimal = Field(..., description="Maximum drawdown percentage")
    sharpe_ratio: Decimal = Field(..., description="Sharpe ratio")
    sortino_ratio: Optional[Decimal] = Field(None, description="Sortino ratio")
    calmar_ratio: Optional[Decimal] = Field(None, description="Calmar ratio")
    
    # Trade statistics
    total_trades: int = Field(..., description="Total number of trades")
    winning_trades: int = Field(..., description="Number of winning trades")
    losing_trades: int = Field(..., description="Number of losing trades")
    win_rate: Decimal = Field(..., description="Win rate percentage")
    avg_win: Decimal = Field(..., description="Average winning trade return")
    avg_loss: Decimal = Field(..., description="Average losing trade return")
    profit_factor: Decimal = Field(..., description="Profit factor")
    expectancy: Decimal = Field(..., description="Trade expectancy")
    
    # Portfolio metrics
    final_equity: Decimal = Field(..., description="Final portfolio value")
    peak_equity: Decimal = Field(..., description="Peak portfolio value")
    total_commission: Decimal = Field(..., description="Total commission paid")
    total_slippage: Decimal = Field(..., description="Total slippage cost")
    
    # Time metrics
    time_in_market: Decimal = Field(..., description="Percentage of time in market")
    avg_trade_duration: Optional[float] = Field(None, description="Average trade duration in hours")
    max_trade_duration: Optional[float] = Field(None, description="Maximum trade duration in hours")


class BacktestTrade(BaseModel):
    """Individual backtest trade record"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    trade_id: int = Field(..., description="Trade sequence number")
    symbol: str = Field(..., description="Trading pair symbol")
    side: str = Field(..., description="Trade side (buy/sell)")
    entry_time: datetime = Field(..., description="Entry timestamp")
    exit_time: Optional[datetime] = Field(None, description="Exit timestamp")
    entry_price: Decimal = Field(..., description="Entry price")
    exit_price: Optional[Decimal] = Field(None, description="Exit price")
    quantity: Decimal = Field(..., description="Trade quantity")
    pnl: Decimal = Field(..., description="Trade profit/loss")
    pnl_percentage: Decimal = Field(..., description="Trade profit/loss percentage")
    commission: Decimal = Field(..., description="Trade commission")
    slippage: Decimal = Field(..., description="Trade slippage")
    exit_reason: Optional[str] = Field(None, description="Trade exit reason")


class BacktestReport(BaseModel):
    """Complete backtest report"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    backtest_id: str = Field(..., description="Unique backtest identifier")
    input_config: BacktestInput = Field(..., description="Input configuration used")
    metrics: BacktestMetrics = Field(..., description="Performance metrics")
    trades: List[BacktestTrade] = Field(..., description="List of all trades")
    equity_curve: List[Dict[str, Any]] = Field(..., description="Equity curve data points")
    drawdown_curve: List[Dict[str, Any]] = Field(..., description="Drawdown curve data points")
    
    # Report outputs
    metrics_json: str = Field(..., description="Metrics as JSON string")
    equity_csv: str = Field(..., description="Equity curve as CSV string")
    trades_csv: str = Field(..., description="Trades log as CSV string")
    html_report: str = Field(..., description="HTML report content")
    
    # Metadata
    created_at: datetime = Field(..., description="Report creation timestamp")
    execution_time: float = Field(..., description="Backtest execution time in seconds")
    data_points: int = Field(..., description="Number of data points processed")
    warnings: List[str] = Field(default_factory=list, description="Any warnings generated")