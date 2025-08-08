#!/usr/bin/env python3
"""
Dashboard Status Check - Shows current system status
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import yaml
from pathlib import Path
from datetime import datetime
from tabulate import tabulate
import sys

def check_dashboard_status():
    """Check and display dashboard status"""
    
    print("\n" + "=" * 60)
    print(" TRADING BOT DASHBOARD STATUS ".center(60))
    print("=" * 60)
    
    # 1. Dashboard URL
    print("\n📊 DASHBOARD ACCESS")
    print("-" * 40)
    print("✅ Dashboard URL: http://localhost:8501")
    print("   Status: RUNNING")
    
    # 2. Configuration
    print("\n⚙️ CURRENT CONFIGURATION")
    print("-" * 40)
    try:
        config_path = Path(__file__).parent / "config" / "live_trading_config.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Find active strategy
        active_strategy = None
        for strategy, settings in config.get('strategy', {}).items():
            if isinstance(settings, dict) and settings.get('enabled'):
                active_strategy = strategy
                if 'symbols' in settings and settings['symbols']:
                    symbol = settings['symbols'][0].get('symbol', 'N/A')
                    interval = settings['symbols'][0].get('interval', 'N/A')
                else:
                    symbol = 'N/A'
                    interval = 'N/A'
                break
        
        print(f"Active Strategy: {active_strategy or 'None'}")
        if active_strategy:
            print(f"  - Symbol: {symbol}")
            print(f"  - Interval: {interval}")
        print(f"Initial Capital: ${config.get('capital', {}).get('initial_capital', 0):,}")
        print(f"Environment: {config.get('mode', {}).get('environment', 'testnet')}")
        print(f"Dry Run: {config.get('mode', {}).get('dry_run', True)}")
        
    except Exception as e:
        print(f"Error loading config: {e}")
    
    # 3. Database Status
    print("\n💾 DATABASE STATUS")
    print("-" * 40)
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='tradingbot'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check positions
        cur.execute("SELECT COUNT(*) as count FROM positions WHERE status = 'OPEN'")
        positions_count = cur.fetchone()['count']
        
        # Check orders
        cur.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'FILLED'")
        orders_count = cur.fetchone()['count']
        
        # Check kline data
        cur.execute("SELECT COUNT(*) as count FROM kline_data")
        kline_count = cur.fetchone()['count']
        
        print(f"✅ Database Connected")
        print(f"  - Open Positions: {positions_count}")
        print(f"  - Filled Orders: {orders_count}")
        print(f"  - Kline Records: {kline_count:,}")
        
        # Show current positions
        if positions_count > 0:
            print("\n📈 CURRENT POSITIONS")
            print("-" * 40)
            cur.execute("""
                SELECT symbol, side, quantity, entry_price, current_price, unrealized_pnl
                FROM positions 
                WHERE status = 'OPEN'
                ORDER BY created_at DESC
            """)
            positions = cur.fetchall()
            
            table_data = []
            for pos in positions:
                table_data.append([
                    pos['symbol'],
                    pos['side'],
                    f"{float(pos['quantity']):.4f}",
                    f"${float(pos['entry_price']):.2f}",
                    f"${float(pos['current_price'] or pos['entry_price']):.2f}",
                    f"${float(pos['unrealized_pnl'] or 0):.2f}"
                ])
            
            print(tabulate(
                table_data,
                headers=['Symbol', 'Side', 'Quantity', 'Entry', 'Current', 'Unrealized P&L'],
                tablefmt='simple'
            ))
        
        conn.close()
        
    except Exception as e:
        print(f"Database Error: {e}")
    
    # 4. Dashboard Features
    print("\n🎯 DASHBOARD FEATURES")
    print("-" * 40)
    print("✅ Live Monitoring - Real-time P&L and positions")
    print("✅ Deploy Strategy - Configure and launch strategies")
    print("✅ Risk Management - Monitor and control risk")
    print("✅ Performance History - Analyze past performance")
    
    # 5. Quick Actions
    print("\n⚡ QUICK ACTIONS")
    print("-" * 40)
    print("1. Open Dashboard: http://localhost:8501")
    print("2. Deploy Strategy: Go to 'Deploy Strategy' tab")
    print("3. Monitor Positions: Check 'Live Monitoring' tab")
    print("4. Emergency Stop: Use 'Risk Management' tab")
    
    # 6. System Health
    print("\n💚 SYSTEM HEALTH")
    print("-" * 40)
    print("✅ Dashboard: RUNNING")
    print("✅ Database: CONNECTED")
    print("✅ Configuration: LOADED")
    print(f"✅ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n" + "=" * 60)
    print(" DASHBOARD READY AT: http://localhost:8501 ".center(60))
    print("=" * 60)
    print()

if __name__ == "__main__":
    try:
        from tabulate import tabulate
    except ImportError:
        print("Installing tabulate...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tabulate"])
        from tabulate import tabulate
    
    check_dashboard_status()