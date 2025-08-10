#!/usr/bin/env python3
"""
Test Risk API Endpoints

Tests the risk summary endpoint with sample data.
"""
import asyncio
import json
from decimal import Decimal

# Test the risk manager directly
from src.infrastructure.risk.risk_manager import RiskManager
from src.config.trading_config import RiskConfig

async def test_risk_summary():
    """Test risk summary generation"""
    
    # Create risk config
    config = RiskConfig(
        max_leverage=10,
        max_position_size_usdt=Decimal("10000"),
        max_positions=5,
        daily_loss_limit_usdt=Decimal("500"),
        max_drawdown_percent=Decimal("10")
    )
    
    # Create risk manager
    risk_manager = RiskManager(config)
    
    # Set some test data
    risk_manager.daily_pnl = Decimal("-250")  # 50% of daily limit
    risk_manager.total_exposure = Decimal("25000")  # Some exposure
    risk_manager.current_drawdown = Decimal("3.5")  # 3.5% drawdown
    
    # Get risk summary
    summary = await risk_manager.get_risk_summary()
    
    print("Risk Summary:")
    print(json.dumps(summary, indent=2, default=str))
    
    # Verify values are sane
    assert 0 <= summary["exposure_pct"] <= 100, "Exposure percentage out of range"
    assert 0 <= summary["daily_loss_pct"] <= 100, "Daily loss percentage out of range"
    assert 0 <= summary["drawdown_pct"], "Drawdown cannot be negative"
    assert summary["risk_level"] in ["low", "medium", "high", "critical"], "Invalid risk level"
    assert "thresholds" in summary, "Missing thresholds"
    
    print("\n✅ All risk summary values are sane!")
    
    # Test with different scenarios
    print("\n--- Testing different risk levels ---")
    
    # Low risk
    risk_manager.daily_pnl = Decimal("-50")
    risk_manager.total_exposure = Decimal("10000")
    summary = await risk_manager.get_risk_summary()
    print(f"Low risk scenario: {summary['risk_level']} (daily_loss: {summary['daily_loss_pct']:.1f}%)")
    
    # Medium risk
    risk_manager.daily_pnl = Decimal("-300")
    risk_manager.total_exposure = Decimal("30000")
    summary = await risk_manager.get_risk_summary()
    print(f"Medium risk scenario: {summary['risk_level']} (daily_loss: {summary['daily_loss_pct']:.1f}%)")
    
    # High risk
    risk_manager.daily_pnl = Decimal("-450")
    risk_manager.total_exposure = Decimal("45000")
    summary = await risk_manager.get_risk_summary()
    print(f"High risk scenario: {summary['risk_level']} (daily_loss: {summary['daily_loss_pct']:.1f}%)")
    
    # Critical risk
    risk_manager.daily_pnl = Decimal("-490")
    risk_manager.total_exposure = Decimal("48000")
    summary = await risk_manager.get_risk_summary()
    print(f"Critical risk scenario: {summary['risk_level']} (daily_loss: {summary['daily_loss_pct']:.1f}%)")

if __name__ == "__main__":
    asyncio.run(test_risk_summary())