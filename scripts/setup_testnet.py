#!/usr/bin/env python3
"""
Binance Testnet Setup Script

This script helps you set up and test your trading system on Binance Testnet
before risking real money.

Steps:
1. Create testnet account
2. Get API credentials
3. Test connectivity
4. Run paper trading
"""

import os
import sys
import json
import yaml
import asyncio
from pathlib import Path
from datetime import datetime
import requests

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(text.center(60))
    print("=" * 60)


def setup_testnet():
    """Guide user through testnet setup"""
    
    print_header("BINANCE TESTNET SETUP")
    
    print("""
This script will help you set up Binance Testnet for safe testing.

IMPORTANT: Always test on testnet first before using real money!
    """)
    
    # Step 1: Create testnet account
    print("\n📝 STEP 1: Create Testnet Account")
    print("-" * 40)
    print("""
1. Go to: https://testnet.binancefuture.com/
2. Register with your email
3. You'll receive 100,000 USDT test funds automatically
    """)
    
    input("\nPress Enter when you've created your testnet account...")
    
    # Step 2: Get API credentials
    print("\n🔑 STEP 2: Get API Credentials")
    print("-" * 40)
    print("""
1. Log into testnet account
2. Go to API Management
3. Create a new API key
4. Save your API Key and Secret securely
    """)
    
    api_key = input("\nEnter your Testnet API Key: ").strip()
    api_secret = input("Enter your Testnet API Secret: ").strip()
    
    if not api_key or not api_secret:
        print("❌ API credentials are required")
        return False
    
    # Step 3: Test connectivity
    print("\n🔌 STEP 3: Testing Connectivity")
    print("-" * 40)
    
    if test_connectivity(api_key, api_secret):
        print("✅ Successfully connected to Binance Testnet!")
    else:
        print("❌ Failed to connect. Please check your credentials.")
        return False
    
    # Step 4: Update configuration
    print("\n⚙️ STEP 4: Updating Configuration")
    print("-" * 40)
    
    config_path = Path("config/live_trading_config.yaml")
    
    if update_config(config_path, api_key, api_secret):
        print("✅ Configuration updated successfully!")
    else:
        print("⚠️  Please update config/live_trading_config.yaml manually")
    
    # Step 5: Run test trade
    print("\n🎯 STEP 5: Test Trade Simulation")
    print("-" * 40)
    
    print("""
Ready to run a test trade simulation!
This will:
1. Connect to testnet
2. Fetch market data
3. Run BNB Grid Strategy in dry-run mode
4. Show you what would happen without placing real orders
    """)
    
    response = input("\nRun test simulation? (yes/no): ")
    if response.lower() == 'yes':
        run_test_simulation()
    
    print_header("SETUP COMPLETE")
    
    print("""
✅ Testnet setup complete!

Next steps:
1. Run paper trading for a few days:
   python scripts/start_live_trading.py --testnet

2. Monitor the logs:
   tail -f logs/live_trading.log

3. Once comfortable, you can move to production:
   - Get real Binance API keys
   - Update config with production credentials
   - Start with small capital ($100-500)
   - Monitor closely!

⚠️  IMPORTANT REMINDERS:
- Never share your API keys
- Always use stop losses
- Start with minimum position sizes
- Monitor your first trades closely
- Have an emergency plan
    """)
    
    return True


