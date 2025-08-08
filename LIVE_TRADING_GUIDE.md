# Live Trading Deployment Guide

## 🚀 Quick Start

### Prerequisites
1. Python 3.8+
2. PostgreSQL (optional, can use in-memory for testing)
3. Binance account with API access
4. Backtested strategy (we're using OptimalGridStrategy)

### Step 1: Configure API Keys

1. Edit the `.env` file:
```bash
nano .env
```

2. Add your Binance API credentials:
```env
# For Testnet (recommended for initial testing)
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_API_SECRET=your_testnet_api_secret

# For Mainnet (real trading)
BINANCE_API_KEY=your_mainnet_api_key
BINANCE_API_SECRET=your_mainnet_api_secret
```

**⚠️ IMPORTANT**: 
- Start with TESTNET first!
- Get testnet keys from: https://testnet.binancefuture.com/
- Never commit your API keys to git

### Step 2: Configure Trading Parameters

Edit `.env` to set your risk parameters:

```env
# Start Conservative
TRADING_MODE=TESTNET           # Use TESTNET first!
MAX_LEVERAGE=3                  # Low leverage
MAX_POSITION_SIZE_USDT=100     # Small position size
DAILY_LOSS_LIMIT_USDT=50       # Strict loss limit
```

### Step 3: Deploy the System

```bash
# One-command deployment
./deploy.sh start
```

This will:
- Install dependencies
- Set up directories
- Start the API server
- Launch live trading

### Step 4: Monitor Trading

#### Via Web Interface
Open: http://localhost:8000/docs

Key endpoints:
- `POST /api/v1/live-trading/session/start` - Start trading
- `GET /api/v1/live-trading/positions` - View positions
- `GET /api/v1/live-trading/session/status` - Check status
- `POST /api/v1/live-trading/emergency-stop` - Emergency stop

#### Via Command Line
```bash
# Check status
./deploy.sh status

# View live logs
./deploy.sh logs trading

# View API logs
./deploy.sh logs api
```

## 📊 Trading Strategy

The system is configured with **OptimalGridStrategy**:
- Uses ATR-based dynamic grid levels
- Buys below midpoint, sells above
- 5 grid levels on each side
- 2% take profit, 5% stop loss

## 🛡️ Safety Features

1. **Pre-Trade Risk Validation**
   - Leverage limits
   - Position size limits
   - Daily loss limits
   - Margin checks

2. **State Recovery**
   - Automatic state saving every 60 seconds
   - Crash recovery on restart
   - Session persistence

3. **Emergency Controls**
   - Emergency stop endpoint
   - Graceful shutdown
   - Position closing on stop

## 🔧 Management Commands

### Start Trading
```bash
./deploy.sh start
```

### Stop Trading
```bash
./deploy.sh stop
```

### Restart Services
```bash
./deploy.sh restart
```

### Check Status
```bash
./deploy.sh status
```

## 📈 Testing Workflow

### 1. Testnet Testing (Recommended First)
```bash
# Set in .env
TRADING_MODE=TESTNET
TRADING_ENABLED=true
AUTO_EXECUTE_SIGNALS=true

# Start
./deploy.sh start

# Monitor for 24-48 hours
./deploy.sh logs trading
```

### 2. Paper Trading (Optional)
```bash
# Set in .env
TRADING_MODE=PAPER

# No real orders, just simulation
./deploy.sh start
```

### 3. Mainnet (Real Money)
```bash
# Set in .env
TRADING_MODE=MAINNET
MAX_POSITION_SIZE_USDT=1000  # Increase gradually

# Start with caution
./deploy.sh start
```

## 🔍 Monitoring Checklist

Monitor these metrics:
- [ ] Win rate > 40%
- [ ] Daily PnL within limits
- [ ] No repeated errors in logs
- [ ] Positions closing properly
- [ ] Grid levels updating daily

## 🚨 Troubleshooting

### API Keys Not Working
```bash
# Test connection
curl -X GET "https://testnet.binancefuture.com/fapi/v1/time"
```

### Database Connection Issues
```bash
# Set to false for in-memory
USE_POSTGRES=false
```

### Strategy Not Generating Signals
Check:
1. `AUTO_EXECUTE_SIGNALS=true`
2. Market is open
3. Price is within grid range
4. Sufficient margin available

### Emergency Stop
```bash
# Via API
curl -X POST http://localhost:8000/api/v1/live-trading/emergency-stop \
  -H "Content-Type: application/json" \
  -d '{"close_positions": true, "reason": "Manual intervention"}'

# Via script
./deploy.sh stop
```

## 📝 Configuration Reference

### Risk Parameters
| Parameter | Conservative | Moderate | Aggressive |
|-----------|-------------|----------|------------|
| MAX_LEVERAGE | 3x | 10x | 20x |
| POSITION_SIZE | 1% | 2% | 5% |
| DAILY_LOSS | 2% | 5% | 10% |
| MAX_POSITIONS | 3 | 5 | 10 |

### Grid Strategy Parameters
| Parameter | Description | Default |
|-----------|-------------|---------|
| GRID_ATR_PERIOD | ATR calculation period | 14 |
| GRID_LEVELS | Levels per side | 5 |
| GRID_ATR_MULTIPLIER | Range multiplier | 1.0 |
| GRID_TAKE_PROFIT_PCT | Take profit % | 2% |
| GRID_STOP_LOSS_PCT | Stop loss % | 5% |

## 🎯 Next Steps

1. **Test on Testnet** for at least 48 hours
2. **Review performance** metrics
3. **Adjust parameters** based on results
4. **Gradually increase** position sizes
5. **Switch to mainnet** only when confident

## ⚠️ Disclaimer

**IMPORTANT**: 
- Trading involves risk of loss
- Start with small amounts
- Never trade money you can't afford to lose
- Past performance doesn't guarantee future results
- Always use stop losses

## 📞 Support

- Logs: `./logs/trading_YYYYMMDD.log`
- State: `./trading_state/`
- API Docs: http://localhost:8000/docs

---

**Ready to trade? Start with:**
```bash
./deploy.sh start
```

Good luck and trade safely! 🚀