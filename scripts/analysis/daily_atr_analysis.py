#!/usr/bin/env python3
"""
Analyze Daily ATR Grid Strategy Results
Shows why wider grids perform better
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import os


def analyze_trade_patterns():
    """Analyze trade patterns from both strategies"""
    
    print("\n" + "="*80)
    print("DAILY ATR GRID STRATEGY - DETAILED ANALYSIS")
    print("="*80)
    
    # Load trade data
    symbols = ['BTCUSDT', 'ETHUSDT']
    
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"{symbol} TRADE PATTERN ANALYSIS")
        print('='*80)
        
        # Load daily ATR trades if available
        daily_file = f"{symbol.lower()}_daily_atr_trades.csv"
        
        if os.path.exists(daily_file):
            daily_trades = pd.read_csv(daily_file)
            
            if not daily_trades.empty:
                print(f"\n📊 Daily ATR Strategy Statistics:")
                print("-"*40)
                
                # Basic stats
                print(f"Total Trades: {len(daily_trades)}")
                print(f"Profitable Trades: {(daily_trades['PnL'] > 0).sum()}")
                print(f"Losing Trades: {(daily_trades['PnL'] < 0).sum()}")
                
                # P&L analysis
                total_pnl = daily_trades['PnL'].sum()
                avg_win = daily_trades[daily_trades['PnL'] > 0]['PnL'].mean() if (daily_trades['PnL'] > 0).any() else 0
                avg_loss = daily_trades[daily_trades['PnL'] < 0]['PnL'].mean() if (daily_trades['PnL'] < 0).any() else 0
                
                print(f"\nP&L Analysis:")
                print(f"  Total P&L: ${total_pnl:,.2f}")
                print(f"  Average Win: ${avg_win:,.2f}")
                print(f"  Average Loss: ${avg_loss:,.2f}")
                print(f"  Risk/Reward Ratio: {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "  Risk/Reward Ratio: N/A")
                
                # Duration analysis
                if 'Duration' in daily_trades.columns:
                    avg_duration = pd.to_timedelta(daily_trades['Duration']).mean()
                    max_duration = pd.to_timedelta(daily_trades['Duration']).max()
                    min_duration = pd.to_timedelta(daily_trades['Duration']).min()
                    
                    print(f"\nTrade Duration Analysis:")
                    print(f"  Average: {avg_duration}")
                    print(f"  Longest: {max_duration}")
                    print(f"  Shortest: {min_duration}")
                
                # Show sample trades
                print(f"\n📋 Sample Trades (First 5):")
                print("-"*60)
                display_cols = ['EntryTime', 'EntryPrice', 'ExitPrice', 'Size', 'PnL', 'ReturnPct']
                display_cols = [col for col in display_cols if col in daily_trades.columns]
                
                if display_cols:
                    sample = daily_trades[display_cols].head()
                    for col in ['EntryPrice', 'ExitPrice', 'PnL']:
                        if col in sample.columns:
                            sample[col] = sample[col].round(2)
                    if 'ReturnPct' in sample.columns:
                        sample['ReturnPct'] = sample['ReturnPct'].round(4)
                    
                    print(sample.to_string(index=False))
    
    # Calculate and display grid statistics
    print("\n" + "="*80)
    print("GRID SPACING IMPACT ANALYSIS")
    print("="*80)
    
    print("""
📊 Trade Frequency Comparison:
--------------------------------
1-Hour ATR:
  - BTCUSDT: 926 trades (2.5 trades/day average)
  - ETHUSDT: 882 trades (2.4 trades/day average)
  - Problem: Overtrading, high transaction costs

1-Day ATR:
  - BTCUSDT: 69 trades (0.19 trades/day average)
  - ETHUSDT: 70 trades (0.19 trades/day average)
  - Benefit: Selective entries, lower costs

📈 Return Improvement:
----------------------
BTCUSDT: +9.52% improvement (-53.19% → -43.68%)
ETHUSDT: +23.26% improvement (-86.88% → -63.62%)

