# 🚀 Trading Bot Dashboard - Quick Start Guide

## ✅ Dashboard is Now Running!

Your dashboard is accessible at: **http://localhost:8501**

## 📊 What You Can Do Right Now

### 1. **Live Monitoring** (First Tab)
Currently showing:
- **3 open positions**: BTC (Long), ETH (Long), BNB (Short)
- **Total P&L**: $11.50 unrealized profit
- **Recent trades**: Last 5 executed orders
- **Auto-refresh**: Updates every 5 seconds

### 2. **Deploy Strategy** (Second Tab)
Configure and launch strategies:
- **Grid Trading** ✅ (Currently enabled for BNBUSDT)
- **Momentum Trading** (Available)
- **EMA Cross** (Available)
- **Mean Reversion** (Coming soon)

Current configuration:
- Strategy: Grid
- Symbol: BNBUSDT
- Capital: $500
- Grid Levels: 10
- Grid Spacing: 0.5%

### 3. **Risk Management** (Third Tab)
Monitor and control:
- **Risk Level**: LOW (green)
- **Exposure**: 3 positions open
- **Drawdown**: 0% currently
- **Emergency Controls**: Pause, Stop, Close All

### 4. **Performance History** (Fourth Tab)
View your trading performance:
- 30-day history with sample data
- Cumulative P&L chart
- Win rate trends
- Monthly heatmap

## 🎯 How to Deploy a Strategy

1. **Go to "Deploy Strategy" tab**
2. **Select your strategy type** (Grid recommended)
3. **Choose symbol** (BTCUSDT, ETHUSDT, BNBUSDT, etc.)
4. **Set parameters**:
   - Grid Levels: 10-20 (more = smaller positions)
   - Grid Spacing: 0.3-1% (wider = fewer trades)
   - Capital: Start with $500-1000
5. **Configure risk limits**:
   - Max Daily Loss: 2%
   - Max Drawdown: 10%
   - Emergency Stop: 15%
6. **Select deployment mode**:
   - ✅ Testnet + Dry Run (safest)
   - ⚠️ Production (real money)
7. **Click "Deploy Strategy"**

## 📈 Understanding the Live Monitoring

### P&L Summary Cards
- **Total P&L**: Combined realized + unrealized profit/loss
- **Daily P&L**: Today's performance only
- **Win Rate**: Percentage of profitable trades
- **Open Positions**: Number of active trades

### Position Table Shows
- **Symbol**: Trading pair (BTCUSDT, etc.)
- **Side**: LONG (buy) or SHORT (sell)
- **Entry Price**: Your purchase/sell price
- **Current Price**: Live market price
- **Unrealized P&L**: Profit/loss if closed now
- **P&L %**: Percentage gain/loss

### Color Coding
- 🟢 **Green**: Profitable positions/positive P&L
- 🔴 **Red**: Losing positions/negative P&L
- 🟡 **Yellow**: Warning/caution levels

## ⚠️ Risk Management Controls

### Risk Levels
- **LOW** (0-25%): Normal operation
- **MEDIUM** (25-50%): Monitor closely
- **HIGH** (50-75%): Consider reducing
- **CRITICAL** (75-100%): Immediate action needed

### Emergency Actions
1. **Pause Trading**: Stops new positions, keeps existing
2. **Stop Trading**: Stops all new trades gracefully
3. **Close All**: Immediately closes all positions
4. **EMERGENCY STOP**: Nuclear option - stops everything

## 🔧 Common Operations

### Start Live Trading
```bash
# Terminal 1: Start the trading bot
python scripts/start_live_trading.py --testnet

# Terminal 2: Dashboard is already running
# Open http://localhost:8501
```

### Check System Status
1. Look at sidebar in dashboard
2. Green dot = Trading active
3. Red dot = Trading stopped
4. Check capital and position count

### Modify Strategy Parameters
1. Go to "Deploy Strategy"
2. Adjust parameters
3. Click "Deploy Strategy" to apply changes
4. System will restart with new settings

### Export Performance Data
1. Go to "Performance History"
2. Select time period
3. Click "Export to CSV"
4. Data downloads to your computer

## 📝 Important Notes

### Database Tables Created
- `positions`: Tracks open positions
- `orders`: Records all trades
- `performance_history`: Daily performance metrics

### Sample Data
The dashboard currently shows sample data for demonstration:
- 3 sample positions (BTC, ETH, BNB)
- 5 sample trades
- 30 days of performance history

This will be replaced with real data when you start trading.

### Real Trading Setup
To connect to real trading:
1. Start your trading bot first
2. Ensure API keys are configured
3. Deploy a strategy through dashboard
4. Monitor in Live Monitoring tab

## 🛠️ Troubleshooting

### Dashboard Not Loading
```bash
# Restart dashboard
pkill -f streamlit
streamlit run dashboard/app.py
```

### No Data Showing
```bash
# Check database connection
psql -d tradingbot -c "SELECT COUNT(*) FROM positions;"
```

### Can't Deploy Strategy
- Check config file: `config/live_trading_config.yaml`
- Ensure trading bot is not already running
- Verify API keys are set

## 📞 Next Steps

1. **Explore each tab** to familiarize yourself
2. **Start with testnet** mode for safety
3. **Deploy a Grid strategy** (most tested)
4. **Monitor for 24 hours** before increasing capital
5. **Adjust risk limits** based on comfort level

## 🎉 You're Ready!

The dashboard is fully functional and waiting for you at:
### 👉 http://localhost:8501

Open it in your browser and start exploring!

---

**Remember**: Always start with small amounts on testnet before using real money.