"""
Unified Backtest Service

Single entry point for all backtesting operations.
Handles strategy resolution, multi-symbol execution, and result aggregation.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from uuid import UUID, uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from src.domain.strategy.value_objects.strategy_configuration import (
    StrategyConfiguration,
    TradingMode
)
from src.infrastructure.strategy.strategy_registry import get_registry
from src.infrastructure.backtesting.backtest_engine import BacktestEngine, BacktestResults
from src.infrastructure.backtesting.futures_backtest_engine import (
    FuturesBacktestEngine, 
    FuturesBacktestResults
)
from src.infrastructure.backtesting.data_adapter import DataAdapter
# Repository import is optional - only if database is configured
try:
    from src.infrastructure.persistence.postgres.repositories.backtest_repository import (
        BacktestRepository
    )
except ImportError:
    BacktestRepository = None

logger = logging.getLogger(__name__)


@dataclass
class UnifiedBacktestRequest:
    """Request for unified backtest execution"""
    strategy_id: str
    symbols: List[str]
    start_time: datetime
    end_time: datetime
    initial_capital: float = 10000
    
    def validate(self) -> List[str]:
        """Validate the request"""
        errors = []
        
        if not self.strategy_id:
            errors.append("Strategy ID is required")
        
        if not self.symbols:
            errors.append("At least one symbol is required")
        
        if self.start_time >= self.end_time:
            errors.append("Start time must be before end time")
        
        if self.initial_capital <= 0:
            errors.append("Initial capital must be positive")
        
        return errors


@dataclass
class SymbolBacktestResult:
    """Result for a single symbol backtest"""
    symbol: str
    stats: pd.Series
    trades: pd.DataFrame
    equity_curve: pd.Series
    chart_html: Optional[str] = None
    futures_metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        if self.error:
            return {
                'symbol': self.symbol,
                'error': self.error
            }
        
        # Convert stats to dict
        stats_dict = {}
        for key, value in self.stats.items():
            if pd.isna(value):
                stats_dict[key] = None
            elif isinstance(value, (pd.Timestamp, datetime)):
                stats_dict[key] = value.isoformat()
            elif isinstance(value, pd.Timedelta):
                stats_dict[key] = str(value)
            else:
                stats_dict[key] = value
        
        return {
            'symbol': self.symbol,
            'stats': stats_dict,
            'trades_count': len(self.trades),
            'futures_metrics': self.futures_metrics
        }


@dataclass
class UnifiedBacktestResult:
    """Aggregated result for multi-symbol backtest"""
    job_id: UUID
    strategy_id: str
    strategy_name: str
    start_time: datetime
    end_time: datetime
    initial_capital: float
    
    # Results by symbol
    symbol_results: Dict[str, SymbolBacktestResult] = field(default_factory=dict)
    
    # Aggregated metrics
    portfolio_stats: Optional[Dict[str, Any]] = None
    portfolio_equity_curve: Optional[pd.Series] = None
    
    # Execution metadata
    execution_time_ms: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_symbol_result(self, symbol: str, result: SymbolBacktestResult):
        """Add a symbol result"""
        self.symbol_results[symbol] = result
    
    def calculate_portfolio_metrics(self):
        """Calculate aggregated portfolio metrics"""
        if not self.symbol_results:
            return
        
        # Collect metrics from all symbols
        total_return = 0
        total_trades = 0
        win_rates = []
        sharpe_ratios = []
        max_drawdowns = []
        
        for symbol, result in self.symbol_results.items():
            if result.error:
                continue
            
            stats = result.stats
            total_return += stats.get('Return [%]', 0)
            total_trades += stats.get('# Trades', 0)
            win_rates.append(stats.get('Win Rate [%]', 0))
            sharpe_ratios.append(stats.get('Sharpe Ratio', 0))
            max_drawdowns.append(stats.get('Max. Drawdown [%]', 0))
        
        # Calculate portfolio-level metrics
        num_symbols = len([r for r in self.symbol_results.values() if not r.error])
        
        if num_symbols > 0:
            self.portfolio_stats = {
                'total_symbols': len(self.symbol_results),
                'successful_symbols': num_symbols,
                'avg_return': total_return / num_symbols,
                'total_return': total_return,
                'total_trades': total_trades,
                'avg_win_rate': np.mean(win_rates) if win_rates else 0,
                'avg_sharpe_ratio': np.mean(sharpe_ratios) if sharpe_ratios else 0,
                'worst_drawdown': min(max_drawdowns) if max_drawdowns else 0,
                'best_performer': max(
                    [(s, r.stats.get('Return [%]', 0)) 
                     for s, r in self.symbol_results.items() if not r.error],
                    key=lambda x: x[1]
                )[0] if num_symbols > 0 else None
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            'job_id': str(self.job_id),
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'initial_capital': self.initial_capital,
            'symbol_results': {
                symbol: result.to_dict() 
                for symbol, result in self.symbol_results.items()
            },
            'portfolio_stats': self.portfolio_stats,
            'execution_time_ms': self.execution_time_ms,
            'created_at': self.created_at.isoformat()
        }


class UnifiedBacktestService:
    """
    Unified service for backtesting operations.
    
    Features:
    - Single interface for all strategy types
    - Multi-symbol parallel execution
    - Automatic engine selection (spot/futures)
    - Result aggregation and persistence
    """
    
    def __init__(self, 
                 max_workers: int = 4,
                 repository: Optional[Any] = None):
        """
        Initialize the unified backtest service.
        
        Args:
            max_workers: Maximum parallel workers for multi-symbol execution
            repository: Repository for persisting results
        """
        self.registry = get_registry()
        self.data_adapter = DataAdapter()
        self.backtest_engine = BacktestEngine()
        self.futures_engine = FuturesBacktestEngine()
        self.repository = repository
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_jobs: Dict[UUID, UnifiedBacktestResult] = {}
    
    async def run_backtest(self, request: UnifiedBacktestRequest) -> UnifiedBacktestResult:
        """
        Run a unified backtest.
        
        Args:
            request: Backtest request
        
        Returns:
            Unified backtest result
        
        Raises:
            ValueError: If request is invalid or strategy not found
        """
        # Validate request
        errors = request.validate()
        if errors:
            raise ValueError(f"Invalid request: {', '.join(errors)}")
        
        # Get strategy configuration
        config = self.registry.get(request.strategy_id)
        if not config:
            raise ValueError(f"Strategy '{request.strategy_id}' not found")
        
        # Get strategy class
        strategy_class = self.registry.get_strategy_class(config.class_name)
        if not strategy_class:
            raise ValueError(f"Strategy class '{config.class_name}' not found")
        
        logger.info(
            f"Starting unified backtest: {request.strategy_id} "
            f"for {len(request.symbols)} symbols"
        )
        
        # Create result container
        result = UnifiedBacktestResult(
            job_id=uuid4(),
            strategy_id=request.strategy_id,
            strategy_name=config.strategy_id.name,
            start_time=request.start_time,
            end_time=request.end_time,
            initial_capital=request.initial_capital
        )
        
        # Store active job
        self._active_jobs[result.job_id] = result
        
        # Track execution time
        start_execution = datetime.utcnow()
        
        try:
            # Run backtests for all symbols
            if len(request.symbols) == 1:
                # Single symbol - run synchronously
                symbol_result = await self._run_symbol_backtest(
                    symbol=request.symbols[0],
                    config=config,
                    strategy_class=strategy_class,
                    request=request
                )
                result.add_symbol_result(request.symbols[0], symbol_result)
            else:
                # Multiple symbols - run in parallel
                await self._run_parallel_backtests(
                    result=result,
                    config=config,
                    strategy_class=strategy_class,
                    request=request
                )
            
            # Calculate portfolio metrics
            result.calculate_portfolio_metrics()
            
            # Calculate execution time
            result.execution_time_ms = int(
                (datetime.utcnow() - start_execution).total_seconds() * 1000
            )
            
            # Save to database if repository available
            if self.repository:
                await self._save_results(result, config)
            
            logger.info(
                f"Completed unified backtest {result.job_id} in {result.execution_time_ms}ms"
            )
            
            return result
            
        finally:
            # Clean up active job
            self._active_jobs.pop(result.job_id, None)
    
    async def _run_symbol_backtest(self,
                                   symbol: str,
                                   config: StrategyConfiguration,
                                   strategy_class: type,
                                   request: UnifiedBacktestRequest) -> SymbolBacktestResult:
        """
        Run backtest for a single symbol.
        
        Args:
            symbol: Trading symbol
            config: Strategy configuration
            strategy_class: Strategy class to use
            request: Original backtest request
        
        Returns:
            Symbol backtest result
        """
        try:
            logger.info(f"Running backtest for {symbol}")
            
            # Fetch data
            data = self.data_adapter.fetch_ohlcv(
                symbol=symbol,
                start_date=request.start_time,
                end_date=request.end_time,
                interval=config.interval
            )
            
            if data.empty:
                raise ValueError(f"No data available for {symbol}")
            
            # Select appropriate engine
            if config.is_futures_strategy():
                # Run futures backtest
                results = self.futures_engine.run_futures_backtest(
                    data=data,
                    strategy_class=strategy_class,
                    initial_cash=request.initial_capital,
                    leverage=config.leverage,
                    market_commission=config.market_commission,
                    limit_commission=config.limit_commission,
                    **config.params
                )
                
                return SymbolBacktestResult(
                    symbol=symbol,
                    stats=results.stats,
                    trades=results.trades,
                    equity_curve=results.equity_curve,
                    chart_html=results.chart_html,
                    futures_metrics=results.futures_metrics
                )
            else:
                # Run spot backtest
                results = self.backtest_engine.run_backtest(
                    data=data,
                    strategy_class=strategy_class,
                    initial_cash=request.initial_capital,
                    commission=config.get_commission_rate(),
                    **config.params
                )
                
                return SymbolBacktestResult(
                    symbol=symbol,
                    stats=results.stats,
                    trades=results.trades,
                    equity_curve=results.equity_curve,
                    chart_html=results.chart_html
                )
                
        except Exception as e:
            logger.error(f"Failed to run backtest for {symbol}: {str(e)}")
            return SymbolBacktestResult(
                symbol=symbol,
                stats=pd.Series(),
                trades=pd.DataFrame(),
                equity_curve=pd.Series(),
                error=str(e)
            )
    
    async def _run_parallel_backtests(self,
                                     result: UnifiedBacktestResult,
                                     config: StrategyConfiguration,
                                     strategy_class: type,
                                     request: UnifiedBacktestRequest):
        """
        Run backtests for multiple symbols in parallel.
        
        Args:
            result: Result container to populate
            config: Strategy configuration
            strategy_class: Strategy class to use
            request: Original backtest request
        """
        # Create futures for all symbols
        loop = asyncio.get_event_loop()
        futures = []
        
        for symbol in request.symbols:
            future = loop.run_in_executor(
                self.executor,
                asyncio.run,
                self._run_symbol_backtest(symbol, config, strategy_class, request)
            )
            futures.append((symbol, future))
        
        # Wait for completion and collect results
        for symbol, future in futures:
            try:
                symbol_result = await future
                result.add_symbol_result(symbol, symbol_result)
            except Exception as e:
                logger.error(f"Failed to run backtest for {symbol}: {str(e)}")
                result.add_symbol_result(
                    symbol,
                    SymbolBacktestResult(
                        symbol=symbol,
                        stats=pd.Series(),
                        trades=pd.DataFrame(),
                        equity_curve=pd.Series(),
                        error=str(e)
                    )
                )
    
    async def _save_results(self, 
                          result: UnifiedBacktestResult,
                          config: StrategyConfiguration):
        """
        Save backtest results to database.
        
        Args:
            result: Backtest result to save
            config: Strategy configuration used
        """
        try:
            # Save main result
            await self.repository.save_backtest_result(
                job_id=result.job_id,
                strategy_config=config,
                result=result
            )
            
            # Save individual symbol results
            for symbol, symbol_result in result.symbol_results.items():
                if not symbol_result.error:
                    await self.repository.save_symbol_result(
                        job_id=result.job_id,
                        symbol=symbol,
                        result=symbol_result
                    )
            
            logger.info(f"Saved backtest results to database: {result.job_id}")
            
        except Exception as e:
            logger.error(f"Failed to save results to database: {str(e)}")
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of active backtest jobs.
        
        Returns:
            List of active job summaries
        """
        return [
            {
                'job_id': str(job_id),
                'strategy_id': result.strategy_id,
                'symbols': list(result.symbol_results.keys()),
                'created_at': result.created_at.isoformat()
            }
            for job_id, result in self._active_jobs.items()
        ]
    
    def get_job_status(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific job.
        
        Args:
            job_id: Job ID to check
        
        Returns:
            Job status or None if not found
        """
        result = self._active_jobs.get(job_id)
        if not result:
            return None
        
        completed_symbols = len(result.symbol_results)
        total_symbols = len(result.symbol_results)  # Should track requested symbols
        
        return {
            'job_id': str(job_id),
            'status': 'running' if completed_symbols < total_symbols else 'completed',
            'progress': f"{completed_symbols}/{total_symbols} symbols",
            'created_at': result.created_at.isoformat()
        }
    
    async def get_historical_results(self,
                                    strategy_id: Optional[str] = None,
                                    symbol: Optional[str] = None,
                                    start_date: Optional[datetime] = None,
                                    end_date: Optional[datetime] = None,
                                    limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical backtest results from database.
        
        Args:
            strategy_id: Filter by strategy
            symbol: Filter by symbol
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results to return
        
        Returns:
            List of historical results
        """
        if not self.repository:
            return []
        
        return await self.repository.get_backtest_results(
            strategy_id=strategy_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
    def shutdown(self):
        """Shutdown the service and cleanup resources"""
        self.executor.shutdown(wait=True)
        logger.info("Unified backtest service shutdown complete")