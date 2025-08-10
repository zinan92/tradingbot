#!/usr/bin/env python3
"""
Generate comprehensive backtest summary with key metrics
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from tabulate import tabulate

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.backtesting_validation_tests import BacktestingValidationTests


def generate_backtest_summary():
    """Generate comprehensive backtest summary"""
    
    print("=" * 100)
    print("COMPREHENSIVE BACKTEST SUMMARY - REAL DATA")
    print("=" * 100)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Data Source: PostgreSQL Database (Real Market Data)")
    
    # Run all tests
    test_suite = BacktestingValidationTests()
    
    # Collect results
    results = []
    
    # Test 1: Bitcoin EMA Crossing
    test1 = test_suite.test_1_bitcoin_ema_crossing()
    results.append({
        'Test': 'BTC EMA Cross (5m)',
        'Symbol': 'BTCUSDT',
        'Strategy': 'EMA 12/26 Crossover',
        'Period': '5 months',
        'Return %': f"{test1['metrics'].get('return_pct', 0):.2f}%",
        'Max DD %': f"{test1['metrics'].get('max_drawdown_pct', 0):.2f}%",
        'Sharpe': f"{test1['metrics'].get('sharpe_ratio', 0):.2f}",
        'Trades': test1['metrics'].get('total_trades', 0),
        'Win Rate': f"{test1['metrics'].get('win_rate_pct', 0):.1f}%"
    })
    
    # Test 2: Ethereum RSI
    test2 = test_suite.test_2_ethereum_rsi_oversold()
    results.append({
        'Test': 'ETH RSI (1h)',
        'Symbol': 'ETHUSDT',
        'Strategy': 'RSI Mean Reversion',
        'Period': '3 months',
        'Return %': f"{test2['metrics'].get('return_pct', 0):.2f}%",
        'Max DD %': f"{test2['metrics'].get('max_drawdown_pct', 0):.2f}%",
        'Sharpe': f"{test2['metrics'].get('sharpe_ratio', 0):.2f}",
        'Trades': test2['metrics'].get('total_trades', 0),
        'Win Rate': f"{test2['metrics'].get('win_rate_pct', 0):.1f}%"
    })
    
    # Test 3: Solana MACD
    test3 = test_suite.test_3_solana_macd_divergence()
    results.append({
        'Test': 'SOL MACD (15m)',
        'Symbol': 'SOLUSDT',
        'Strategy': 'MACD Divergence',
        'Period': '1 month',
        'Return %': f"{test3['metrics'].get('return_pct', 0):.2f}%",
        'Max DD %': f"{test3['metrics'].get('max_drawdown_pct', 0):.2f}%",
        'Sharpe': f"{test3['metrics'].get('sharpe_ratio', 0):.2f}",
        'Trades': test3['metrics'].get('total_trades', 0),
        'Win Rate': f"{test3['metrics'].get('win_rate_pct', 0):.1f}%"
    })
    
    # Test 5: BNB Grid Trading
    test5 = test_suite.test_5_bnb_grid_trading()
    results.append({
        'Test': 'BNB Grid (1h)',
        'Symbol': 'BNBUSDT',
        'Strategy': 'Grid Trading',
        'Period': '2 months',
        'Return %': f"{test5['metrics'].get('return_pct', 0):.2f}%",
        'Max DD %': f"{test5['metrics'].get('max_drawdown_pct', 0):.2f}%",
        'Sharpe': f"{test5['metrics'].get('sharpe_ratio', 0):.2f}",
        'Trades': test5['metrics'].get('total_trades', 0),
        'Win Rate': f"{test5['metrics'].get('win_rate_pct', 0):.1f}%"
    })
    
    # Test 6: XRP Volume
    test6 = test_suite.test_6_xrp_volume_breakout()
    results.append({
        'Test': 'XRP Volume (1d)',
        'Symbol': 'XRPUSDT',
        'Strategy': 'Volume Breakout',
        'Period': '1 year',
        'Return %': f"{test6['metrics'].get('return_pct', 0):.2f}%",
        'Max DD %': f"{test6['metrics'].get('max_drawdown_pct', 0):.2f}%",
        'Sharpe': f"{test6['metrics'].get('sharpe_ratio', 0):.2f}",
        'Trades': test6['metrics'].get('total_trades', 0),
        'Win Rate': f"{test6['metrics'].get('win_rate_pct', 0):.1f}%"
    })
    
    # Test 7: AVAX Bollinger
    test7 = test_suite.test_7_avax_bollinger_bands()
    results.append({
        'Test': 'AVAX BB (30m)',
        'Symbol': 'AVAXUSDT',
        'Strategy': 'Bollinger Bands',
        'Period': '45 days',
        'Return %': f"{test7['metrics'].get('return_pct', 0):.2f}%",
        'Max DD %': f"{test7['metrics'].get('max_drawdown_pct', 0):.2f}%",
        'Sharpe': f"{test7['metrics'].get('sharpe_ratio', 0):.2f}",
        'Trades': test7['metrics'].get('total_trades', 0),
        'Win Rate': f"{test7['metrics'].get('win_rate_pct', 0):.1f}%"
    })
    
    # Test 8: LINK Momentum
    test8 = test_suite.test_8_link_futures_momentum()
    results.append({
        'Test': 'LINK Momentum (2h)',
        'Symbol': 'LINKUSDT',
        'Strategy': 'Momentum + Leverage',
        'Period': '3 months',
        'Return %': f"{test8['metrics'].get('return_pct', 0):.2f}%",
        'Max DD %': f"{test8['metrics'].get('max_drawdown_pct', 0):.2f}%",
        'Sharpe': f"{test8['metrics'].get('sharpe_ratio', 0):.2f}",
        'Trades': test8['metrics'].get('total_trades', 0),
        'Win Rate': f"{test8['metrics'].get('win_rate_pct', 0):.1f}%"
    })
    
    # Test 10: BTC Risk Grid
    test10 = test_suite.test_10_btc_risk_adjusted_grid()
    results.append({
        'Test': 'BTC Risk Grid (4h)',
        'Symbol': 'BTCUSDT',
        'Strategy': 'Conservative Grid',
        'Period': '90 days',
        'Return %': f"{test10['metrics'].get('return_pct', 0):.2f}%",
        'Max DD %': f"{test10['metrics'].get('max_drawdown_pct', 0):.2f}%",
        'Sharpe': f"{test10['metrics'].get('sharpe_ratio', 0):.2f}",
        'Trades': test10['metrics'].get('total_trades', 0),
        'Win Rate': f"{test10['metrics'].get('win_rate_pct', 0):.1f}%"
    })
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    print("\n" + "=" * 100)
    print("BACKTEST RESULTS SUMMARY")
    print("=" * 100)
    
    # Display table
    print(tabulate(df, headers='keys', tablefmt='grid', showindex=True))
    
    # Calculate overall statistics
    print("\n" + "=" * 100)
    print("PERFORMANCE STATISTICS")
    print("=" * 100)
    
    # Parse numeric values for statistics
    returns = []
    drawdowns = []
    sharpes = []
    trades = []
    
    for r in results:
        ret = float(r['Return %'].replace('%', ''))
        dd = float(r['Max DD %'].replace('%', ''))
        sharpe = float(r['Sharpe'])
        trade_count = int(r['Trades'])
        
        returns.append(ret)
        drawdowns.append(dd)
        sharpes.append(sharpe)
        trades.append(trade_count)
    
    print(f"\n📊 RETURN STATISTICS:")
    print(f"  Best Return:        {max(returns):.2f}% ({results[returns.index(max(returns))]['Test']})")
    print(f"  Worst Return:       {min(returns):.2f}% ({results[returns.index(min(returns))]['Test']})")
    print(f"  Average Return:     {sum(returns)/len(returns):.2f}%")
    print(f"  Positive Returns:   {len([r for r in returns if r > 0])}/8")
    
    print(f"\n📉 DRAWDOWN STATISTICS:")
    print(f"  Best (Smallest) DD: {max(drawdowns):.2f}% ({results[drawdowns.index(max(drawdowns))]['Test']})")
    print(f"  Worst (Largest) DD: {min(drawdowns):.2f}% ({results[drawdowns.index(min(drawdowns))]['Test']})")
    print(f"  Average Drawdown:   {sum(drawdowns)/len(drawdowns):.2f}%")
    
    print(f"\n📈 SHARPE RATIO STATISTICS:")
    print(f"  Best Sharpe:        {max(sharpes):.2f} ({results[sharpes.index(max(sharpes))]['Test']})")
    print(f"  Worst Sharpe:       {min(sharpes):.2f} ({results[sharpes.index(min(sharpes))]['Test']})")
    print(f"  Average Sharpe:     {sum(sharpes)/len(sharpes):.2f}")
    print(f"  Positive Sharpe:    {len([s for s in sharpes if s > 0])}/8")
    
    print(f"\n🎯 TRADING ACTIVITY:")
    print(f"  Most Active:        {max(trades)} trades ({results[trades.index(max(trades))]['Test']})")
    print(f"  Least Active:       {min(trades)} trades ({results[trades.index(min(trades))]['Test']})")
    print(f"  Total Trades:       {sum(trades)}")
    print(f"  Average Trades:     {sum(trades)/len(trades):.0f}")
    
    print("\n" + "=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100)
    
    # Identify best strategies
    profitable = [results[i] for i, r in enumerate(returns) if r > 0]
    if profitable:
        print(f"\n✅ PROFITABLE STRATEGIES ({len(profitable)}):")
        for p in profitable:
            print(f"  • {p['Test']}: {p['Return %']} return, {p['Max DD %']} max DD, {p['Sharpe']} Sharpe")
    
    # Identify strategies needing improvement
    unprofitable = [results[i] for i, r in enumerate(returns) if r < -10]
    if unprofitable:
        print(f"\n⚠️ STRATEGIES NEEDING OPTIMIZATION ({len(unprofitable)}):")
        for u in unprofitable:
            print(f"  • {u['Test']}: {u['Return %']} return, {u['Max DD %']} max DD")
    
    print("\n" + "=" * 100)
    
    return results


if __name__ == "__main__":
    results = generate_backtest_summary()