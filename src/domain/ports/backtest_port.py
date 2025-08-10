"""
Backtest port interface.

Defines the contract for backtesting engines.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass

from src.domain.entities import Order, Position
from src.domain.value_objects import Symbol


@dataclass
class BacktestResults:
    """Results from a backtest run."""
    total_return: Decimal
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: Decimal
    avg_loss: Decimal
    profit_factor: float
    recovery_factor: float
    calmar_ratio: float
    sortino_ratio: float
    equity_curve: List[float]
    trades: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_return": float(self.total_return),
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_win": float(self.avg_win),
            "avg_loss": float(self.avg_loss),
            "profit_factor": self.profit_factor,
            "recovery_factor": self.recovery_factor,
            "calmar_ratio": self.calmar_ratio,
            "sortino_ratio": self.sortino_ratio,
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "metrics": self.metrics
        }


@dataclass
class BacktestConfig:
    """Configuration for backtest."""
    symbol: Symbol
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    commission: float = 0.001
    slippage: float = 0.0001
    leverage: float = 1.0
    data_frequency: str = "1m"


class BacktestPort(ABC):
    """
    Port interface for backtesting engines.
    
    All backtesting implementations must implement this interface.
    """
    
    @abstractmethod
    async def run_backtest(
        self,
        strategy: 'StrategyPort',
        config: BacktestConfig
    ) -> BacktestResults:
        """
        Run a backtest with given strategy and configuration.
        
        Args:
            strategy: Strategy to test
            config: Backtest configuration
            
        Returns:
            Backtest results
        """
        pass
    
    @abstractmethod
    async def get_historical_data(
        self,
        symbol: Symbol,
        start_date: datetime,
        end_date: datetime,
        frequency: str
    ) -> List[Dict[str, Any]]:
        """
        Get historical market data.
        
        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            frequency: Data frequency (1m, 5m, 1h, etc.)
            
        Returns:
            List of price bars
        """
        pass
    
    @abstractmethod
    def get_current_position(self, symbol: Symbol) -> Optional[Position]:
        """
        Get current position for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current position or None
        """
        pass
    
    @abstractmethod
    def get_account_balance(self) -> Decimal:
        """
        Get current account balance.
        
        Returns:
            Account balance
        """
        pass
    
    @abstractmethod
    def place_order(self, order: Order) -> bool:
        """
        Place an order in backtest.
        
        Args:
            order: Order to place
            
        Returns:
            True if order was placed successfully
        """
        pass


class StrategyPort(ABC):
    """
    Port interface for trading strategies.
    
    All strategies must implement this interface.
    """
    
    @abstractmethod
    def initialize(self, **params) -> None:
        """
        Initialize strategy with parameters.
        
        Args:
            **params: Strategy-specific parameters
        """
        pass
    
    @abstractmethod
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Order]:
        """
        Handle new tick data.
        
        Args:
            tick: Tick data
            
        Returns:
            Order to place or None
        """
        pass
    
    @abstractmethod
    def on_bar(self, bar: Dict[str, Any]) -> Optional[Order]:
        """
        Handle new price bar.
        
        Args:
            bar: Price bar (OHLCV)
            
        Returns:
            Order to place or None
        """
        pass
    
    @abstractmethod
    def should_close_position(self, position: Position, current_price: Decimal) -> bool:
        """
        Check if position should be closed.
        
        Args:
            position: Current position
            current_price: Current market price
            
        Returns:
            True if position should be closed
        """
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """
        Get strategy parameters.
        
        Returns:
            Strategy parameters
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get strategy name.
        
        Returns:
            Strategy name
        """
        pass