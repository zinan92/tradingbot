"""
Futures Backtest Engine

Enhanced backtesting engine that supports futures trading features:
- Leverage/margin trading
- Different commission rates for market/limit orders
- LONG and SHORT position tracking
- Advanced metrics for futures trading
"""

from backtesting import Backtest
from backtesting._stats import compute_stats
import pandas as pd
import numpy as np
from typing import Type, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import logging

from .futures_strategy_adapter import FuturesBaseStrategy, OrderType
from .results_formatter import ResultsFormatter

logger = logging.getLogger(__name__)


@dataclass
class FuturesBacktestResults:
    """Container for futures backtest results"""
    stats: pd.Series  # Performance statistics
    trades: pd.DataFrame  # Trade history with direction
    equity_curve: pd.Series  # Equity over time
    chart_html: str  # Interactive HTML chart
    strategy_params: Dict[str, Any]  # Strategy parameters used
    futures_metrics: Dict[str, Any]  # Futures-specific metrics
    
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
            'strategy_params': self.strategy_params,
            'futures_metrics': self.futures_metrics
        }


class FuturesBacktestEngine:
    """
    Enhanced backtesting engine for futures trading
    """
    
    def __init__(self):
        """Initialize the futures backtest engine"""
        self.formatter = ResultsFormatter()
        self._last_backtest = None  # Store last Backtest object for plotting
    
    def run_futures_backtest(self,
                            data: pd.DataFrame,
                            strategy_class: Type[FuturesBaseStrategy],
                            initial_cash: float = 10000,
                            leverage: float = 10.0,
                            market_commission: float = 0.0004,
                            limit_commission: float = 0.0002,
                            margin_requirement: float = 0.1,
                            trade_on_close: bool = False,
                            exclusive_orders: bool = True,
                            **strategy_params) -> FuturesBacktestResults:
        """
        Run a futures backtest with leverage and advanced features.
        
        Args:
            data: OHLCV DataFrame with DatetimeIndex
            strategy_class: Strategy class (must inherit from FuturesBaseStrategy)
            initial_cash: Starting capital
            leverage: Trading leverage (e.g., 10 = 10x leverage)
            market_commission: Commission for market orders (e.g., 0.0004 = 0.04%)
            limit_commission: Commission for limit orders (e.g., 0.0002 = 0.02%)
            margin_requirement: Margin requirement (e.g., 0.1 = 10% margin)
            trade_on_close: Execute trades on close price
            exclusive_orders: Cancel pending orders on new signal
            **strategy_params: Parameters to pass to strategy
            
        Returns:
            FuturesBacktestResults containing stats, trades, and charts
        """
        logger.info(f"Starting futures backtest with {strategy_class.__name__}")
        logger.info(f"Data range: {data.index[0]} to {data.index[-1]}")
        logger.info(f"Initial cash: ${initial_cash:,.2f}, Leverage: {leverage}x")
        logger.info(f"Market commission: {market_commission:.2%}, Limit commission: {limit_commission:.2%}")
        
        # Validate data
        self._validate_data(data)
        
        # Set strategy parameters
        if 'leverage' in strategy_params:
            leverage = strategy_params['leverage']
        if 'market_commission' in strategy_params:
            market_commission = strategy_params['market_commission']
        if 'limit_commission' in strategy_params:
            limit_commission = strategy_params['limit_commission']
        
        # Calculate effective margin for backtesting.py
        # backtesting.py uses margin as 1/leverage
        effective_margin = 1 / leverage if leverage > 0 else 1.0
        
        # Use average commission for backtesting.py (will track separately)
        avg_commission = (market_commission + limit_commission) / 2
        
        # Create Backtest instance
        bt = Backtest(
            data=data,
            strategy=strategy_class,
            cash=initial_cash,
            commission=avg_commission,
            margin=effective_margin,
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
        
        # Format the results with futures enhancements
        formatted_stats = self._format_futures_stats(stats, leverage)
        
        # Get trade history with direction tracking
        trades = self._extract_futures_trades(stats, strategy_class)
        
        # Get equity curve
        equity_curve = self._extract_equity_curve(stats)
        
        # Calculate futures-specific metrics
        futures_metrics = self._calculate_futures_metrics(
            trades, 
            leverage, 
            market_commission, 
            limit_commission
        )
        
        # Generate HTML chart
        try:
            # Generate the plot without opening browser
            from bokeh.embed import file_html
            from bokeh.resources import CDN
            
            plot_obj = bt.plot(open_browser=False, resample=False)
            
            # Convert bokeh plot to HTML string
            if plot_obj is not None:
                chart_html = file_html(plot_obj, CDN, "Futures Backtest Results")
            else:
                chart_html = "<p>No chart data available</p>"
                
        except Exception as e:
            logger.warning(f"Failed to generate chart: {str(e)}")
            chart_html = "<p>Chart generation failed</p>"
        
        logger.info(f"Backtest complete. {len(trades)} trades executed.")
        logger.info(f"Final return (with {leverage}x leverage): {formatted_stats['Leveraged Return [%]']:.2f}%")
        
        return FuturesBacktestResults(
            stats=formatted_stats,
            trades=trades,
            equity_curve=equity_curve,
            chart_html=chart_html,
            strategy_params=strategy_params,
            futures_metrics=futures_metrics
        )
    
    def _format_futures_stats(self, stats: pd.Series, leverage: float) -> pd.Series:
        """
        Format statistics with futures-specific metrics.
        
        Args:
            stats: Original backtest statistics
            leverage: Leverage used
            
        Returns:
            Enhanced statistics
        """
        # Start with original stats
        formatted = self.formatter.format_stats(stats)
        
        # Add leveraged metrics
        base_return = formatted.get('Return [%]', 0)
        leveraged_return = base_return * leverage
        
        # Adjust volatility for leverage
        base_volatility = formatted.get('Volatility (Ann.) [%]', 0)
        leveraged_volatility = base_volatility * leverage
        
        # Adjust Sharpe ratio (return increases but so does volatility)
        # Sharpe remains the same theoretically, but we recalculate for accuracy
        if leveraged_volatility > 0:
            risk_free_rate = 0  # Assuming 0% risk-free rate
            leveraged_sharpe = (leveraged_return - risk_free_rate) / leveraged_volatility
        else:
            leveraged_sharpe = 0
        
        # Add futures-specific metrics
        formatted['Leverage'] = leverage
        formatted['Base Return [%]'] = base_return
        formatted['Leveraged Return [%]'] = leveraged_return
        formatted['Leveraged Volatility [%]'] = leveraged_volatility
        formatted['Leveraged Sharpe'] = leveraged_sharpe
        
        # Calculate margin utilization
        if 'Exposure Time [%]' in formatted:
            formatted['Avg Margin Utilization [%]'] = formatted['Exposure Time [%]'] * leverage
        
        return formatted
    
    def _extract_futures_trades(self, stats: pd.Series, strategy_class: Type) -> pd.DataFrame:
        """
        Extract trade history with futures-specific details.
        
        Args:
            stats: Backtest statistics
            strategy_class: Strategy class used
            
        Returns:
            DataFrame with enhanced trade details
        """
        try:
            trades = stats['_trades']
            
            if trades is None or trades.empty:
                return pd.DataFrame()
            
            # Clean up trades DataFrame
            trades_df = trades.copy()
            
            # Add trade number
            trades_df['TradeNum'] = range(1, len(trades_df) + 1)
            
            # Determine position direction based on size
            # Positive size = LONG, Negative size = SHORT
            trades_df['Direction'] = trades_df['Size'].apply(
                lambda x: 'LONG' if x > 0 else 'SHORT' if x < 0 else 'NEUTRAL'
            )
            
            # Calculate leveraged P&L
            if 'ReturnPct' in trades_df.columns:
                strategy_leverage = getattr(strategy_class, 'leverage', 1.0)
                trades_df['LeveragedReturnPct'] = trades_df['ReturnPct'] * strategy_leverage
            
            # Add commission type (simplified - could be enhanced)
            trades_df['OrderType'] = 'MARKET'  # Default to market orders
            
            return trades_df
            
        except Exception as e:
            logger.warning(f"Failed to extract futures trades: {str(e)}")
            return pd.DataFrame()
    
    def _calculate_futures_metrics(self,
                                  trades: pd.DataFrame,
                                  leverage: float,
                                  market_commission: float,
                                  limit_commission: float) -> Dict[str, Any]:
        """
        Calculate futures-specific metrics.
        
        Args:
            trades: Trade history
            leverage: Leverage used
            market_commission: Market order commission
            limit_commission: Limit order commission
            
        Returns:
            Dictionary of futures metrics
        """
        if trades.empty:
            return {
                'total_longs': 0,
                'total_shorts': 0,
                'long_win_rate': 0,
                'short_win_rate': 0,
                'avg_leverage_used': leverage,
                'total_commission_paid': 0,
                'effective_commission_rate': 0
            }
        
        # Count long and short trades
        longs = trades[trades['Direction'] == 'LONG']
        shorts = trades[trades['Direction'] == 'SHORT']
        
        # Calculate win rates by direction
        long_wins = len(longs[longs['PnL'] > 0]) if len(longs) > 0 else 0
        short_wins = len(shorts[shorts['PnL'] > 0]) if len(shorts) > 0 else 0
        
        long_win_rate = (long_wins / len(longs) * 100) if len(longs) > 0 else 0
        short_win_rate = (short_wins / len(shorts) * 100) if len(shorts) > 0 else 0
        
        # Calculate commission costs
        market_trades = trades[trades['OrderType'] == 'MARKET']
        limit_trades = trades[trades['OrderType'] == 'LIMIT']
        
        total_market_volume = market_trades['Size'].abs().sum() if len(market_trades) > 0 else 0
        total_limit_volume = limit_trades['Size'].abs().sum() if len(limit_trades) > 0 else 0
        
        market_commission_paid = total_market_volume * market_commission
        limit_commission_paid = total_limit_volume * limit_commission
        total_commission = market_commission_paid + limit_commission_paid
        
        total_volume = trades['Size'].abs().sum()
        effective_commission = (total_commission / total_volume) if total_volume > 0 else 0
        
        return {
            'total_longs': len(longs),
            'total_shorts': len(shorts),
            'long_win_rate': long_win_rate,
            'short_win_rate': short_win_rate,
            'avg_leverage_used': leverage,
            'total_commission_paid': total_commission,
            'effective_commission_rate': effective_commission,
            'market_trades': len(market_trades),
            'limit_trades': len(limit_trades),
            'long_short_ratio': len(longs) / len(shorts) if len(shorts) > 0 else float('inf')
        }
    
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
    
    def generate_report(self, results: FuturesBacktestResults) -> str:
        """
        Generate a text report of futures backtest results.
        
        Args:
            results: FuturesBacktestResults object
            
        Returns:
            Formatted text report
        """
        report = self.formatter.generate_text_report(results.stats, results.trades)
        
        # Add futures-specific section
        report += "\n" + "=" * 60 + "\n"
        report += "FUTURES TRADING METRICS\n"
        report += "=" * 60 + "\n"
        
        metrics = results.futures_metrics
        report += f"Total Long Trades:     {metrics.get('total_longs', 0)}\n"
        report += f"Total Short Trades:    {metrics.get('total_shorts', 0)}\n"
        report += f"Long Win Rate:         {metrics.get('long_win_rate', 0):.2f}%\n"
        report += f"Short Win Rate:        {metrics.get('short_win_rate', 0):.2f}%\n"
        report += f"Long/Short Ratio:      {metrics.get('long_short_ratio', 0):.2f}\n"
        report += f"Leverage Used:         {metrics.get('avg_leverage_used', 1):.1f}x\n"
        report += f"Total Commission:      ${metrics.get('total_commission_paid', 0):.2f}\n"
        report += f"Effective Comm Rate:   {metrics.get('effective_commission_rate', 0):.4%}\n"
        
        return report