def test_connectivity(api_key, api_secret):
    """Test connection to Binance testnet"""
    try:
        import hmac
        import hashlib
        from urllib.parse import urlencode
        
        base_url = "https://testnet.binancefuture.com"
        
        # Test public endpoint first
        response = requests.get(f"{base_url}/fapi/v1/ping")
        if response.status_code != 200:
            print("Cannot reach testnet API")
            return False
        
        # Test authenticated endpoint
        endpoint = "/fapi/v2/account"
        timestamp = int(datetime.now().timestamp() * 1000)
        
        params = {
            'timestamp': timestamp,
            'recvWindow': 5000
        }
        
        query_string = urlencode(params)
        signature = hmac.new(
            api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        params['signature'] = signature
        
        headers = {
            'X-MBX-APIKEY': api_key
        }
        
        response = requests.get(
            f"{base_url}{endpoint}",
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            balance = next((b for b in data.get('assets', []) if b['asset'] == 'USDT'), None)
            if balance:
                print(f"✅ Account balance: {balance['walletBalance']} USDT (testnet)")
            return True
        else:
            print(f"Authentication failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"Connection error: {e}")
        return False


def update_config(config_path, api_key, api_secret):
    """Update configuration file with testnet credentials"""
    try:
        # Load existing config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update testnet credentials
        config['binance']['testnet']['api_key'] = api_key
        config['binance']['testnet']['api_secret'] = api_secret
        
        # Ensure testnet mode is enabled
        config['mode']['environment'] = 'testnet'
        config['mode']['dry_run'] = True
        
        # Set conservative initial capital
        config['capital']['initial_capital'] = 1000  # $1000 test funds
        
        # Save updated config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        return True
        
    except Exception as e:
        print(f"Error updating config: {e}")
        return False


def run_test_simulation():
    """Run a quick test simulation"""
    try:
        print("\n🚀 Running test simulation...")
        print("-" * 40)
        
        # Import components
        from src.infrastructure.binance_client import BinanceClient
        from src.application.trading.strategies.live_grid_strategy import LiveGridStrategy
        
        # Load config
        config_path = Path("config/live_trading_config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize strategy
        strategy = LiveGridStrategy(
            symbol="BNBUSDT",
            grid_levels=5,  # Fewer levels for test
            grid_spacing=0.005
        )
        
        print("Strategy: Grid Trading")
        print("Symbol: BNBUSDT")
        print("Grid Levels: 5")
        print("Grid Spacing: 0.5%")
        
        # Simulate grid creation
        current_price = 650.0  # Example BNB price
        capital = 1000.0
        
        buy_grid, sell_grid = strategy.calculate_grid_levels(current_price, capital)
        
        print(f"\nSimulated Grid (at price ${current_price:.2f}):")
        print("\nBuy Orders:")
        for i, level in enumerate(buy_grid[:3], 1):
            print(f"  {i}. ${level.price:.2f} - Qty: {level.quantity:.4f}")
        
        print("\nSell Orders:")
        for i, level in enumerate(sell_grid[:3], 1):
            print(f"  {i}. ${level.price:.2f} - Qty: {level.quantity:.4f}")
        
        print("\n✅ Simulation complete! Grid strategy is ready.")
        print("In live trading, these orders would be placed automatically.")
        
    except Exception as e:
        print(f"Simulation error: {e}")
        print("This is normal if dependencies aren't fully set up yet.")


def check_requirements():
    """Check if all requirements are installed"""
    print("\n📦 Checking Requirements")
    print("-" * 40)
    
    required_packages = [
        'pandas',
        'numpy',
        'sqlalchemy',
        'psycopg2-binary',
        'pyyaml',
        'websocket-client',
        'requests',
        'python-dotenv',
        'backtesting',
        'bokeh',
        'tabulate'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (missing)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        return False
    
    print("\n✅ All requirements installed!")
    return True


def main():
    """Main entry point"""
    print_header("BINANCE TESTNET SETUP WIZARD")
    
    print("""
Welcome to the Binance Testnet Setup Wizard!

This will help you:
✅ Set up a testnet account
✅ Configure API credentials
✅ Test connectivity
✅ Run a simulation

Let's ensure everything is safe before trading real money.
    """)
    
    # Check requirements first
    if not check_requirements():
        print("\n⚠️  Please install missing requirements first")
        sys.exit(1)
    
    # Run setup
    if setup_testnet():
        print("\n🎉 Setup successful! You're ready for testnet trading.")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()