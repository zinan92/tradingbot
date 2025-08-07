"""
Run Backtest Command

Command and handler for executing backtests.
Follows CQRS pattern for command handling.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
import logging

from src.infrastructure.backtesting import BacktestEngine, DataAdapter
from src.infrastructure.backtesting.backtest_engine import BacktestResults

logger = logging.getLogger(__name__)


@dataclass
class RunBacktestCommand:
    """
    Command to run a backtest
    
    Attributes:
        strategy_name: Name of strategy to run (e.g., 'SmaCross')
        symbol: Trading symbol (e.g., 'BTCUSDT')
        start_date: Start date for backtest
        end_date: End date for backtest
        initial_capital: Starting capital (default: 10000)
        commission: Trading commission as fraction (default: 0.002)
        interval: Data interval (1m, 5m, 1h, 1d, etc.)
        strategy_params: Strategy-specific parameters
    """
    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000
    commission: float = 0.002
    interval: str = '1h'
    strategy_params: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize command ID and validate parameters"""
        self.command_id = uuid4()
        self.strategy_params = self.strategy_params or {}
        
        # Validate dates
        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")
        
        # Validate capital
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")
        
        # Validate commission
        if self.commission < 0 or self.commission > 1:
            raise ValueError("Commission must be between 0 and 1")


class RunBacktestCommandHandler:
    """
    Handler for RunBacktestCommand
    
    Coordinates the backtest execution process.
    """
    
    def __init__(self, 
                 backtest_engine: Optional[BacktestEngine] = None,
                 data_adapter: Optional[DataAdapter] = None):
        """
        Initialize handler with dependencies
        
        Args:
            backtest_engine: Engine for running backtests
            data_adapter: Adapter for fetching market data
        """
        self.backtest_engine = backtest_engine or BacktestEngine()
        self.data_adapter = data_adapter or DataAdapter()
        self.strategy_registry = self._initialize_strategy_registry()
    
    def _initialize_strategy_registry(self) -> Dict[str, type]:
        """
        Initialize registry of available strategies
        
        Returns:
            Dictionary mapping strategy names to classes
        """
        from src.application.backtesting.strategies.sma_cross_strategy import (
            SmaCrossStrategy,
            EnhancedSmaCrossStrategy,
            AdaptiveSmaCrossStrategy
        )
        
        return {
            'SmaCross': SmaCrossStrategy,
            'EnhancedSmaCross': EnhancedSmaCrossStrategy,
            'AdaptiveSmaCross': AdaptiveSmaCrossStrategy,
        }
    
    def handle(self, command: RunBacktestCommand) -> BacktestResults:
        """
        Execute the backtest command
        
        Args:
            command: RunBacktestCommand to execute
            
        Returns:
            BacktestResults with statistics and charts
            
        Raises:
            ValueError: If strategy not found or data unavailable
            RuntimeError: If backtest execution fails
        """
        logger.info(f"Executing backtest command {command.command_id}")
        logger.info(f"Strategy: {command.strategy_name}, Symbol: {command.symbol}")
        logger.info(f"Period: {command.start_date} to {command.end_date}")
        
        try:
            # 1. Validate and get strategy class
            strategy_class = self._get_strategy_class(command.strategy_name)
            
            # 2. Fetch and prepare market data
            data = self._prepare_data(
                symbol=command.symbol,
                start_date=command.start_date,
                end_date=command.end_date,
                interval=command.interval
            )
            
            # 3. Run the backtest
            results = self.backtest_engine.run_backtest(
                data=data,
                strategy_class=strategy_class,
                initial_cash=command.initial_capital,
                commission=command.commission,
                **command.strategy_params
            )
            
            # 4. Log summary statistics
            self._log_results_summary(results)
            
            return results
            
        except ValueError as e:
            logger.error(f"Validation error in backtest: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to execute backtest: {str(e)}")
            raise RuntimeError(f"Backtest execution failed: {str(e)}")
    
    def _get_strategy_class(self, strategy_name: str) -> type:
        """
        Get strategy class from registry
        
        Args:
            strategy_name: Name of strategy
            
        Returns:
            Strategy class
            
        Raises:
            ValueError: If strategy not found
        """
        strategy_class = self.strategy_registry.get(strategy_name)
        
        if not strategy_class:
            available = ', '.join(self.strategy_registry.keys())
            raise ValueError(
                f"Strategy '{strategy_name}' not found. "
                f"Available strategies: {available}"
            )
        
        return strategy_class
    
    def _prepare_data(self,
                     symbol: str,
                     start_date: datetime,
                     end_date: datetime,
                     interval: str) -> Any:
        """
        Fetch and prepare market data for backtesting
        
        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            interval: Time interval
            
        Returns:
            Prepared DataFrame
            
        Raises:
            ValueError: If data unavailable
        """
        logger.info(f"Fetching {symbol} data from {start_date} to {end_date}")
        
        # Fetch data with indicators
        data = self.data_adapter.prepare_for_backtest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            add_indicators=True
        )
        
        if data.empty:
            raise ValueError(f"No data available for {symbol} in specified period")
        
        logger.info(f"Prepared {len(data)} bars of data")
        
        return data
    
    def _log_results_summary(self, results: BacktestResults):
        """
        Log summary of backtest results
        
        Args:
            results: Backtest results
        """
        stats = results.stats
        
        logger.info("=" * 50)
        logger.info("BACKTEST RESULTS SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total Return: {stats.get('Return [%]', 0):.2f}%")
        logger.info(f"Buy & Hold Return: {stats.get('Buy & Hold Return [%]', 0):.2f}%")
        logger.info(f"Sharpe Ratio: {stats.get('Sharpe Ratio', 0):.2f}")
        logger.info(f"Max Drawdown: {stats.get('Max. Drawdown [%]', 0):.2f}%")
        logger.info(f"Number of Trades: {stats.get('# Trades', 0)}")
        logger.info(f"Win Rate: {stats.get('Win Rate [%]', 0):.2f}%")
        logger.info(f"Profit Factor: {stats.get('Profit Factor', 0):.2f}")
        logger.info("=" * 50)


class BacktestNotFoundError(Exception):
    """Raised when a backtest is not found"""
    pass


class BacktestExecutionError(Exception):
    """Raised when backtest execution fails"""
    pass