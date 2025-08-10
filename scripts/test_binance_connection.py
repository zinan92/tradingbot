#!/usr/bin/env python3
"""
Test Binance API Connection

Quick script to verify your API keys are working correctly.
Always test with testnet first!
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
import ccxt
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

def test_connection(testnet=True):
    """Test connection to Binance"""
    
    # Load environment variables
    load_dotenv()
    
    print("=" * 60)
    print(f"🔌 Testing Binance {'TESTNET' if testnet else 'PRODUCTION'} Connection")
    print("=" * 60)
    
    # Get API credentials
    if testnet:
        api_key = os.getenv('BINANCE_TESTNET_API_KEY')
        api_secret = os.getenv('BINANCE_TESTNET_API_SECRET')
        exchange_id = 'binance'
        
        if not api_key or api_key == 'YOUR_TESTNET_KEY_HERE':
            print("❌ TESTNET API keys not configured!")
            print("\n📝 How to fix:")
            print("1. Go to https://testnet.binancefuture.com/")
            print("2. Create API keys")
            print("3. Add to .env file:")
            print("   BINANCE_TESTNET_API_KEY=your_key")
            print("   BINANCE_TESTNET_API_SECRET=your_secret")
            return False
            
        # Configure for testnet
        exchange_config = {
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'sandboxMode': True
            }
        }
        
        # Testnet URLs
        exchange_config['urls'] = {
            'api': {
                'public': 'https://testnet.binancefuture.com',
                'private': 'https://testnet.binancefuture.com',
                'v1': 'https://testnet.binancefuture.com',
                'v2': 'https://testnet.binancefuture.com',
            }
        }
        
    else:
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        exchange_id = 'binance'
        
        if not api_key or api_key == 'YOUR_PRODUCTION_API_KEY_HERE':
            print("❌ PRODUCTION API keys not configured!")
            print("\n⚠️  WARNING: Only use production after testing on testnet!")
            print("\n📝 How to fix:")
            print("1. Go to https://www.binance.com/en/my/settings/api-management")
            print("2. Create API keys with trading permissions")
            print("3. Add to .env file:")
            print("   BINANCE_API_KEY=your_key")
            print("   BINANCE_API_SECRET=your_secret")
            return False
            
        exchange_config = {
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        }
    
    try:
        # Create exchange instance
        print(f"\n🔄 Connecting to Binance {'Testnet' if testnet else 'Production'}...")
        exchange = ccxt.binance(exchange_config)
        
        # Test 1: Fetch account balance
        print("\n📊 Fetching account information...")
        balance = exchange.fetch_balance()
        
        print("✅ Successfully connected to Binance!")
        print(f"   Environment: {'TESTNET' if testnet else 'PRODUCTION'}")
        print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Show USDT balance
        usdt_balance = balance.get('USDT', {})
        if usdt_balance:
            print(f"\n💰 USDT Balance:")
            print(f"   Free: {usdt_balance.get('free', 0):.2f} USDT")
            print(f"   Used: {usdt_balance.get('used', 0):.2f} USDT")
            print(f"   Total: {usdt_balance.get('total', 0):.2f} USDT")
            
            if testnet and usdt_balance.get('total', 0) == 0:
                print("\n💡 Tip: Get free testnet USDT from the testnet faucet!")
        
        # Test 2: Fetch ticker
        print("\n📈 Testing market data access...")
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"✅ BTC/USDT Price: ${ticker['last']:,.2f}")
        
        # Test 3: Check trading permissions
        print("\n🔑 Checking API permissions...")
        try:
            # Try to fetch open orders (requires trading permission)
            orders = exchange.fetch_open_orders('BTC/USDT')
            print("✅ Trading permissions: ENABLED")
            print(f"   Open orders: {len(orders)}")
        except Exception as e:
            if 'Invalid API' in str(e):
                print("⚠️  Trading permissions: DISABLED (read-only mode)")
                print("   This is fine for monitoring, but you need trading permissions to place orders")
            else:
                print(f"⚠️  Could not verify trading permissions: {str(e)[:100]}")
        
        # Test 4: Network latency
        print("\n⚡ Testing network latency...")
        import time
        start = time.time()
        exchange.fetch_time()
        latency = (time.time() - start) * 1000
        print(f"✅ Latency: {latency:.1f}ms")
        
        if latency > 1000:
            print("   ⚠️  High latency detected. Consider using a VPS closer to Binance servers.")
        
        print("\n" + "=" * 60)
        print("🎉 All tests passed! Your API connection is working.")
        print("=" * 60)
        
        if testnet:
            print("\n📌 Next steps:")
            print("1. Try paper trading: python scripts/start_live_trading.py --testnet")
            print("2. Monitor with dashboard: streamlit run dashboard/app.py")
            print("3. After successful testing, switch to production carefully")
        else:
            print("\n⚠️  PRODUCTION MODE - Real money at risk!")
            print("Start with small amounts and monitor closely.")
        
        return True
        
    except ccxt.NetworkError as e:
        print(f"\n❌ Network Error: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Check your internet connection")
        print("2. Verify Binance is not under maintenance")
        print("3. Try again in a few seconds")
        return False
        
    except ccxt.AuthenticationError as e:
        print(f"\n❌ Authentication Error: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Check your API keys in .env file")
        print("2. Ensure no extra spaces or quotes")
        print("3. Verify keys on Binance website")
        print("4. Check IP whitelist if enabled")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        print("\n🔧 Please check:")
        print("1. Your .env file has correct keys")
        print("2. You're using the right environment (testnet vs production)")
        print("3. Check logs for more details")
        return False

def main():
    parser = argparse.ArgumentParser(description='Test Binance API Connection')
    parser.add_argument('--testnet', action='store_true', 
                      help='Test testnet connection (default)')
    parser.add_argument('--production', action='store_true',
                      help='Test production connection (use carefully!)')
    
    args = parser.parse_args()
    
    # Default to testnet if nothing specified
    if not args.production:
        args.testnet = True
    
    # Safety check
    if args.production:
        print("⚠️  WARNING: Testing PRODUCTION connection with real money!")
        response = input("Are you sure? (type 'yes' to continue): ")
        if response.lower() != 'yes':
            print("Cancelled. Good choice - always test with testnet first!")
            return
    
    # Check for ccxt
    try:
        import ccxt
    except ImportError:
        print("Installing required package: ccxt...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ccxt"])
        import ccxt
    
    # Run test
    success = test_connection(testnet=args.testnet)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()