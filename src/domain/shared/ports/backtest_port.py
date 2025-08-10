"""
Backtest Port

Abstract interface for backtesting operations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path


class BacktestPort(ABC):
    """Abstract interface for backtesting operations"""
    
    @abstractmethod
    async def run(self, input_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a backtest with the given configuration
        
        Args:
            input_config: Backtest configuration including:
                - strategy: Strategy configuration
                - symbol: Trading pair symbol
                - start_date: Backtest start date
                - end_date: Backtest end date
                - initial_capital: Starting capital
                - commission: Trading commission rate
                - slippage: Slippage model configuration
                
        Returns:
            BacktestReport dictionary containing:
                - metrics_json: Performance metrics as JSON
                - equity_csv: Equity curve data as CSV string
                - trades_csv: Trade log as CSV string
                - html_report: HTML report content
        """
        pass
    
    @abstractmethod
    async def validate_config(
        self,
        config: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate backtest configuration
        
        Args:
            config: Backtest configuration to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    async def estimate_duration(
        self,
        config: Dict[str, Any]
    ) -> float:
        """
        Estimate backtest execution duration
        
        Args:
            config: Backtest configuration
            
        Returns:
            Estimated duration in seconds
        """
        pass
    
    @abstractmethod
    async def get_available_data_range(
        self,
        symbol: str,
        interval: str
    ) -> tuple[datetime, datetime]:
        """
        Get available data range for a symbol
        
        Args:
            symbol: Trading pair symbol
            interval: Data interval
            
        Returns:
            Tuple of (start_date, end_date) for available data
        """
        pass
    
    @abstractmethod
    async def run_batch(
        self,
        strategy_name: str,
        search_space: Dict[str, List[Any]],
        base_config: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Path]:
        """
        Run batch backtests with parameter optimization
        
        Args:
            strategy_name: Name of the strategy to optimize
            search_space: Parameter search space, e.g.:
                {
                    'fast_period': [10, 20, 30],
                    'slow_period': [50, 100, 200],
                    'stop_loss': [0.01, 0.02, 0.03]
                }
            base_config: Base configuration for all backtests including:
                - symbol: Trading pair
                - start_date: Backtest start
                - end_date: Backtest end
                - initial_capital: Starting capital
                
        Returns:
            Tuple of (best_params, leaderboard_path) where:
                - best_params: Dictionary of best parameter values
                - leaderboard_path: Path to leaderboard.csv file
                
        Selection criteria:
            - Primary: Highest Sharpe ratio
            - Tie-breaker: Lower maximum drawdown
        """
        pass