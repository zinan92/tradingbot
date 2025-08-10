#!/usr/bin/env python3
"""
Test failing acceptance scenario
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.acceptance_backtest import AcceptanceBacktest

async def test_failing():
    """Test with metrics that should fail"""
    runner = AcceptanceBacktest(output_dir="artifacts/test_fail")
    
    # Create failing metrics
    metrics_path = Path("artifacts/test_fail/metrics.json")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    
    import json
    with open(metrics_path, 'w') as f:
        json.dump({
            'sharpe': 0.5,  # Below 1.0 threshold
            'max_dd': 25.0,  # Above 20% threshold
            'win_rate': 35.0,  # Below 40% threshold
            'returns': -10.0,
            'profit_factor': 0.8,
            'total_trades': 20
        }, f)
    
    # Validate metrics (should fail)
    passed, _ = runner.validate_metrics(metrics_path)
    
    # Clean up
    import shutil
    shutil.rmtree("artifacts/test_fail", ignore_errors=True)
    
    return 0 if not passed else 1  # Expect failure

if __name__ == "__main__":
    exit_code = asyncio.run(test_failing())
    print(f"\nTest {'PASSED' if exit_code == 0 else 'FAILED'}: Acceptance correctly rejected bad metrics")
    sys.exit(exit_code)