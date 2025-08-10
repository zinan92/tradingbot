"""
Results Storage Port for Backtesting

Port interface for storing and formatting backtest results.
Provides both tabular statistics and chart generation following hexagonal architecture.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Union, Protocol
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ResultsStore(Protocol):
    """Port interface for storing and retrieving backtest results"""
    
    def store_results(self, results: Dict[str, Any]) -> str:
        """Store backtest results and return result ID"""
        pass
    
    def retrieve_results(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve backtest results by ID"""
        pass
    
    def list_results(self, strategy_name: Optional[str] = None) -> list:
        """List stored results, optionally filtered by strategy"""
        pass


class ResultsFormatter:
    """
    Formats backtest results for display and analysis.
    This is an adapter implementing the results storage functionality.
    """
    
    def format_stats(self, raw_stats: pd.Series) -> pd.Series:
        """
        Format raw backtesting.py stats to match the exact format from screenshot.
        
        Args:
            raw_stats: Raw statistics from backtesting.py
            
        Returns:
            Formatted statistics matching the screenshot format
        """
        # Create formatted stats dictionary matching screenshot exactly
        formatted = pd.Series()
        
        # Time metrics
        formatted['Start'] = raw_stats.get('Start', '')
        formatted['End'] = raw_stats.get('End', '')
        formatted['Duration'] = raw_stats.get('Duration', '')
        formatted['Exposure Time [%]'] = self._format_percentage(raw_stats.get('Exposure Time [%]', 0))
        
        # Equity metrics
        formatted['Equity Final [$]'] = self._format_currency(raw_stats.get('Equity Final [$]', 0))
        formatted['Equity Peak [$]'] = self._format_currency(raw_stats.get('Equity Peak [$]', 0))
        formatted['Return [%]'] = self._format_percentage(raw_stats.get('Return [%]', 0))
        formatted['Buy & Hold Return [%]'] = self._format_percentage(raw_stats.get('Buy & Hold Return [%]', 0))
        formatted['Return (Ann.) [%]'] = self._format_percentage(raw_stats.get('Return (Ann.) [%]', 0))
        formatted['Volatility (Ann.) [%]'] = self._format_percentage(raw_stats.get('Volatility (Ann.) [%]', 0))
        
        # Risk metrics
        formatted['CAGR [%]'] = self._calculate_cagr(raw_stats)
        formatted['Sharpe Ratio'] = self._format_ratio(raw_stats.get('Sharpe Ratio', 0))
        formatted['Sortino Ratio'] = self._format_ratio(raw_stats.get('Sortino Ratio', 0))
        formatted['Calmar Ratio'] = self._format_ratio(raw_stats.get('Calmar Ratio', 0))
        formatted['Alpha [%]'] = self._calculate_alpha(raw_stats)
        formatted['Beta'] = self._format_ratio(raw_stats.get('Beta', 0))
        
        # Drawdown metrics
        formatted['Max. Drawdown [%]'] = self._format_percentage(raw_stats.get('Max. Drawdown [%]', 0))
        formatted['Avg. Drawdown [%]'] = self._format_percentage(raw_stats.get('Avg. Drawdown [%]', 0))
        formatted['Max. Drawdown Duration'] = self._format_duration(raw_stats.get('Max. Drawdown Duration', ''))
        formatted['Avg. Drawdown Duration'] = self._format_duration(raw_stats.get('Avg. Drawdown Duration', ''))
        
        # Trade metrics
        formatted['# Trades'] = int(raw_stats.get('# Trades', 0))
        formatted['Win Rate [%]'] = self._format_percentage(raw_stats.get('Win Rate [%]', 0))
        formatted['Best Trade [%]'] = self._format_percentage(raw_stats.get('Best Trade [%]', 0))
        formatted['Worst Trade [%]'] = self._format_percentage(raw_stats.get('Worst Trade [%]', 0))
        formatted['Avg. Trade [%]'] = self._format_percentage(raw_stats.get('Avg. Trade [%]', 0))
        formatted['Max. Trade Duration'] = self._format_duration(raw_stats.get('Max. Trade Duration', ''))
        formatted['Avg. Trade Duration'] = self._format_duration(raw_stats.get('Avg. Trade Duration', ''))
        
        # Advanced metrics
        formatted['Profit Factor'] = self._format_ratio(raw_stats.get('Profit Factor', 0))
        formatted['Expectancy [%]'] = self._format_percentage(raw_stats.get('Expectancy [%]', 0))
        formatted['SQN'] = self._format_ratio(raw_stats.get('SQN', 0))
        formatted['Kelly Criterion'] = self._calculate_kelly_criterion(raw_stats)
        
        # Strategy information
        formatted['_strategy'] = raw_stats.get('_strategy', '')
        formatted['_equity_curve'] = raw_stats.get('_equity_curve', pd.Series())
        formatted['_trades'] = raw_stats.get('_trades', pd.DataFrame())
        
        return formatted
    
    def _format_percentage(self, value: Union[float, int]) -> float:
        """Format percentage values"""
        if pd.isna(value):
            return 0.0
        return round(float(value), 2)
    
    def _format_currency(self, value: Union[float, int]) -> float:
        """Format currency values"""
        if pd.isna(value):
            return 0.0
        return round(float(value), 2)
    
    def _format_ratio(self, value: Union[float, int]) -> float:
        """Format ratio values"""
        if pd.isna(value):
            return 0.0
        # Handle infinite values
        if np.isinf(value):
            return 0.0
        return round(float(value), 2)
    
    def _format_duration(self, value: Any) -> str:
        """Format duration values"""
        if pd.isna(value) or value == '':
            return '0 days 00:00:00'
        
        if isinstance(value, pd.Timedelta):
            return str(value)
        elif isinstance(value, str):
            return value
        else:
            return '0 days 00:00:00'
    
    def _calculate_cagr(self, stats: pd.Series) -> float:
        """
        Calculate Compound Annual Growth Rate
        
        CAGR = (Ending Value / Beginning Value)^(1 / Years) - 1
        """
        try:
            equity_final = stats.get('Equity Final [$]', 0)
            equity_initial = stats.get('Equity Initial [$]', 10000)  # Default initial
            
            # Calculate duration in years
            start = stats.get('Start')
            end = stats.get('End')
            
            if start and end:
                if isinstance(start, str):
                    start = pd.to_datetime(start)
                if isinstance(end, str):
                    end = pd.to_datetime(end)
                
                years = (end - start).days / 365.25
                
                if years > 0 and equity_initial > 0:
                    cagr = (equity_final / equity_initial) ** (1 / years) - 1
                    return self._format_percentage(cagr * 100)
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Failed to calculate CAGR: {str(e)}")
            return 0.0
    
    def _calculate_alpha(self, stats: pd.Series) -> float:
        """
        Calculate Alpha (excess return over benchmark)
        
        Alpha = Portfolio Return - (Risk Free Rate + Beta * (Market Return - Risk Free Rate))
        Simplified: Alpha = Portfolio Return - Buy & Hold Return
        """
        try:
            portfolio_return = stats.get('Return [%]', 0)
            buy_hold_return = stats.get('Buy & Hold Return [%]', 0)
            
            # Simple alpha calculation
            alpha = portfolio_return - buy_hold_return
            
            return self._format_percentage(alpha)
            
        except Exception as e:
            logger.warning(f"Failed to calculate Alpha: {str(e)}")
            return 0.0
    
    def _calculate_kelly_criterion(self, stats: pd.Series) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing
        
        Kelly % = (Win Rate * Avg Win - Loss Rate * Avg Loss) / Avg Win
        """
        try:
            win_rate = stats.get('Win Rate [%]', 0) / 100
            trades = stats.get('_trades')
            
            if trades is not None and not trades.empty and len(trades) > 0:
                # Calculate average win and loss
                winning_trades = trades[trades['PnL'] > 0]
                losing_trades = trades[trades['PnL'] <= 0]
                
                if len(winning_trades) > 0 and len(losing_trades) > 0:
                    avg_win = winning_trades['PnL'].mean()
                    avg_loss = abs(losing_trades['PnL'].mean())
                    loss_rate = 1 - win_rate
                    
                    if avg_win > 0:
                        kelly = (win_rate * avg_win - loss_rate * avg_loss) / avg_win
                        return self._format_ratio(kelly)
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Failed to calculate Kelly Criterion: {str(e)}")
            return 0.0
    
    def generate_text_report(self, stats: pd.Series, trades: pd.DataFrame) -> str:
        """
        Generate a formatted text report matching the screenshot format.
        
        Args:
            stats: Formatted statistics
            trades: Trade history
            
        Returns:
            Formatted text report
        """
        report = []
        report.append("Results in:")
        report.append("")
        
        # Time section
        report.append(f"{'Start':<30} {stats.get('Start', '')}")
        report.append(f"{'End':<30} {stats.get('End', '')}")
        report.append(f"{'Duration':<30} {stats.get('Duration', '')}")
        report.append(f"{'Exposure Time [%]':<30} {stats.get('Exposure Time [%]', 0):.2f}")
        
        # Equity section
        report.append(f"{'Equity Final [$]':<30} {stats.get('Equity Final [$]', 0):.2f}")
        report.append(f"{'Equity Peak [$]':<30} {stats.get('Equity Peak [$]', 0):.2f}")
        report.append(f"{'Return [%]':<30} {stats.get('Return [%]', 0):.2f}")
        report.append(f"{'Buy & Hold Return [%]':<30} {stats.get('Buy & Hold Return [%]', 0):.2f}")
        report.append(f"{'Return (Ann.) [%]':<30} {stats.get('Return (Ann.) [%]', 0):.2f}")
        report.append(f"{'Volatility (Ann.) [%]':<30} {stats.get('Volatility (Ann.) [%]', 0):.2f}")
        
        # Risk metrics
        report.append(f"{'CAGR [%]':<30} {stats.get('CAGR [%]', 0):.2f}")
        report.append(f"{'Sharpe Ratio':<30} {stats.get('Sharpe Ratio', 0):.2f}")
        report.append(f"{'Sortino Ratio':<30} {stats.get('Sortino Ratio', 0):.2f}")
        report.append(f"{'Calmar Ratio':<30} {stats.get('Calmar Ratio', 0):.2f}")
        report.append(f"{'Alpha [%]':<30} {stats.get('Alpha [%]', 0):.2f}")
        report.append(f"{'Beta':<30} {stats.get('Beta', 0):.2f}")
        
        # Drawdown section
        report.append(f"{'Max. Drawdown [%]':<30} {stats.get('Max. Drawdown [%]', 0):.2f}")
        report.append(f"{'Avg. Drawdown [%]':<30} {stats.get('Avg. Drawdown [%]', 0):.2f}")
        report.append(f"{'Max. Drawdown Duration':<30} {stats.get('Max. Drawdown Duration', '')}")
        report.append(f"{'Avg. Drawdown Duration':<30} {stats.get('Avg. Drawdown Duration', '')}")
        
        # Trade section
        report.append(f"{'# Trades':<30} {stats.get('# Trades', 0)}")
        report.append(f"{'Win Rate [%]':<30} {stats.get('Win Rate [%]', 0):.2f}")
        report.append(f"{'Best Trade [%]':<30} {stats.get('Best Trade [%]', 0):.2f}")
        report.append(f"{'Worst Trade [%]':<30} {stats.get('Worst Trade [%]', 0):.2f}")
        report.append(f"{'Avg. Trade [%]':<30} {stats.get('Avg. Trade [%]', 0):.2f}")
        report.append(f"{'Max. Trade Duration':<30} {stats.get('Max. Trade Duration', '')}")
        report.append(f"{'Avg. Trade Duration':<30} {stats.get('Avg. Trade Duration', '')}")
        
        # Advanced metrics
        report.append(f"{'Profit Factor':<30} {stats.get('Profit Factor', 0):.2f}")
        report.append(f"{'Expectancy [%]':<30} {stats.get('Expectancy [%]', 0):.2f}")
        report.append(f"{'SQN':<30} {stats.get('SQN', 0):.2f}")
        report.append(f"{'Kelly Criterion':<30} {stats.get('Kelly Criterion', 0):.4f}")
        
        # Strategy info
        report.append(f"{'_strategy':<30} {stats.get('_strategy', '')}")
        report.append(f"{'_equity_curve':<30} Equ...")
        report.append(f"{'_trades':<30} Size   EntryB...")
        report.append(f"dtype: object")
        
        return '\n'.join(report)
    
    def format_trades_table(self, trades: pd.DataFrame) -> pd.DataFrame:
        """
        Format trades table for display.
        
        Args:
            trades: Raw trades DataFrame
            
        Returns:
            Formatted trades DataFrame
        """
        if trades.empty:
            return pd.DataFrame()
        
        formatted = pd.DataFrame()
        
        # Select and rename columns
        formatted['#'] = range(1, len(trades) + 1)
        formatted['Entry Time'] = trades['EntryTime'] if 'EntryTime' in trades else ''
        formatted['Exit Time'] = trades['ExitTime'] if 'ExitTime' in trades else ''
        formatted['Symbol'] = trades['Symbol'] if 'Symbol' in trades else 'N/A'
        formatted['Size'] = trades['Size'] if 'Size' in trades else 0
        formatted['Entry Price'] = trades['EntryPrice'] if 'EntryPrice' in trades else 0
        formatted['Exit Price'] = trades['ExitPrice'] if 'ExitPrice' in trades else 0
        formatted['PnL'] = trades['PnL'] if 'PnL' in trades else 0
        formatted['PnL %'] = trades['ReturnPct'] if 'ReturnPct' in trades else 0
        formatted['Duration'] = trades['Duration'] if 'Duration' in trades else ''
        
        return formatted


class InMemoryResultsStore:
    """Simple in-memory implementation of ResultsStore port"""
    
    def __init__(self):
        self._results = {}
        self._counter = 0
    
    def store_results(self, results: Dict[str, Any]) -> str:
        """Store backtest results and return result ID"""
        self._counter += 1
        result_id = f"result_{self._counter}"
        
        self._results[result_id] = {
            **results,
            'stored_at': datetime.utcnow(),
            'result_id': result_id
        }
        
        return result_id
    
    def retrieve_results(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve backtest results by ID"""
        return self._results.get(result_id)
    
    def list_results(self, strategy_name: Optional[str] = None) -> list:
        """List stored results, optionally filtered by strategy"""
        results = []
        
        for result_id, result_data in self._results.items():
            if strategy_name is None or result_data.get('strategy_name') == strategy_name:
                results.append({
                    'result_id': result_id,
                    'strategy_name': result_data.get('strategy_name'),
                    'stored_at': result_data.get('stored_at'),
                    'return_pct': result_data.get('stats', {}).get('Return [%]', 0),
                    'trades_count': result_data.get('stats', {}).get('# Trades', 0)
                })
        
        return sorted(results, key=lambda x: x['stored_at'], reverse=True)