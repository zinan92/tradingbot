"""
Demo script for Grid Trading Strategy backtesting

This script demonstrates how to run the grid trading strategy
with historical market data and analyze the results.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Import backtest components
from src.infrastructure.backtesting.futures_backtest_engine import FuturesBacktestEngine
from src.application.backtesting.strategies.futures_grid_strategy import (
    FuturesGridStrategy,
    GridMode
)
from src.infrastructure.market_data.bulk_data_loader import BulkDataLoader

# Load environment variables
load_dotenv()


async def load_sample_data():
    """Load sample market data for backtesting"""
    
    # Database connection
    db_url = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/trading_db')
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    
    with SessionLocal() as session:
        loader = BulkDataLoader(session)
        
        # Load BTC/USDT 5m data for grid trading (good for volatility)
        print("Loading market data...")
        data = await loader.load_kline_data(
            symbol='BTCUSDT',
            interval='5m',
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now()
        )
        
        if data.empty:
            # Generate synthetic data for demo if no real data
            print("No data found, generating synthetic data...")
            data = generate_synthetic_data()
        
        return data


def generate_synthetic_data():
    """Generate synthetic ranging market data ideal for grid trading"""
    
    # Create ranging market with volatility
    dates = pd.date_range(end=datetime.now(), periods=8640, freq='5min')  # 30 days of 5m data
    
    # Base price with mean reversion
    base_price = 50000
    prices = []
    current_price = base_price
    
    for i in range(len(dates)):
        # Add mean reversion
        mean_reversion = (base_price - current_price) * 0.001
        
        # Add random walk with bounds
        random_move = np.random.randn() * 0.002 * base_price
        
        # Add some volatility cycles
        volatility = np.sin(i / 100) * 0.01 * base_price
        
        current_price = current_price + mean_reversion + random_move + volatility
        
        # Keep price in range (good for grid trading)
        current_price = max(base_price * 0.9, min(base_price * 1.1, current_price))
        prices.append(current_price)
    
    # Create OHLCV data
    df = pd.DataFrame(index=dates)
    df['Close'] = prices
    
    # Generate OHLV from close
    df['Open'] = df['Close'].shift(1).fillna(df['Close'])
    df['High'] = df[['Open', 'Close']].max(axis=1) * (1 + np.random.rand(len(df)) * 0.002)
    df['Low'] = df[['Open', 'Close']].min(axis=1) * (1 - np.random.rand(len(df)) * 0.002)
    df['Volume'] = np.random.rand(len(df)) * 1000000 + 500000
    
    return df


def run_grid_backtest():
    """Run backtest with different grid configurations"""
    
    print("\n" + "="*60)
    print("GRID TRADING STRATEGY BACKTEST")
    print("="*60)
    
    # Load or generate data
    data = asyncio.run(load_sample_data())
    
    if data is None or data.empty:
        data = generate_synthetic_data()
    
    print(f"\nData loaded: {len(data)} candles")
    print(f"Date range: {data.index[0]} to {data.index[-1]}")
    print(f"Price range: ${data['Low'].min():.2f} - ${data['High'].max():.2f}")
    
    # Initialize backtest engine
    engine = FuturesBacktestEngine()
    
    # Test different grid configurations
    configurations = [
        {
            'name': 'Conservative Grid',
            'params': {
                'grid_levels': 5,
                'grid_spacing_pct': 1.0,
                'leverage': 3,
                'position_per_grid': 0.1,
                'take_profit_grids': 2
            }
        },
        {
            'name': 'Aggressive Grid',
            'params': {
                'grid_levels': 15,
                'grid_spacing_pct': 0.3,
                'leverage': 10,
                'position_per_grid': 0.05,
                'take_profit_grids': 1
            }
        },
        {
            'name': 'Adaptive Grid',
            'params': {
                'grid_levels': 10,
                'grid_spacing_pct': 0.5,
                'leverage': 5,
                'grid_mode': GridMode.ADAPTIVE,
                'trailing_grid': True,
                'pyramid_mode': True
            }
        }
    ]
    
    results = []
    
    for config in configurations:
        print(f"\n\nTesting: {config['name']}")
        print("-" * 40)
        
        try:
            # Run backtest
            result = engine.run_backtest(
                data=data,
                strategy_class=FuturesGridStrategy,
                initial_cash=10000,
                commission=0.0004,  # 0.04% futures commission
                margin=1/config['params'].get('leverage', 5),
                **config['params']
            )
            
            # Store results
            results.append({
                'name': config['name'],
                'result': result,
                'params': config['params']
            })
            
            # Print key metrics
            stats = result.stats
            print(f"Total Return: {stats.get('Return [%]', 0):.2f}%")
            print(f"Sharpe Ratio: {stats.get('Sharpe Ratio', 0):.2f}")
            print(f"Max Drawdown: {stats.get('Max. Drawdown [%]', 0):.2f}%")
            print(f"Win Rate: {stats.get('Win Rate [%]', 0):.2f}%")
            print(f"Total Trades: {stats.get('# Trades', 0)}")
            
            # Get strategy-specific metrics if available
            if hasattr(result, 'strategy_metrics'):
                metrics = result.strategy_metrics
                print(f"Grid Fill Rate: {metrics.get('fill_rate', 0):.2%}")
                print(f"Avg Trade Profit: ${metrics.get('avg_trade_profit', 0):.2f}")
            
        except Exception as e:
            print(f"Error running backtest: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Compare results
    if results:
        print("\n\n" + "="*60)
        print("COMPARISON OF STRATEGIES")
        print("="*60)
        
        comparison_df = pd.DataFrame([
            {
                'Strategy': r['name'],
                'Return %': r['result'].stats.get('Return [%]', 0),
                'Sharpe': r['result'].stats.get('Sharpe Ratio', 0),
                'Drawdown %': r['result'].stats.get('Max. Drawdown [%]', 0),
                'Trades': r['result'].stats.get('# Trades', 0),
                'Win Rate %': r['result'].stats.get('Win Rate [%]', 0),
            }
            for r in results
        ])
        
        print(comparison_df.to_string(index=False))
        
        # Find best configuration
        best_sharpe = max(results, key=lambda x: x['result'].stats.get('Sharpe Ratio', 0))
        best_return = max(results, key=lambda x: x['result'].stats.get('Return [%]', 0))
        
        print(f"\n📊 Best Sharpe Ratio: {best_sharpe['name']}")
        print(f"💰 Best Total Return: {best_return['name']}")
        
        # Save the best result chart
        if best_sharpe['result'].chart_html:
            with open('grid_backtest_chart.html', 'w') as f:
                f.write(best_sharpe['result'].chart_html)
            print("\n✅ Chart saved to grid_backtest_chart.html")
    
    print("\n" + "="*60)
    print("BACKTEST COMPLETE")
    print("="*60)


def run_optimization():
    """Optimize grid parameters"""
    
    print("\n" + "="*60)
    print("GRID STRATEGY PARAMETER OPTIMIZATION")
    print("="*60)
    
    # Load data
    data = asyncio.run(load_sample_data())
    if data is None or data.empty:
        data = generate_synthetic_data()
    
    # Initialize backtest engine
    engine = FuturesBacktestEngine()
    
    print("\nOptimizing grid parameters...")
    print("This may take a few minutes...")
    
    try:
        # Define parameter ranges to optimize
        param_ranges = {
            'grid_levels': range(5, 20, 5),           # 5, 10, 15
            'grid_spacing_pct': [0.3, 0.5, 0.75, 1.0],  # Different spacings
            'take_profit_grids': range(1, 4),         # 1, 2, 3 grids
            'leverage': [3, 5, 8, 10],                # Different leverages
        }
        
        # Run optimization
        best_params, all_results = engine.optimize(
            data=data,
            strategy_class=FuturesGridStrategy,
            initial_cash=10000,
            commission=0.0004,
            maximize='Sharpe Ratio',  # Or 'Return [%]', 'Win Rate [%]'
            **param_ranges
        )
        
        print("\n" + "="*40)
        print("OPTIMIZATION RESULTS")
        print("="*40)
        
        print(f"\n📈 Best Parameters:")
        print(f"Grid Levels: {best_params._strategy.grid_levels}")
        print(f"Grid Spacing: {best_params._strategy.grid_spacing_pct}%")
        print(f"Take Profit Grids: {best_params._strategy.take_profit_grids}")
        print(f"Leverage: {best_params._strategy.leverage}x")
        
        print(f"\n📊 Performance:")
        print(f"Sharpe Ratio: {best_params['Sharpe Ratio']:.2f}")
        print(f"Total Return: {best_params['Return [%]']:.2f}%")
        print(f"Max Drawdown: {best_params['Max. Drawdown [%]']:.2f}%")
        print(f"Total Trades: {best_params['# Trades']}")
        
    except Exception as e:
        print(f"Error during optimization: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--optimize':
        run_optimization()
    else:
        run_grid_backtest()
    
    print("\n✅ Demo complete!")
    print("Run with --optimize flag to optimize parameters")