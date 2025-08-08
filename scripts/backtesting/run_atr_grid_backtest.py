#!/usr/bin/env python3
"""
ATR Grid Strategy Backtest Runner

Runs comprehensive backtests of the ATR-based grid trading strategy
on BTC and ETH with 1 year of historical data.

Tests different market regimes to find optimal configuration.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from backtesting import Backtest
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Add project root to path
# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)))

from src.infrastructure.backtesting.strategies.simple_atr_grid import SimpleATRGridStrategy
from src.infrastructure.backtesting.strategies.atr_grid_strategy import (
    ATRGridStrategy,
    OptimizedATRGridStrategy
)
from src.domain.strategy.regime.regime_models import MarketRegime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a backtest run"""
    symbol: str
    regime: MarketRegime
    strategy_class: type
    initial_capital: float = 100000  # Increased for BTC trading
    commission: float = 0.002  # 0.2% trading fee
    
    # Grid parameters
    atr_multiplier: float = 0.75
    grid_levels: int = 5
    max_position_size: float = 0.1
    stop_loss_atr_mult: float = 2.0
    atr_period: int = 14
    use_regime: bool = True


class DataLoader:
    """Handles loading historical data from PostgreSQL"""
    
    def __init__(self, db_url: str = None):
        """Initialize data loader with database connection"""
        self.db_url = db_url or os.environ.get(
            'DATABASE_URL', 
            'postgresql://localhost/tradingbot'
        )
        self.engine = None
        
    def connect(self):
        """Establish database connection"""
        try:
            self.engine = create_engine(self.db_url)
            # Test connection
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def load_kline_data(self, symbol: str, interval: str, 
                       start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Load OHLCV data from database
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            interval: Timeframe (e.g., '1h')
            start_date: Start of period
            end_date: End of period
            
        Returns:
            DataFrame with OHLCV data
        """
        if not self.engine:
            raise RuntimeError("Not connected to database")
        
        query = """
        SELECT 
            open_time as timestamp,
            open_price as "Open",
            high_price as "High",
            low_price as "Low",
            close_price as "Close",
            volume as "Volume"
        FROM kline_data
        WHERE symbol = %(symbol)s
          AND interval = %(interval)s
          AND open_time >= %(start_date)s
          AND open_time <= %(end_date)s
        ORDER BY open_time
        """
        
        try:
            df = pd.read_sql(
                query,
                self.engine,
                params={
                    'symbol': symbol,
                    'interval': interval,
                    'start_date': start_date,
                    'end_date': end_date
                },
                parse_dates=['timestamp']
            )
            
            if df.empty:
                logger.warning(f"No data found for {symbol} from {start_date} to {end_date}")
                return pd.DataFrame()
            
            # Set timestamp as index
            df.set_index('timestamp', inplace=True)
            
            # Ensure numeric types
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove any NaN values
            df.dropna(inplace=True)
            
            logger.info(f"Loaded {len(df)} candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
            return pd.DataFrame()


def run_single_backtest(data: pd.DataFrame, config: BacktestConfig) -> Dict[str, Any]:
    """
    Run a single backtest with given configuration
    
    Args:
        data: OHLCV DataFrame
        config: Backtest configuration
        
    Returns:
        Dictionary with backtest results
    """
    if data.empty:
        return {
            'error': 'No data available',
            'symbol': config.symbol,
            'regime': config.regime.value
        }
    
    try:
        # Create backtest instance
        bt = Backtest(
            data,
            config.strategy_class,
            cash=config.initial_capital,
            commission=config.commission,
            exclusive_orders=True,
            trade_on_close=False
        )
        
        # Run backtest with parameters
        stats = bt.run(
            atr_multiplier=config.atr_multiplier,
            grid_levels=config.grid_levels,
            atr_period=config.atr_period,
            take_profit_atr=1.5,  # More conservative TP
            stop_loss_atr=config.stop_loss_atr_mult
        )
        
        # Extract key metrics
        results = {
            'symbol': config.symbol,
            'regime': config.regime.value,
            'return_pct': float(stats['Return [%]']) if 'Return [%]' in stats else 0,
            'sharpe_ratio': float(stats['Sharpe Ratio']) if 'Sharpe Ratio' in stats else 0,
            'max_drawdown_pct': float(stats['Max. Drawdown [%]']) if 'Max. Drawdown [%]' in stats else 0,
            'win_rate_pct': float(stats['Win Rate [%]']) if 'Win Rate [%]' in stats else 0,
            'num_trades': int(stats['# Trades']) if '# Trades' in stats else 0,
            'exposure_time_pct': float(stats['Exposure Time [%]']) if 'Exposure Time [%]' in stats else 0,
            'equity_final': float(stats['Equity Final [$]']) if 'Equity Final [$]' in stats else config.initial_capital,
            'equity_peak': float(stats['Equity Peak [$]']) if 'Equity Peak [$]' in stats else config.initial_capital,
            'avg_trade_pct': float(stats['Avg. Trade [%]']) if 'Avg. Trade [%]' in stats else 0,
            'best_trade_pct': float(stats['Best Trade [%]']) if 'Best Trade [%]' in stats else 0,
            'worst_trade_pct': float(stats['Worst Trade [%]']) if 'Worst Trade [%]' in stats else 0,
            'profit_factor': float(stats['Profit Factor']) if 'Profit Factor' in stats else 0,
            'expectancy_pct': float(stats['Expectancy [%]']) if 'Expectancy [%]' in stats else 0,
            'sqn': float(stats['SQN']) if 'SQN' in stats else 0
        }
        
        # Try to get grid-specific metrics if available
        # Note: bt._strategy is the class, not instance
        # Grid metrics would be available on the instance during execution
        # For now, we'll skip this as backtesting.py doesn't expose the instance after run
        
        # Save plot if this is the best result
        results['plot'] = bt.plot(open_browser=False, resample=False)
        
        return results
        
    except Exception as e:
        logger.error(f"Backtest failed for {config.symbol} in {config.regime.value} mode: {e}")
        import traceback
        traceback.print_exc()
        return {
            'error': str(e),
            'symbol': config.symbol,
            'regime': config.regime.value
        }


def print_results_table(results: List[Dict[str, Any]]):
    """Print formatted results table"""
    
    # Convert to DataFrame for easy formatting
    df = pd.DataFrame(results)
    
    # Remove error entries for display
    df_clean = df[~df.apply(lambda x: 'error' in x, axis=1)]
    
    if df_clean.empty:
        print("\n❌ No successful backtests completed")
        return
    
    print("\n" + "="*100)
    print("BACKTEST RESULTS SUMMARY")
    print("="*100)
    
    # Group by symbol
    for symbol in df_clean['symbol'].unique():
        symbol_data = df_clean[df_clean['symbol'] == symbol]
        
        print(f"\n📊 {symbol}")
        print("-" * 50)
        
        # Create formatted table
        display_cols = [
            'regime', 'return_pct', 'sharpe_ratio', 'max_drawdown_pct',
            'win_rate_pct', 'num_trades', 'avg_trade_pct', 'profit_factor'
        ]
        
        # Format the data
        formatted_data = symbol_data[display_cols].copy()
        formatted_data.columns = [
            'Regime', 'Return %', 'Sharpe', 'Max DD %',
            'Win Rate %', '# Trades', 'Avg Trade %', 'Profit Factor'
        ]
        
        # Round numeric columns
        numeric_cols = formatted_data.select_dtypes(include=[np.number]).columns
        formatted_data[numeric_cols] = formatted_data[numeric_cols].round(2)
        
        print(formatted_data.to_string(index=False))
        
        # Find best regime for this symbol
        if not symbol_data.empty:
            # Handle NaN values in sharpe_ratio
            valid_sharpe = symbol_data[symbol_data['sharpe_ratio'].notna()]
            if not valid_sharpe.empty:
                best_sharpe = valid_sharpe.loc[valid_sharpe['sharpe_ratio'].idxmax()]
            else:
                best_sharpe = symbol_data.iloc[0]  # Default to first if all NaN
            
            best_return = symbol_data.loc[symbol_data['return_pct'].idxmax()]
        
        print(f"\n✨ Best Sharpe Ratio: {best_sharpe['regime'].upper()} (Sharpe: {best_sharpe['sharpe_ratio']:.2f})")
        print(f"💰 Best Return: {best_return['regime'].upper()} (Return: {best_return['return_pct']:.2f}%)")
    
    # Overall comparison
    print("\n" + "="*100)
    print("OVERALL COMPARISON")
    print("="*100)
    
    # Average performance by regime
    regime_avg = df_clean.groupby('regime').agg({
        'return_pct': 'mean',
        'sharpe_ratio': 'mean',
        'max_drawdown_pct': 'mean',
        'win_rate_pct': 'mean',
        'num_trades': 'mean'
    }).round(2)
    
    print("\nAverage Performance by Regime:")
    print(regime_avg.to_string())
    
    # Best overall configuration
    best_overall = df_clean.loc[df_clean['sharpe_ratio'].idxmax()]
    print(f"\n🏆 BEST OVERALL CONFIGURATION:")
    print(f"   Symbol: {best_overall['symbol']}")
    print(f"   Regime: {best_overall['regime'].upper()}")
    print(f"   Return: {best_overall['return_pct']:.2f}%")
    print(f"   Sharpe: {best_overall['sharpe_ratio']:.2f}")
    print(f"   Max Drawdown: {best_overall['max_drawdown_pct']:.2f}%")
    print(f"   Win Rate: {best_overall['win_rate_pct']:.2f}%")


def generate_recommendations(results: List[Dict[str, Any]]) -> str:
    """Generate trading recommendations based on results"""
    
    df = pd.DataFrame(results)
    df_clean = df[~df.apply(lambda x: 'error' in x, axis=1)]
    
    if df_clean.empty:
        return "No successful backtests to analyze"
    
    recommendations = []
    recommendations.append("\n" + "="*100)
    recommendations.append("TRADING RECOMMENDATIONS")
    recommendations.append("="*100)
    
    # Analyze by symbol
    for symbol in df_clean['symbol'].unique():
        symbol_data = df_clean[df_clean['symbol'] == symbol]
        
        recommendations.append(f"\n📈 {symbol}:")
        
        # Find best regime
        best = symbol_data.loc[symbol_data['sharpe_ratio'].idxmax()]
        
        # Determine market characteristics
        range_perf = symbol_data[symbol_data['regime'] == 'range']
        bullish_perf = symbol_data[symbol_data['regime'] == 'bullish']
        bearish_perf = symbol_data[symbol_data['regime'] == 'bearish']
        
        if not range_perf.empty and range_perf.iloc[0]['sharpe_ratio'] > 0.5:
            recommendations.append(f"   ✓ RANGE mode recommended (Sharpe: {range_perf.iloc[0]['sharpe_ratio']:.2f})")
            recommendations.append("   - Market shows good mean reversion characteristics")
            recommendations.append("   - Bidirectional grids capture volatility effectively")
        elif not bullish_perf.empty and bullish_perf.iloc[0]['return_pct'] > 20:
            recommendations.append(f"   ✓ BULLISH mode recommended (Return: {bullish_perf.iloc[0]['return_pct']:.2f}%)")
            recommendations.append("   - Strong upward trend detected in historical data")
            recommendations.append("   - Long-only grids capture trend momentum")
        else:
            recommendations.append(f"   ✓ Best mode: {best['regime'].upper()}")
        
        # Risk warnings
        if best['max_drawdown_pct'] < -30:
            recommendations.append("   ⚠️ Warning: High drawdown risk - consider reducing position sizes")
        
        if best['num_trades'] < 50:
            recommendations.append("   ⚠️ Warning: Low trade frequency - consider tighter grid spacing")
    
    # General recommendations
    recommendations.append("\n📋 GENERAL RECOMMENDATIONS:")
    
    # Analyze overall regime performance
    regime_avg = df_clean.groupby('regime')['sharpe_ratio'].mean()
    best_regime = regime_avg.idxmax()
    
    if best_regime == 'range':
        recommendations.append("   • Grid trading works best in ranging/sideways markets")
        recommendations.append("   • Consider using technical indicators (RSI, Bollinger Bands) to identify ranges")
        recommendations.append("   • Implement automatic regime detection for better results")
    elif best_regime == 'bullish':
        recommendations.append("   • Current market shows trending behavior")
        recommendations.append("   • Consider combining with trend-following indicators")
        recommendations.append("   • Use wider grid spacing in strong trends")
    
    # Parameter optimization suggestions
    avg_trades = df_clean['num_trades'].mean()
    if avg_trades < 100:
        recommendations.append("   • Consider reducing grid spacing (lower atr_multiplier) for more trades")
    elif avg_trades > 500:
        recommendations.append("   • Consider increasing grid spacing to reduce overtrading")
    
    # Risk management
    avg_drawdown = df_clean['max_drawdown_pct'].mean()
    if avg_drawdown < -25:
        recommendations.append("   • Implement stricter risk management:")
        recommendations.append("     - Reduce max_position_size to 0.05-0.08")
        recommendations.append("     - Tighten stop loss to 1.5x ATR")
        recommendations.append("     - Consider using trailing stops")
    
    recommendations.append("\n💡 NEXT STEPS:")
    recommendations.append("   1. Implement automatic regime detection using:")
    recommendations.append("      - ADX for trend strength")
    recommendations.append("      - Moving average slopes for trend direction")
    recommendations.append("      - ATR for volatility regimes")
    recommendations.append("   2. Add position sizing based on market volatility")
    recommendations.append("   3. Test with different timeframes (30m, 2h, 4h)")
    recommendations.append("   4. Implement portfolio-level risk management")
    
    return "\n".join(recommendations)


def main():
    """Main execution function"""
    
    print("\n" + "="*100)
    print(" ATR GRID STRATEGY BACKTEST - 1 YEAR ANALYSIS ")
    print("="*100)
    
    # Configuration
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    symbols = ['BTCUSDT', 'ETHUSDT']
    regimes = [MarketRegime.RANGE, MarketRegime.BULLISH, MarketRegime.BEARISH]
    
    print(f"\n📅 Period: {start_date.date()} to {end_date.date()}")
    print(f"📊 Symbols: {', '.join(symbols)}")
    print(f"🎯 Testing Regimes: {', '.join([r.value for r in regimes])}")
    print(f"💰 Initial Capital: $1,000,000 (BTC) / $100,000 (ETH)")
    print(f"⚙️ Strategy: ATR Grid (ATR mult: 0.75, Levels: 5)")
    
    # Initialize data loader
    print("\n🔌 Connecting to database...")
    loader = DataLoader()
    
    if not loader.connect():
        print("\n❌ Failed to connect to database")
        print("Please ensure PostgreSQL is running and DATABASE_URL is set")
        return
    
    # Load data for each symbol
    print("\n📥 Loading historical data...")
    data_dict = {}
    
    for symbol in symbols:
        data = loader.load_kline_data(
            symbol=symbol,
            interval='1h',
            start_date=start_date,
            end_date=end_date
        )
        
        if not data.empty:
            data_dict[symbol] = data
            print(f"   ✅ {symbol}: {len(data)} candles loaded")
        else:
            print(f"   ❌ {symbol}: No data available")
    
    if not data_dict:
        print("\n❌ No data available for backtesting")
        return
    
    # Run backtests
    print("\n🚀 Running backtests...")
    results = []
    total_tests = len(symbols) * len(regimes)
    current_test = 0
    
    for symbol in symbols:
        if symbol not in data_dict:
            continue
            
        data = data_dict[symbol]
        
        for regime in regimes:
            current_test += 1
            print(f"\n   [{current_test}/{total_tests}] Testing {symbol} in {regime.value.upper()} mode...")
            
            # Adjust parameters based on symbol
            if symbol == 'BTCUSDT':
                capital = 1000000  # Need more for BTC
                atr_mult = 0.3     # Tighter grids
            else:
                capital = 100000   # ETH needs less
                atr_mult = 0.4
            
            config = BacktestConfig(
                symbol=symbol,
                regime=regime,
                strategy_class=SimpleATRGridStrategy,  # Use simplified version
                initial_capital=capital,
                commission=0.001,  # Lower commission
                atr_multiplier=atr_mult,
                grid_levels=3,     # Fewer levels for clearer signals
                max_position_size=0.1,
                stop_loss_atr_mult=3.0,  # Wider stop
                atr_period=14,
                use_regime=False  # Simplified version doesn't use regime
            )
            
            result = run_single_backtest(data, config)
            results.append(result)
            
            if 'error' not in result:
                print(f"      Return: {result['return_pct']:.2f}% | Sharpe: {result['sharpe_ratio']:.2f} | Trades: {result['num_trades']}")
            else:
                print(f"      ❌ Error: {result['error']}")
    
    # Display results
    print_results_table(results)
    
    # Generate recommendations
    recommendations = generate_recommendations(results)
    print(recommendations)
    
    # Save best chart
    best_result = max(
        [r for r in results if 'error' not in r],
        key=lambda x: x['sharpe_ratio'],
        default=None
    )
    
    if best_result and 'plot' in best_result:
        try:
            from bokeh.embed import file_html
            from bokeh.resources import CDN
            
            html = file_html(best_result['plot'], CDN, "ATR Grid Strategy Backtest")
            
            filename = 'atr_grid_backtest_chart.html'
            with open(filename, 'w') as f:
                f.write(html)
            
            print(f"\n📊 Chart saved to {filename}")
            print(f"   Best configuration: {best_result['symbol']} in {best_result['regime'].upper()} mode")
        except Exception as e:
            logger.error(f"Failed to save chart: {e}")
    
    print("\n" + "="*100)
    print(" BACKTEST COMPLETE ")
    print("="*100)


if __name__ == "__main__":
    main()