🎯 Why Daily ATR Works Better:
------------------------------
1. **Wider Grid Spacing:**
   - 1-Hour: ~$350-500 spacing (0.3-0.4% moves)
   - 1-Day: ~$2,500-3,000 spacing (2-3% moves)
   - Result: Grid doesn't trigger on noise

2. **Better Risk Management:**
   - Wider stop losses (2x daily ATR = 4-5% moves)
   - More room for price to reverse
   - Avoids premature stop-outs

3. **Trend Resistance:**
   - Doesn't accumulate positions quickly in trends
   - Time for trend exhaustion between entries
   - Better capital preservation

4. **Trade Quality:**
   - Each trade represents a more significant move
   - Higher conviction entries
   - Better risk/reward setups

📉 Remaining Challenges:
------------------------
- Still negative returns (grid trading struggles in strong trends)
- Need trend filters or regime detection
- Consider adaptive grid sizing based on volatility
""")


def calculate_optimal_parameters():
    """Calculate optimal parameters for daily ATR strategy"""
    
    print("\n" + "="*80)
    print("OPTIMAL PARAMETER RECOMMENDATIONS")
    print("="*80)
    
    # Based on current daily ATR values
    btc_daily_atr = 2463.21
    eth_daily_atr = 177.99
    
    btc_price = 115588.80
    eth_price = 3787.08
    
    print("\n📊 Current Market Conditions:")
    print("-"*40)
    print(f"BTC: ${btc_price:,.2f} | Daily ATR: ${btc_daily_atr:.2f} ({btc_daily_atr/btc_price*100:.2f}%)")
    print(f"ETH: ${eth_price:,.2f} | Daily ATR: ${eth_daily_atr:.2f} ({eth_daily_atr/eth_price*100:.2f}%)")
    
    print("\n🎯 Recommended Parameters for Daily ATR Grid:")
    print("-"*50)
    
    # Conservative settings
    print("\nConservative (Lower Risk):")
    print("  - ATR Multiplier: 0.75")
    print("  - Grid Levels: 3")
    print("  - Take Profit: 1.5x ATR")
    print("  - Stop Loss: 3.0x ATR")
    print(f"  - BTC Grid Range: ${btc_daily_atr * 0.75 * 3:,.0f}")
    print(f"  - ETH Grid Range: ${eth_daily_atr * 0.75 * 3:,.0f}")
    
    # Balanced settings
    print("\nBalanced (Current):")
    print("  - ATR Multiplier: 0.5")
    print("  - Grid Levels: 5")
    print("  - Take Profit: 1.0x ATR")
    print("  - Stop Loss: 2.0x ATR")
    print(f"  - BTC Grid Range: ${btc_daily_atr * 0.5 * 5:,.0f}")
    print(f"  - ETH Grid Range: ${eth_daily_atr * 0.5 * 5:,.0f}")
    
    # Aggressive settings
    print("\nAggressive (Higher Risk/Reward):")
    print("  - ATR Multiplier: 0.4")
    print("  - Grid Levels: 7")
    print("  - Take Profit: 0.75x ATR")
    print("  - Stop Loss: 1.5x ATR")
    print(f"  - BTC Grid Range: ${btc_daily_atr * 0.4 * 7:,.0f}")
    print(f"  - ETH Grid Range: ${eth_daily_atr * 0.4 * 7:,.0f}")
    
    print("\n💡 Additional Recommendations:")
    print("-"*40)
    print("""
1. **Add Trend Filter:**
   - Disable grid in strong trends (ADX > 30)
   - Use 50-day MA as trend reference
   - Only trade in ranging markets

2. **Volatility Adjustment:**
   - Increase multiplier when ATR is low
   - Decrease multiplier when ATR is high
   - Dynamic adjustment formula: multiplier = base * (avg_atr / current_atr)

3. **Position Sizing:**
   - Risk only 1-2% per grid level
   - Scale position size with volatility
   - Keep total exposure under 10%

4. **Time Filters:**
   - Avoid major news events
   - Consider trading sessions (Asia/Europe/US)
   - Weekend gap protection
""")


if __name__ == "__main__":
    analyze_trade_patterns()
    calculate_optimal_parameters()