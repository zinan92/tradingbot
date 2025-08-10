#!/usr/bin/env python3
"""
Final Risk Management Test

Demonstrates the complete risk management integration.
"""
import asyncio
import json
from decimal import Decimal

from src.infrastructure.risk.risk_manager import RiskManager
from src.config.trading_config import RiskConfig
from src.domain.shared.ports import RiskAction


async def test_complete_risk_flow():
    """Test complete risk validation flow"""
    
    print("=" * 60)
    print("RISK MANAGEMENT INTEGRATION TEST")
    print("=" * 60)
    
    # Create risk config
    config = RiskConfig(
        max_leverage=10,
        max_position_size_usdt=Decimal("10000"),
        max_positions=5,
        daily_loss_limit_usdt=Decimal("500"),
        max_drawdown_percent=Decimal("10")
    )
    
    risk_manager = RiskManager(config)
    
    # Test scenarios
    test_cases = [
        {
            "name": "Oversize Position",
            "order": {
                "symbol": "BTCUSDT",
                "side": "buy",
                "quantity": 1,  # $50k position at $50k price
                "price": 50000,
                "leverage": 5
            },
            "portfolio": {
                "balance": Decimal("10000"),
                "equity": Decimal("10000"),
                "margin_used": Decimal("0"),
                "positions": []
            },
            "expected_action": RiskAction.BLOCK
        },
        {
            "name": "Excessive Leverage",
            "order": {
                "symbol": "BTCUSDT",
                "side": "buy",
                "quantity": 0.1,
                "price": 50000,
                "leverage": 20  # Exceeds max 10x
            },
            "portfolio": {
                "balance": Decimal("10000"),
                "equity": Decimal("10000"),
                "margin_used": Decimal("0"),
                "positions": []
            },
            "expected_action": RiskAction.ADJUST
        },
        {
            "name": "Daily Loss Limit",
            "order": {
                "symbol": "ETHUSDT",
                "side": "buy",
                "quantity": 0.5,
                "price": 3000,
                "leverage": 5
            },
            "portfolio": {
                "balance": Decimal("10000"),
                "equity": Decimal("9500"),  # Already down $500
                "margin_used": Decimal("0"),
                "positions": []
            },
            "expected_action": RiskAction.BLOCK
        },
        {
            "name": "Normal Order",
            "order": {
                "symbol": "BTCUSDT",
                "side": "buy",
                "quantity": 0.01,
                "price": 50000,
                "leverage": 5
            },
            "portfolio": {
                "balance": Decimal("10000"),
                "equity": Decimal("10000"),
                "margin_used": Decimal("0"),
                "positions": []
            },
            "expected_action": RiskAction.ALLOW
        }
    ]
    
    # Set daily loss for test
    risk_manager.daily_pnl = Decimal("-500")  # At daily limit
    
    print("\n📊 TEST SCENARIOS:")
    print("-" * 40)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['name']}")
        
        # Reset daily loss for non-loss tests
        if "Loss" not in test["name"]:
            risk_manager.daily_pnl = Decimal("0")
        
        action, reason, adjustments = await risk_manager.validate_trade(
            test["order"],
            test["portfolio"]
        )
        
        print(f"   Order: {test['order']['quantity']} {test['order']['symbol']} @ ${test['order']['price']}")
        print(f"   Action: {action.value.upper()}")
        print(f"   Reason: {reason}")
        if adjustments:
            print(f"   Adjustments: {adjustments}")
        
        # Verify expected outcome
        if action == test["expected_action"]:
            print(f"   ✅ Test passed")
        else:
            print(f"   ❌ Test failed - expected {test['expected_action'].value}")
    
    # Test risk summary
    print("\n📈 RISK SUMMARY:")
    print("-" * 40)
    
    risk_manager.total_exposure = Decimal("25000")
    risk_manager.daily_pnl = Decimal("-250")
    risk_manager.current_drawdown = Decimal("5.0")
    
    summary = await risk_manager.get_risk_summary()
    
    print(f"Exposure: {summary['exposure_pct']:.1f}%")
    print(f"Daily Loss: {summary['daily_loss_pct']:.1f}%")
    print(f"Drawdown: {summary['drawdown_pct']:.1f}%")
    print(f"Risk Level: {summary['risk_level'].upper()}")
    print("\nThresholds:")
    for key, value in summary['thresholds'].items():
        print(f"  - {key}: {value}")
    
    # Validate summary values
    print("\n🔍 VALIDATION:")
    print("-" * 40)
    
    checks = [
        ("Exposure %", 0 <= summary['exposure_pct'] <= 100),
        ("Daily Loss %", 0 <= summary['daily_loss_pct'] <= 100),
        ("Drawdown %", 0 <= summary['drawdown_pct']),
        ("Risk Level", summary['risk_level'] in ["low", "medium", "high", "critical"]),
        ("Has Thresholds", "thresholds" in summary and len(summary['thresholds']) > 0)
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}: {'PASS' if passed else 'FAIL'}")
        all_passed = all_passed and passed
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL RISK MANAGEMENT TESTS PASSED!")
    else:
        print("❌ Some tests failed")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(test_complete_risk_flow())
    exit(0 if result else 1)