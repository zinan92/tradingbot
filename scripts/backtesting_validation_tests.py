#!/usr/bin/env python3
"""
Comprehensive Backtesting Validation Test Suite

10 different end-to-end backtesting scenarios testing various strategies,
timeframes, and market conditions.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from tabulate import tabulate
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Import backtesting components
from src.infrastructure.backtesting.backtest_engine import BacktestEngine, BacktestResults
from src.infrastructure.backtesting.data_adapter import DataAdapter
from src.application.backtesting.strategies.ema_cross_strategy import EMACrossStrategy
from src.application.backtesting.strategies.rsi_strategy import RSIStrategy
from src.application.backtesting.strategies.macd_strategy import MACDStrategy
from src.application.backtesting.strategies.sma_cross_strategy import SmaCrossStrategy

# Database connection
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@dataclass
class BacktestScenario:
    """Configuration for a backtest scenario"""
    name: str
    description: str
    symbol: str
    strategy_class: type
    strategy_params: Dict[str, Any]
    interval: str
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000
    commission: float = 0.001
    expected_metrics: Dict[str, Any] = None


class BacktestingValidationTests:
    """
    Comprehensive backtesting validation test suite
    """
    
    def __init__(self, database_url: str = None):
        """Initialize the test suite"""
        self.database_url = database_url or os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
        self.engine = create_engine(self.database_url)
        Session = sessionmaker(bind=self.engine)
        self.db_session = Session()
        
        # Initialize components
        self.backtest_engine = BacktestEngine()
        # Configure DataAdapter to use REAL database connection
        self.data_adapter = DataAdapter({
            'host': 'localhost',
            'port': 5432,
            'database': 'tradingbot',
            'user': None,  # Will use current user
            'password': None
        })
        
        # Store test results
        self.test_results = []
        self.failed_tests = []
        
    def test_1_bitcoin_ema_crossing(self) -> Dict:
        """Test 1: Bitcoin EMA crossing 5-minute backtest for past 5 months"""
        scenario = BacktestScenario(
            name="Bitcoin EMA Crossing",
            description="EMA 12/26 crossover on 5-minute data",
            symbol="BTCUSDT",
            strategy_class=EMACrossStrategy,
            strategy_params={
                'fast_period': 12,
                'slow_period': 26,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.05
            },
            interval="5m",
            start_date=datetime.now() - timedelta(days=150),
            end_date=datetime.now(),
            initial_capital=1000000,  # Increased for Bitcoin prices
            commission=0.001
        )
        
        return self._run_backtest(scenario)
    
    def test_2_ethereum_rsi_oversold(self) -> Dict:
        """Test 2: Ethereum RSI oversold/overbought strategy on 1-hour data for 3 months"""
        scenario = BacktestScenario(
            name="Ethereum RSI Mean Reversion",
            description="RSI-based mean reversion on hourly data",
            symbol="ETHUSDT",
            strategy_class=RSIStrategy,
            strategy_params={
                'rsi_period': 14,
                'oversold_level': 30,
                'overbought_level': 70,
                'exit_on_neutral': True
            },
            interval="1h",
            start_date=datetime.now() - timedelta(days=90),
            end_date=datetime.now(),
            initial_capital=10000,
            commission=0.001
        )
        
        return self._run_backtest(scenario)
    
    def test_3_solana_macd_divergence(self) -> Dict:
        """Test 3: Solana MACD divergence on 15-minute data for 1 month"""
        scenario = BacktestScenario(
            name="Solana MACD Divergence",
            description="MACD signal crossover with histogram confirmation",
            symbol="SOLUSDT",
            strategy_class=MACDStrategy,
            strategy_params={
                'fast_period': 12,
                'slow_period': 26,
                'signal_period': 9,
                'use_histogram': True,
                'use_divergence': True
            },
            interval="15m",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
            initial_capital=10000,
            commission=0.001
        )
        
        return self._run_backtest(scenario)
    
    def test_4_multi_symbol_mean_reversion(self) -> Dict:
        """Test 4: Multi-symbol mean reversion on 4-hour data for 6 months"""
        # Run backtests for multiple symbols
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        results = []
        
        for symbol in symbols:
            scenario = BacktestScenario(
                name=f"Mean Reversion - {symbol}",
                description="RSI mean reversion across multiple symbols",
                symbol=symbol,
                strategy_class=RSIStrategy,
                strategy_params={
                    'rsi_period': 21,
                    'oversold_level': 25,
                    'overbought_level': 75,
                    'use_trend_filter': True
                },
                interval="4h",
                start_date=datetime.now() - timedelta(days=180),
                end_date=datetime.now(),
                initial_capital=10000,
                commission=0.001
            )
            
            result = self._run_backtest(scenario)
            results.append(result)
        
        # Aggregate results
        total_return = np.mean([r['metrics'].get('return_pct', 0) for r in results])
        avg_sharpe = np.mean([r['metrics'].get('sharpe_ratio', 0) for r in results])
        total_trades = sum([r['metrics'].get('total_trades', 0) for r in results])
        
        return {
            'passed': all(r['passed'] for r in results),
            'metrics': {
                'symbols_tested': len(symbols),
                'avg_return_pct': f"{total_return:.2f}",
                'avg_sharpe_ratio': f"{avg_sharpe:.2f}",
                'total_trades': total_trades,
                'individual_results': results
            },
            'details': f"Multi-symbol mean reversion backtest for {', '.join(symbols)}"
        }
    
    def test_5_bnb_grid_trading(self) -> Dict:
        """Test 5: BNB Grid Trading with ATR on 1-hour data for 2 months"""
        # Use SMA cross as proxy for grid trading (grid strategy not yet implemented)
        scenario = BacktestScenario(
            name="BNB Grid Trading Simulation",
            description="Grid-like trading using SMA crossovers",
            symbol="BNBUSDT",
            strategy_class=SmaCrossStrategy,
            strategy_params={
                'n1': 5,
                'n2': 20,
                'stop_loss_pct': 0.01,
                'take_profit_pct': 0.02
            },
            interval="1h",
            start_date=datetime.now() - timedelta(days=60),
            end_date=datetime.now(),
            initial_capital=10000,
            commission=0.001
        )
        
        return self._run_backtest(scenario)
    
    def test_6_xrp_volume_breakout(self) -> Dict:
        """Test 6: XRP Volume Breakout on daily data for 1 year"""
        # Use EMA cross with volume filter as proxy for volume breakout
        scenario = BacktestScenario(
            name="XRP Volume Breakout",
            description="Volume-filtered trend following",
            symbol="XRPUSDT",
            strategy_class=EMACrossStrategy,
            strategy_params={
                'fast_period': 20,
                'slow_period': 50,
                'use_volume_filter': True,
                'volume_threshold': 70  # 70th percentile
            },
            interval="1d",
            start_date=datetime.now() - timedelta(days=365),
            end_date=datetime.now(),
            initial_capital=10000,
            commission=0.001
        )
        
        return self._run_backtest(scenario)
    
    def test_7_avax_bollinger_bands(self) -> Dict:
        """Test 7: AVAX Bollinger Bands Squeeze on 30-minute data for 45 days"""
        # Use RSI with tight levels as proxy for BB squeeze
        scenario = BacktestScenario(
            name="AVAX Bollinger Bands Simulation",
            description="Volatility expansion trading",
            symbol="AVAXUSDT",
            strategy_class=RSIStrategy,
            strategy_params={
                'rsi_period': 20,
                'oversold_level': 35,
                'overbought_level': 65,
                'use_divergence': True
            },
            interval="30m",
            start_date=datetime.now() - timedelta(days=45),
            end_date=datetime.now(),
            initial_capital=10000,
            commission=0.001
        )
        
        return self._run_backtest(scenario)
    
    def test_8_link_futures_momentum(self) -> Dict:
        """Test 8: LINK Futures Momentum on 2-hour data for 3 months"""
        scenario = BacktestScenario(
            name="LINK Futures Momentum",
            description="Momentum strategy with leverage simulation",
            symbol="LINKUSDT",
            strategy_class=MACDStrategy,
            strategy_params={
                'fast_period': 8,
                'slow_period': 21,
                'signal_period': 5,
                'use_histogram': True,
                'exit_on_signal_cross': True
            },
            interval="2h",
            start_date=datetime.now() - timedelta(days=90),
            end_date=datetime.now(),
            initial_capital=10000,
            commission=0.002  # Higher commission for futures
        )
        
        return self._run_backtest(scenario)
    
    def test_9_portfolio_rotation(self) -> Dict:
        """Test 9: Portfolio Rotation Strategy on daily data for 2 years"""
        # Test multiple symbols with different strategies
        portfolio_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
        results = []
        
        for symbol in portfolio_symbols:
            # Use different strategy parameters for each symbol
            scenario = BacktestScenario(
                name=f"Portfolio - {symbol}",
                description="Portfolio rotation component",
                symbol=symbol,
                strategy_class=SmaCrossStrategy,
                strategy_params={
                    'n1': 20,
                    'n2': 50,
                    'stop_loss_pct': 0.03,
                    'position_size': 0.2  # 20% allocation per symbol
                },
                interval="1d",
                start_date=datetime.now() - timedelta(days=730),
                end_date=datetime.now(),
                initial_capital=10000,
                commission=0.001
            )
            
            result = self._run_backtest(scenario)
            results.append(result)
        
        # Calculate portfolio metrics
        portfolio_return = np.mean([r['metrics'].get('return_pct', 0) for r in results])
        best_performer = max(results, key=lambda x: x['metrics'].get('return_pct', 0))
        worst_performer = min(results, key=lambda x: x['metrics'].get('return_pct', 0))
        
        return {
            'passed': len([r for r in results if r['passed']]) >= 3,  # At least 3 successful
            'metrics': {
                'portfolio_size': len(portfolio_symbols),
                'portfolio_return_pct': f"{portfolio_return:.2f}",
                'best_performer': best_performer.get('symbol', 'N/A'),
                'worst_performer': worst_performer.get('symbol', 'N/A'),
                'successful_symbols': len([r for r in results if r['passed']])
            },
            'details': f"Portfolio rotation test with {len(portfolio_symbols)} symbols"
        }
    
    def test_10_btc_risk_adjusted_grid(self) -> Dict:
        """Test 10: BTCUSDT Risk-Adjusted Grid on 4-hour data for 90 days"""
        scenario = BacktestScenario(
            name="BTC Risk-Adjusted Grid",
            description="Grid trading with dynamic position sizing",
            symbol="BTCUSDT",
            strategy_class=EMACrossStrategy,
            strategy_params={
                'fast_period': 9,
                'slow_period': 21,
                'stop_loss_pct': 0.015,  # Tighter stop loss
                'take_profit_pct': 0.03,  # Smaller take profit
                'position_size': 0.5,  # Conservative position sizing
                'trailing_stop_pct': 0.02  # Trailing stop
            },
            interval="4h",
            start_date=datetime.now() - timedelta(days=90),
            end_date=datetime.now(),
            initial_capital=1000000,  # Increased for Bitcoin prices
            commission=0.001
        )
        
        return self._run_backtest(scenario)
    
    def _run_backtest(self, scenario: BacktestScenario) -> Dict:
        """Run a single backtest scenario"""
        try:
            print(f"\nRunning: {scenario.name}")
            print(f"Symbol: {scenario.symbol}, Interval: {scenario.interval}")
            
            # Load data - use fetch_ohlcv or fetch_from_database
            data = self.data_adapter.fetch_from_database(
                symbol=scenario.symbol,
                interval=scenario.interval,
                start_date=scenario.start_date,
                end_date=scenario.end_date
            )
            
            if data.empty or len(data) < 100:
                return {
                    'passed': False,
                    'symbol': scenario.symbol,
                    'metrics': {},
                    'details': f"Insufficient data: {len(data)} candles",
                    'error': 'Insufficient data'
                }
            
            print(f"Loaded {len(data)} candles")
            
            # Run backtest
            results = self.backtest_engine.run_backtest(
                data=data,
                strategy_class=scenario.strategy_class,
                initial_cash=scenario.initial_capital,
                commission=scenario.commission,
                **scenario.strategy_params
            )
            
            # Extract key metrics
            stats = results.stats
            metrics = {
                'return_pct': float(stats.get('Return [%]', 0)),
                'sharpe_ratio': float(stats.get('Sharpe Ratio', 0)),
                'max_drawdown_pct': float(stats.get('Max. Drawdown [%]', 0)),
                'total_trades': int(stats.get('# Trades', 0)),
                'win_rate_pct': float(stats.get('Win Rate [%]', 0)),
                'profit_factor': float(stats.get('Profit Factor', 0)),
                'cagr_pct': float(stats.get('CAGR [%]', 0)),
                'volatility_pct': float(stats.get('Volatility (Ann.) [%]', 0))
            }
            
            # Validate results
            passed = self._validate_results(metrics, scenario)
            
            return {
                'passed': passed,
                'symbol': scenario.symbol,
                'metrics': metrics,
                'details': scenario.description,
                'trades': len(results.trades),
                'start_date': scenario.start_date.strftime('%Y-%m-%d'),
                'end_date': scenario.end_date.strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            print(f"Error in backtest: {e}")
            return {
                'passed': False,
                'symbol': scenario.symbol,
                'metrics': {},
                'details': scenario.description,
                'error': str(e)
            }
    
    def _validate_results(self, metrics: Dict, scenario: BacktestScenario) -> bool:
        """Validate backtest results"""
        # Basic validation criteria
        validations = []
        
        # Must have executed trades
        validations.append(metrics.get('total_trades', 0) > 0)
        
        # Sharpe ratio should be calculated
        validations.append(not np.isnan(metrics.get('sharpe_ratio', np.nan)))
        
        # Max drawdown should be reasonable
        validations.append(metrics.get('max_drawdown_pct', -100) > -50)
        
        # Win rate should be between 0 and 100
        win_rate = metrics.get('win_rate_pct', -1)
        validations.append(0 <= win_rate <= 100)
        
        # If we have expected metrics, validate against them
        if scenario.expected_metrics:
            for key, expected_value in scenario.expected_metrics.items():
                actual_value = metrics.get(key)
                if actual_value is not None:
                    # Allow 20% deviation from expected
                    if isinstance(expected_value, (int, float)):
                        validations.append(
                            abs(actual_value - expected_value) / abs(expected_value) < 0.2
                        )
        
        return all(validations)
    
    def run_all_tests(self):
        """Run all backtesting validation tests"""
        print("=" * 80)
        print("COMPREHENSIVE BACKTESTING VALIDATION TEST SUITE")
        print("=" * 80)
        print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Define all tests
        tests = [
            self.test_1_bitcoin_ema_crossing,
            self.test_2_ethereum_rsi_oversold,
            self.test_3_solana_macd_divergence,
            self.test_4_multi_symbol_mean_reversion,
            self.test_5_bnb_grid_trading,
            self.test_6_xrp_volume_breakout,
            self.test_7_avax_bollinger_bands,
            self.test_8_link_futures_momentum,
            self.test_9_portfolio_rotation,
            self.test_10_btc_risk_adjusted_grid
        ]
        
        # Run each test
        for i, test_func in enumerate(tests, 1):
            print("=" * 80)
            print(f"Test {i}: {test_func.__doc__.split(':')[1].strip()}")
            print("=" * 80)
            
            result = test_func()
            self.test_results.append(result)
            
            # Display results
            status = "✅ PASSED" if result['passed'] else "❌ FAILED"
            print(f"\nStatus: {status}")
            print(f"Details: {result['details']}")
            
            if 'metrics' in result and result['metrics']:
                print("\nMetrics:")
                for key, value in result['metrics'].items():
                    if key != 'individual_results':  # Skip nested results
                        print(f"  {key}: {value}")
            
            if result.get('error'):
                print(f"Error: {result['error']}")
                self.failed_tests.append(i)
        
        # Display summary
        self._display_summary()
    
    def _display_summary(self):
        """Display test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['passed']])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        print("\nDetailed Results:")
        print("-" * 80)
        
        # Create summary table
        table_data = []
        for i, result in enumerate(self.test_results, 1):
            status = "✅ PASSED" if result['passed'] else "❌ FAILED"
            symbol = result.get('symbol', 'Multiple')
            
            # Get key metric
            metrics = result.get('metrics', {})
            return_pct = metrics.get('return_pct', metrics.get('avg_return_pct', 'N/A'))
            trades = metrics.get('total_trades', 'N/A')
            
            table_data.append([
                i,
                result.get('details', '')[:40] + '...',
                status,
                symbol,
                f"{return_pct}%" if isinstance(return_pct, (int, float)) else return_pct,
                trades
            ])
        
        headers = ['#', 'Test Name', 'Status', 'Symbol', 'Return %', 'Trades']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))
        
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if success_rate == 100:
            print("\n✅ All tests passed successfully!")
        elif failed_tests > 0:
            print(f"\n⚠️ {failed_tests} test(s) failed. Please review the results.")


def main():
    """Main entry point"""
    # Create and run test suite
    test_suite = BacktestingValidationTests()
    
    try:
        test_suite.run_all_tests()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        test_suite.db_session.close()


if __name__ == "__main__":
    main()