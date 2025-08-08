#!/usr/bin/env python3
"""
Test script to verify dashboard components are working
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

def test_imports():
    """Test that all dashboard modules can be imported"""
    print("Testing dashboard imports...")
    
    try:
        from dashboard.services.data_service import DataService
        print("✅ Data Service imported successfully")
        
        from dashboard.pages import live_monitoring
        print("✅ Live Monitoring page imported")
        
        from dashboard.pages import deploy_strategy
        print("✅ Deploy Strategy page imported")
        
        from dashboard.pages import risk_management
        print("✅ Risk Management page imported")
        
        from dashboard.pages import performance_history
        print("✅ Performance History page imported")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_data_service():
    """Test data service connectivity"""
    print("\nTesting data service...")
    
    try:
        from dashboard.services.data_service import DataService
        
        # Initialize service
        data_service = DataService()
        print("✅ Data service initialized")
        
        # Test config loading
        config = data_service.load_config()
        if config:
            print(f"✅ Config loaded successfully")
            active_strategy = None
            for strategy, settings in config.get('strategy', {}).items():
                if isinstance(settings, dict) and settings.get('enabled'):
                    active_strategy = strategy
                    break
            print(f"   Active strategy: {active_strategy or 'None'}")
            print(f"   Initial capital: ${config.get('capital', {}).get('initial_capital', 0)}")
        
        # Test database connection
        positions = data_service.get_positions()
        print(f"✅ Database connection working")
        print(f"   Open positions: {len(positions)}")
        
        # Test PnL calculation
        pnl = data_service.get_pnl_summary()
        print(f"✅ PnL calculation working")
        print(f"   Total P&L: ${pnl.get('total_pnl', 0):.2f}")
        
        # Test risk metrics
        risk = data_service.get_risk_metrics()
        print(f"✅ Risk metrics working")
        print(f"   Risk level: {risk.get('risk_level', 'UNKNOWN')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Data service error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("DASHBOARD COMPONENT TEST")
    print("=" * 50)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test data service
    if not test_data_service():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ALL TESTS PASSED!")
        print("\n📊 Dashboard is ready to use!")
        print("   URL: http://localhost:8501")
        print("\nNext steps:")
        print("1. Open http://localhost:8501 in your browser")
        print("2. Navigate through the pages:")
        print("   - Live Monitoring: See current positions and P&L")
        print("   - Deploy Strategy: Configure and launch strategies")
        print("   - Risk Management: Monitor and control risk")
        print("   - Performance History: Analyze past performance")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    print("=" * 50)

if __name__ == "__main__":
    main()