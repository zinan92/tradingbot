#!/usr/bin/env python3
"""
Analyze Optimal Grid Strategy Results
Understand why BTC improved but ETH didn't
"""

import pandas as pd
import numpy as np
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def analyze_trades(symbol):
    """Analyze trades for a specific symbol"""
    
    # Update path to look in outputs/trades folder
    filename = os.path.join(project_root, "outputs", "trades", f"{symbol.lower()}_optimal_grid_trades.csv")
    
    if not os.path.exists(filename):
        print(f"❌ No trades file found for {symbol}")
        return None
    
    trades = pd.read_csv(filename)
    
    print(f"\n{'='*80}")
    print(f"{symbol} - OPTIMAL GRID ANALYSIS")
    print('='*80)
    
    # Basic statistics
    total_trades = len(trades)
    winning_trades = (trades['PnL'] > 0).sum()
    losing_trades = (trades['PnL'] < 0).sum()
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    print(f"\n📊 Trade Statistics:")
    print("-"*40)
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {winning_trades} ({win_rate:.1f}%)")
    print(f"Losing Trades: {losing_trades}")
    
    # P&L Analysis
    total_pnl = trades['PnL'].sum()
    avg_pnl = trades['PnL'].mean()
    best_trade = trades['PnL'].max()
    worst_trade = trades['PnL'].min()
    
    avg_win = trades[trades['PnL'] > 0]['PnL'].mean() if winning_trades > 0 else 0
    avg_loss = trades[trades['PnL'] < 0]['PnL'].mean() if losing_trades > 0 else 0
    risk_reward = abs(avg_win/avg_loss) if avg_loss != 0 else 0
    
    print(f"\n💰 P&L Analysis:")
    print("-"*40)
    print(f"Total P&L: ${total_pnl:,.2f}")
    print(f"Average P&L: ${avg_pnl:,.2f}")
    print(f"Best Trade: ${best_trade:,.2f}")
    print(f"Worst Trade: ${worst_trade:,.2f}")
    print(f"Average Win: ${avg_win:,.2f}")
    print(f"Average Loss: ${avg_loss:,.2f}")
    print(f"Risk/Reward Ratio: {risk_reward:.2f}")
    
    # Position distribution
    if 'Size' in trades.columns:
        long_trades = (trades['Size'] > 0).sum()
        short_trades = (trades['Size'] < 0).sum()
        print(f"\n📈 Position Distribution:")
        print("-"*40)
        print(f"Long Trades: {long_trades} ({long_trades/total_trades*100:.1f}%)")
        print(f"Short Trades: {short_trades} ({short_trades/total_trades*100:.1f}%)")
    
    # Duration analysis
    if 'Duration' in trades.columns:
        durations = pd.to_timedelta(trades['Duration'])
        avg_duration = durations.mean()
        print(f"\n⏱️ Average Duration: {avg_duration}")
    
    # Return percentage analysis
    if 'ReturnPct' in trades.columns:
        avg_return_pct = trades['ReturnPct'].mean() * 100
        print(f"Average Return %: {avg_return_pct:.3f}%")
    
    # Sample trades
    print(f"\n📋 Sample Trades (First 5 and Last 5):")
    print("-"*80)
    display_cols = ['EntryTime', 'EntryPrice', 'ExitPrice', 'Size', 'PnL']
    display_cols = [col for col in display_cols if col in trades.columns]
    
    if display_cols and len(trades) > 0:
        print("First 5:")
        first_5 = trades[display_cols].head()
        for col in ['EntryPrice', 'ExitPrice', 'PnL']:
            if col in first_5.columns:
                first_5[col] = first_5[col].round(2)
        print(first_5.to_string(index=False))
        
        if len(trades) > 5:
            print("\nLast 5:")
            last_5 = trades[display_cols].tail()
            for col in ['EntryPrice', 'ExitPrice', 'PnL']:
                if col in last_5.columns:
                    last_5[col] = last_5[col].round(2)
            print(last_5.to_string(index=False))
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'risk_reward': risk_reward
    }


def compare_strategies():
    """Compare optimal grid with 4-hour ATR"""
    
    print("\n" + "="*80)
    print("STRATEGY COMPARISON ANALYSIS")
    print("="*80)
    
    # Results from the backtest
    results = {
        'BTCUSDT': {
            'Optimal': {'Return': -5.07, 'Trades': 269, 'WinRate': 66.54},
            '4H_ATR': {'Return': -23.93, 'Trades': 340, 'WinRate': 53.82}
        },
        'ETHUSDT': {
            'Optimal': {'Return': -48.83, 'Trades': 396, 'WinRate': 63.38},
            '4H_ATR': {'Return': -11.60, 'Trades': 346, 'WinRate': 56.94}
        }
    }
    
    print("\n🔍 Why Different Results for BTC vs ETH?")
    print("-"*60)
    
    print("""
1. **Bitcoin (Better with Optimal Grid):**
   - Optimal: -5.07% return, 66.54% win rate ✅
   - 4H ATR: -23.93% return, 53.82% win rate
   - Improvement: +18.85%
   
   Why it worked:
   • Higher win rate (66% vs 54%)
   • Midpoint rule prevented bad entries
   • Daily range updates caught volatility changes
   • Fewer trades = lower fees

2. **Ethereum (Worse with Optimal Grid):**
   - Optimal: -48.83% return, 63.38% win rate ❌
   - 4H ATR: -11.60% return, 56.94% win rate
   - Decline: -37.23%
   
   Why it struggled:
   • More trades (396 vs 346) = higher fees
   • ETH's higher volatility may exceed daily ATR range
   • Grid levels might be too tight for ETH
   • Take profit (2%) may be too small for ETH volatility

3. **Key Differences:**
   • BTC volatility: ~2% daily (matches 2% TP)
   • ETH volatility: ~4% daily (exceeds 2% TP)
   • ETH needs wider grids or larger TP/SL
""")
    
    print("\n💡 Optimization Suggestions:")
    print("-"*60)
    print("""
For Bitcoin:
• Keep current settings (working well)
• Consider tighter stop loss (3% instead of 5%)
• Test with 0.75x ATR range multiplier

For Ethereum:
• Increase take profit to 3-4%
• Use 1.5x ATR range multiplier
• Reduce grid levels to 3 (wider spacing)
• Or switch back to 4H ATR for ETH
""")


def main():
    """Main execution"""
    print("\n" + "="*80)
    print("OPTIMAL GRID STRATEGY - DETAILED ANALYSIS")
    print("="*80)
    
    # Analyze both symbols
    btc_stats = analyze_trades('BTCUSDT')
    eth_stats = analyze_trades('ETHUSDT')
    
    # Compare strategies
    compare_strategies()
    
    # Final recommendations
    print("\n" + "="*80)
    print("FINAL RECOMMENDATIONS")
    print("="*80)
    
    print("""
🎯 Optimal Configuration:

**For BTCUSDT:**
✅ Use Optimal Grid Strategy
• Daily ATR range with midpoint rules
• 5 grid levels, 2% TP, 5% SL
• Expected return: -5% to break-even

**For ETHUSDT:**
✅ Use 4-Hour ATR Strategy
• Better suited for ETH volatility
• Expected return: -11% (near break-even)
• Or adjust Optimal Grid parameters for ETH

**Next Steps:**
1. Implement separate configs for BTC/ETH
2. Add regime detection (BULLISH/BEARISH)
3. Allow human input for daily range
4. Test with different TP/SL ratios
""")


if __name__ == "__main__":
    main()