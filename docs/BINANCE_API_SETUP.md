# 🔑 Binance API Key Setup Guide

## Quick Start

**IMPORTANT:** Your API keys go in the `.env` file, NOT in the YAML config files!

## Where to Put Your API Keys

### ✅ Correct Location: `.env` file
```bash
# Edit the .env file
BINANCE_TESTNET_API_KEY=your_actual_testnet_key
BINANCE_TESTNET_API_SECRET=your_actual_testnet_secret
BINANCE_API_KEY=your_actual_production_key
BINANCE_API_SECRET=your_actual_production_secret
```

### ❌ Wrong Location: `config/live_trading_config.yaml`
The YAML file should keep placeholder values. Your actual keys in `.env` will override these automatically.

## Step-by-Step Setup

### Step 1: Get TESTNET Keys (Start Here!)

1. **Go to Binance Testnet**
   - URL: https://testnet.binancefuture.com/
   - This is a sandbox environment with fake money

2. **Create Account**
   - Register with any email (can be temporary)
   - No KYC required

3. **Generate API Keys**
   - Go to Account → API Management
   - Click "Create API"
   - Give it a label like "TradingBot_Testnet"
   - Save both the API Key and Secret Key

4. **Add to .env file**
   ```bash
   BINANCE_TESTNET_API_KEY=paste_your_testnet_key_here
   BINANCE_TESTNET_API_SECRET=paste_your_testnet_secret_here
   ```

### Step 2: Test Your Connection

```bash
# Test with testnet first
python scripts/test_binance_connection.py --testnet

# You should see:
# ✅ Connected to Binance Testnet
# Account Balance: 10000.00 USDT (testnet funds)
```

### Step 3: Get PRODUCTION Keys (Only After Successful Testing!)

1. **Go to Binance Main Site**
   - URL: https://www.binance.com/en/my/settings/api-management
   - Requires verified account with 2FA

2. **Create API Key**
   - Click "Create API"
   - Label: "TradingBot_Production"
   - Complete 2FA verification

3. **Configure Permissions**
   - ✅ Enable Reading
   - ✅ Enable Futures (if trading futures)
   - ✅ Enable Spot & Margin Trading (if needed)
   - ❌ Disable Withdrawals (for security!)

4. **Set IP Restrictions (HIGHLY RECOMMENDED)**
   - Click "Edit restrictions"
   - Add your server/home IP address
   - This prevents unauthorized access

5. **Add to .env file**
   ```bash
   BINANCE_API_KEY=paste_your_production_key_here
   BINANCE_API_SECRET=paste_your_production_secret_here
   ```

## Security Best Practices

### 🔒 DO's
- ✅ Use `.env` file for API keys
- ✅ Enable IP whitelist on production keys
- ✅ Start with testnet for at least 1 week
- ✅ Use read-only keys initially
- ✅ Keep `.env` in `.gitignore`
- ✅ Rotate keys every 90 days
- ✅ Monitor API usage regularly

### ⛔ DON'Ts
- ❌ Never commit `.env` to git
- ❌ Never share API secrets
- ❌ Never enable withdrawal permissions
- ❌ Never use production keys in testnet mode
- ❌ Never store keys in YAML files
- ❌ Never use same keys on multiple systems

## Testing Your Setup

### 1. Check Environment Variables
```bash
# Verify keys are loaded (hides actual values)
python -c "import os; print('Testnet Key Set:', bool(os.getenv('BINANCE_TESTNET_API_KEY')))"
python -c "import os; print('Production Key Set:', bool(os.getenv('BINANCE_API_KEY')))"
```

### 2. Test Connection Script
Create `test_connection.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Check if keys are loaded
testnet_key = os.getenv('BINANCE_TESTNET_API_KEY')
prod_key = os.getenv('BINANCE_API_KEY')

print(f"Testnet API Key: {'✅ Set' if testnet_key and testnet_key != 'YOUR_TESTNET_KEY_HERE' else '❌ Not Set'}")
print(f"Production API Key: {'✅ Set' if prod_key and prod_key != 'YOUR_PRODUCTION_API_KEY_HERE' else '❌ Not Set'}")
```

### 3. Start Trading Bot
```bash
# Always start with testnet
python scripts/start_live_trading.py --testnet

# Only use production after thorough testing
python scripts/start_live_trading.py --production
```

## How The System Uses Your Keys

1. **Priority Order:**
   - `.env` file (highest priority) ✅
   - `live_trading_config.yaml` (fallback)
   - Default values (will fail)

2. **Automatic Selection:**
   - Testnet mode → Uses `BINANCE_TESTNET_API_KEY`
   - Production mode → Uses `BINANCE_API_KEY`

3. **Code Reference:**
   ```python
   # This is how the system loads keys (start_live_trading.py)
   if os.environ.get('BINANCE_API_KEY'):
       config['binance'][env]['api_key'] = os.environ['BINANCE_API_KEY']
       config['binance'][env]['api_secret'] = os.environ['BINANCE_API_SECRET']
   ```

## Common Issues & Solutions

### Issue: "Invalid API Key"
**Solution:** 
- Check for extra spaces in `.env`
- Ensure you're using correct keys (testnet vs production)
- Verify keys on Binance website

### Issue: "Signature validation failed"
**Solution:**
- Check API Secret is correct
- Ensure system time is synchronized
- Don't mix testnet/production keys

### Issue: "IP not whitelisted"
**Solution:**
- Add your IP to API key restrictions on Binance
- Check your current IP: `curl ifconfig.me`

### Issue: "Insufficient balance"
**Solution:**
- For testnet: Get free test funds from faucet
- For production: Ensure account has USDT

## Trading Progression Path

1. **Week 1-2: Testnet Only**
   - Use testnet keys
   - Test all strategies
   - Verify dashboard works

2. **Week 3-4: Production Read-Only**
   - Use production keys with read-only permissions
   - Monitor real market data
   - No actual trading

3. **Week 5+: Production Trading**
   - Enable trading permissions
   - Start with $100-500
   - Gradually increase as confidence grows

## Emergency Procedures

### If API Keys Are Compromised:
1. **Immediately** go to Binance and delete the API keys
2. Create new keys with new IP restrictions
3. Update `.env` file
4. Check account for unauthorized trades
5. Enable all security features (2FA, anti-phishing, etc.)

### Quick Disable Trading:
```bash
# Emergency stop
echo "TRADING_ENABLED=false" >> .env
pkill -f "start_live_trading.py"
```

## Need Help?

1. **Check logs:** `tail -f logs/live_trading.log`
2. **Test connection:** `python scripts/test_binance_connection.py --testnet`
3. **Verify setup:** `python test_connection.py`
4. **Dashboard status:** `python dashboard_status.py`

---

⚠️ **Remember:** Always start with TESTNET before using real money!