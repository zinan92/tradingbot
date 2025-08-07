"""
Backtest Engine

Core backtesting engine that wraps backtesting.py library.
Runs backtests and produces performance metrics and charts.
"""

from backtesting import Backtest
from backtesting._stats import compute_stats
import pandas as pd
import numpy as np
from typing import Type, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import base64
from io import StringIO
import logging

from .strategy_adapter import BaseStrategy
from .results_formatter import ResultsFormatter

logger = logging.getLogger(__name__)


@dataclass
class BacktestResults:
    """Container for backtest results"""
    stats: pd.Series  # Performance statistics
    trades: pd.DataFrame  # Trade history
    equity_curve: pd.Series  # Equity over time
    chart_html: str  # Interactive HTML chart
    strategy_params: Dict[str, Any]  # Strategy parameters used
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary format"""
        # Convert stats to dict, handling special types
        stats_dict = {}
        for key, value in self.stats.items():
            if pd.isna(value):
                stats_dict[key] = None
            elif isinstance(value, (pd.Timestamp, datetime)):
                stats_dict[key] = value.isoformat()
            elif isinstance(value, pd.Timedelta):
                stats_dict[key] = str(value)
            elif isinstance(value, (int, float, str, bool)):
                stats_dict[key] = value
            else:
                stats_dict[key] = str(value)
        
        return {
            'stats': stats_dict,
            'trades': self.trades.to_dict('records') if not self.trades.empty else [],
            'equity_curve': self.equity_curve.to_list() if self.equity_curve is not None else [],
            'chart_html': self.chart_html,
            'strategy_params': self.strategy_params
        }


class BacktestEngine:
    """
    Main backtesting engine that coordinates strategy execution and results generation
    """
    
    def __init__(self):
        """Initialize the backtest engine"""
        self.formatter = ResultsFormatter()
        self._last_backtest = None  # Store last Backtest object for plotting
    
    def run_backtest(self,
                    data: pd.DataFrame,
                    strategy_class: Type[BaseStrategy],
                    initial_cash: float = 10000,
                    commission: float = 0.002,
                    margin: float = 1.0,
                    trade_on_close: bool = False,
                    exclusive_orders: bool = True,
                    **strategy_params) -> BacktestResults:
        """
        Run a backtest with the given data and strategy.
        
        Args:
            data: OHLCV DataFrame with DatetimeIndex
            strategy_class: Strategy class (must inherit from BaseStrategy)
            initial_cash: Starting capital
            commission: Commission per trade (as fraction, e.g., 0.002 = 0.2%)
            margin: Margin requirement (1.0 = no leverage)
            trade_on_close: Execute trades on close price
            exclusive_orders: Cancel pending orders on new signal
            **strategy_params: Parameters to pass to strategy
            
        Returns:
            BacktestResults containing stats, trades, and charts
        """
        logger.info(f"Starting backtest with {strategy_class.__name__}")
        logger.info(f"Data range: {data.index[0]} to {data.index[-1]}")
        logger.info(f"Initial cash: ${initial_cash:,.2f}, Commission: {commission:.2%}")
        
        # Validate data
        self._validate_data(data)
        
        # Create Backtest instance
        bt = Backtest(
            data=data,
            strategy=strategy_class,
            cash=initial_cash,
            commission=commission,
            margin=margin,
            trade_on_close=trade_on_close,
            exclusive_orders=exclusive_orders
        )
        
        # Store for later plotting
        self._last_backtest = bt
        
        # Run the backtest with strategy parameters
        try:
            stats = bt.run(**strategy_params)
        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}")
            raise
        
        # Format the results
        formatted_stats = self.formatter.format_stats(stats)
        
        # Get trade history
        trades = self._extract_trades(stats)
        
        # Get equity curve
        equity_curve = self._extract_equity_curve(stats)
        
        # Generate HTML chart
        try:
            # Generate the plot without opening browser
            chart_html = bt.plot(open_browser=False, resample=False)
        except Exception as e:
            logger.warning(f"Failed to generate chart: {str(e)}")
            chart_html = "<p>Chart generation failed</p>"
        
        logger.info(f"Backtest complete. {len(trades)} trades executed.")
        logger.info(f"Final return: {formatted_stats['Return [%]']:.2f}%")
        
        return BacktestResults(
            stats=formatted_stats,
            trades=trades,
            equity_curve=equity_curve,
            chart_html=chart_html,
            strategy_params=strategy_params
        )
    
    def optimize(self,
                data: pd.DataFrame,
                strategy_class: Type[BaseStrategy],
                initial_cash: float = 10000,
                commission: float = 0.002,
                maximize: str = 'Sharpe Ratio',
                constraint: Optional[callable] = None,
                **param_ranges) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Optimize strategy parameters.
        
        Args:
            data: OHLCV DataFrame
            strategy_class: Strategy class to optimize
            initial_cash: Starting capital
            commission: Commission per trade
            maximize: Metric to maximize ('Sharpe Ratio', 'Return [%]', etc.)
            constraint: Optional constraint function
            **param_ranges: Parameter ranges to optimize
                           e.g., n1=range(5, 30), n2=range(20, 80)
        
        Returns:
            Tuple of (best_params, all_results)
        """
        logger.info(f"Starting optimization for {strategy_class.__name__}")
        logger.info(f"Optimizing: {param_ranges}")
        
        # Create Backtest instance
        bt = Backtest(
            data=data,
            strategy=strategy_class,
            cash=initial_cash,
            commission=commission,
            exclusive_orders=True
        )
        
        # Run optimization
        results = bt.optimize(
            maximize=maximize,
            constraint=constraint,
            **param_ranges
        )
        
        logger.info(f"Optimization complete. Best {maximize}: {results[maximize]:.2f}")
        
        return results, results._strategy
    
    def _validate_data(self, data: pd.DataFrame):
        """
        Validate that data is in correct format for backtesting.
        
        Args:
            data: DataFrame to validate
            
        Raises:
            ValueError: If data is invalid
        """
        # Check required columns
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Check index is DatetimeIndex
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data index must be DatetimeIndex")
        
        # Check for NaN values in OHLCV
        if data[required_columns].isnull().any().any():
            raise ValueError("OHLCV data contains NaN values")
        
        # Check OHLC relationships
        if not (data['Low'] <= data['High']).all():
            raise ValueError("Invalid OHLC data: Low > High")
        
        if not ((data['Low'] <= data['Open']) & (data['Open'] <= data['High'])).all():
            raise ValueError("Invalid OHLC data: Open outside Low-High range")
        
        if not ((data['Low'] <= data['Close']) & (data['Close'] <= data['High'])).all():
            raise ValueError("Invalid OHLC data: Close outside Low-High range")
    
    def _extract_trades(self, stats: pd.Series) -> pd.DataFrame:
        """
        Extract trade history from backtest results.
        
        Args:
            stats: Backtest statistics
            
        Returns:
            DataFrame with trade details
        """
        try:
            trades = stats['_trades']
            
            if trades is None or trades.empty:
                return pd.DataFrame()
            
            # Clean up trades DataFrame
            trades_df = trades.copy()
            
            # Add trade number
            trades_df['TradeNum'] = range(1, len(trades_df) + 1)
            
            # Calculate trade statistics
            if 'ReturnPct' not in trades_df.columns and 'PnL' in trades_df.columns:
                # Calculate return percentage from PnL
                trades_df['ReturnPct'] = trades_df['PnL'] / trades_df['EntryPrice'] * 100
            
            return trades_df
            
        except Exception as e:
            logger.warning(f"Failed to extract trades: {str(e)}")
            return pd.DataFrame()
    
    def _extract_equity_curve(self, stats: pd.Series) -> pd.Series:
        """
        Extract equity curve from backtest results.
        
        Args:
            stats: Backtest statistics
            
        Returns:
            Series with equity values over time
        """
        try:
            equity = stats.get('_equity_curve')
            
            if equity is None:
                return pd.Series()
            
            if isinstance(equity, pd.DataFrame):
                # Extract the Equity column
                return equity['Equity'] if 'Equity' in equity.columns else equity.iloc[:, 0]
            elif isinstance(equity, pd.Series):
                return equity
            else:
                return pd.Series()
                
        except Exception as e:
            logger.warning(f"Failed to extract equity curve: {str(e)}")
            return pd.Series()
    
    def generate_report(self, results: BacktestResults) -> str:
        """
        Generate a text report of backtest results.
        
        Args:
            results: BacktestResults object
            
        Returns:
            Formatted text report
        """
        return self.formatter.generate_text_report(results.stats, results.trades)