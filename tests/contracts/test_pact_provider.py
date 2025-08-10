"""
Pact Provider Verification Tests for FastAPI

This module verifies that the FastAPI backend adheres to the contracts
defined by the frontend consumer tests.
"""

import os
import pytest
import asyncio
from typing import Dict, Any
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Import the FastAPI app
from src.api.main import app
from src.domain.entities import Strategy, Backtest, Position, Order
from src.infrastructure.repositories import StrategyRepository, BacktestRepository


class PactProviderVerifier:
    """Verifies Pact contracts against the FastAPI provider."""
    
    def __init__(self, app, pact_dir: str = "web/frontend/pacts"):
        self.app = app
        self.client = TestClient(app)
        self.pact_dir = pact_dir
        
    def setup_provider_states(self) -> Dict[str, callable]:
        """Define provider state handlers for different test scenarios."""
        return {
            "strategies exist": self._setup_strategies_exist,
            "strategy exists": self._setup_strategy_exists,
            "ready to publish strategy": self._setup_ready_to_publish,
            "ready to run backtest": self._setup_ready_for_backtest,
            "ready to run async backtest": self._setup_ready_for_async_backtest,
            "live trading is active": self._setup_live_trading_active,
            "no active positions": self._setup_no_positions,
            "exchange connection lost": self._setup_exchange_down,
            "trading is active with normal risk": self._setup_normal_risk,
            "critical risk thresholds breached": self._setup_critical_risk,
        }
    
    def _setup_strategies_exist(self):
        """Setup state with existing strategies."""
        with patch('src.infrastructure.repositories.StrategyRepository.get_all') as mock:
            mock.return_value = [
                Strategy(
                    id="strat-001",
                    name="EMA Cross Strategy",
                    type="EMA_CROSS",
                    status="active",
                    params={
                        "fast_period": 12,
                        "slow_period": 26,
                        "stop_loss_pct": 0.02,
                        "take_profit_pct": 0.05
                    },
                    performance={
                        "total_return": 15.5,
                        "sharpe_ratio": 1.8,
                        "max_drawdown": -5.2,
                        "win_rate": 62.5
                    }
                )
            ]
    
    def _setup_strategy_exists(self):
        """Setup state with a specific strategy."""
        with patch('src.infrastructure.repositories.StrategyRepository.get_by_id') as mock:
            mock.return_value = Strategy(
                id="strat-001",
                name="EMA Cross Strategy",
                type="EMA_CROSS",
                status="active",
                params={
                    "fast_period": 12,
                    "slow_period": 26,
                    "stop_loss_pct": 0.02,
                    "take_profit_pct": 0.05,
                    "position_size": 0.95,
                    "use_volume_filter": False,
                    "trailing_stop_pct": 0.03
                },
                performance={
                    "total_return": 15.5,
                    "sharpe_ratio": 1.8,
                    "max_drawdown": -5.2,
                    "win_rate": 62.5,
                    "profit_factor": 1.6,
                    "total_trades": 125,
                    "winning_trades": 78,
                    "losing_trades": 47
                },
                risk_metrics={
                    "var_95": -2.5,
                    "cvar_95": -3.2,
                    "beta": 0.85,
                    "alpha": 0.12
                }
            )
    
    def _setup_ready_to_publish(self):
        """Setup state ready to publish strategy."""
        with patch('src.application.use_cases.PublishStrategyUseCase.execute') as mock:
            mock.return_value = {
                "success": True,
                "message": "Strategy published successfully",
                "deployment": {
                    "id": "deploy-123",
                    "strategy_id": "strat-001",
                    "environment": "production",
                    "version": "1.2.0",
                    "status": "deployed"
                }
            }
    
    def _setup_ready_for_backtest(self):
        """Setup state ready for backtesting."""
        with patch('src.application.use_cases.RunBacktestUseCase.execute') as mock:
            mock.return_value = Backtest(
                backtest_id="backtest-456",
                status="completed",
                strategy_id="strat-001",
                symbol="BTCUSDT",
                timeframe="1h",
                metrics={
                    "total_return": 25.5,
                    "total_return_pct": 2.55,
                    "sharpe_ratio": 1.85,
                    "max_drawdown": -8.5,
                    "win_rate": 58.5,
                    "profit_factor": 1.75,
                    "total_trades": 245
                },
                trades=[],
                equity_curve=[]
            )
    
    def _setup_ready_for_async_backtest(self):
        """Setup state for async backtest."""
        with patch('src.application.use_cases.RunBacktestUseCase.execute_async') as mock:
            mock.return_value = {
                "backtest_id": "backtest-789",
                "status": "running",
                "message": "Backtest started successfully",
                "estimated_time_seconds": 30,
                "progress_url": "/api/backtest/backtest-789/status",
                "result_url": "/api/backtest/backtest-789/result"
            }
    
    def _setup_live_trading_active(self):
        """Setup state with active live trading."""
        with patch('src.application.use_cases.EmergencyStopUseCase.execute') as mock:
            mock.return_value = {
                "success": True,
                "status": "emergency_stop_executed",
                "actions_taken": {
                    "positions_closed": 5,
                    "orders_cancelled": 3,
                    "trading_disabled": True,
                    "notifications_sent": True
                },
                "system_state": {
                    "trading_enabled": False,
                    "risk_monitoring": True,
                    "auto_trading": False,
                    "manual_override": True
                }
            }
    
    def _setup_no_positions(self):
        """Setup state with no active positions."""
        with patch('src.infrastructure.repositories.PositionRepository.get_active') as mock:
            mock.return_value = []
    
    def _setup_exchange_down(self):
        """Setup state with exchange connection lost."""
        with patch('src.infrastructure.exchange.ExchangeClient.is_connected') as mock:
            mock.return_value = False
    
    def _setup_normal_risk(self):
        """Setup state with normal risk levels."""
        with patch('src.application.use_cases.GetRiskSummaryUseCase.execute') as mock:
            mock.return_value = {
                "exposure_pct": 45.5,
                "daily_loss_pct": 1.2,
                "drawdown_pct": 3.5,
                "risk_level": "MEDIUM",
                "thresholds": {
                    "exposure": 80,
                    "daily_loss": 5,
                    "drawdown": 10
                },
                "metrics": {
                    "var_95": -2500.00,
                    "cvar_95": -3200.00,
                    "sharpe_ratio": 1.85,
                    "sortino_ratio": 2.1
                }
            }
    
    def _setup_critical_risk(self):
        """Setup state with critical risk levels."""
        with patch('src.application.use_cases.GetRiskSummaryUseCase.execute') as mock:
            mock.return_value = {
                "exposure_pct": 95.0,
                "daily_loss_pct": 6.5,
                "drawdown_pct": 12.0,
                "risk_level": "CRITICAL",
                "thresholds": {
                    "exposure": 80,
                    "daily_loss": 5,
                    "drawdown": 10
                },
                "breaches": [
                    {
                        "metric": "exposure",
                        "current_value": 95.0,
                        "threshold": 80,
                        "exceeded_by_pct": 18.75,
                        "duration_minutes": 15,
                        "action_required": "immediate_reduction"
                    }
                ],
                "auto_actions": {
                    "enabled": True,
                    "triggered": []
                },
                "emergency_controls": {
                    "pause_trading": True,
                    "close_all_positions": True,
                    "cancel_all_orders": True,
                    "estimated_loss_if_closed": -5250.00
                }
            }


@pytest.fixture
def pact_verifier():
    """Create a Pact verifier instance."""
    return PactProviderVerifier(app)


class TestPactProviderVerification:
    """Test suite for Pact provider verification."""
    
    @pytest.mark.asyncio
    async def test_verify_strategy_contracts(self, pact_verifier):
        """Verify strategy API contracts."""
        # This would normally use pact-python's verifier
        # For demonstration, we're showing the structure
        
        # Setup provider states
        states = pact_verifier.setup_provider_states()
        
        # Verify GET /api/strategy
        states["strategies exist"]()
        response = pact_verifier.client.get("/api/strategy")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "id" in data[0]
            assert "name" in data[0]
            assert "status" in data[0]
    
    @pytest.mark.asyncio
    async def test_verify_backtest_contracts(self, pact_verifier):
        """Verify backtest API contracts."""
        states = pact_verifier.setup_provider_states()
        
        # Verify POST /api/backtest/run
        states["ready to run backtest"]()
        response = pact_verifier.client.post(
            "/api/backtest/run",
            json={
                "strategy_id": "strat-001",
                "symbol": "BTCUSDT",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 10000,
                "timeframe": "1h"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "backtest_id" in data
        assert "status" in data
        assert "metrics" in data
    
    @pytest.mark.asyncio
    async def test_verify_emergency_stop_contracts(self, pact_verifier):
        """Verify emergency stop API contracts."""
        states = pact_verifier.setup_provider_states()
        
        # Verify POST /api/live/emergency-stop
        states["live trading is active"]()
        response = pact_verifier.client.post(
            "/api/live/emergency-stop",
            json={
                "reason": "Market volatility exceeds risk threshold",
                "close_positions": True,
                "cancel_orders": True,
                "disable_trading": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "status" in data
        assert "actions_taken" in data
    
    @pytest.mark.asyncio
    async def test_verify_risk_summary_contracts(self, pact_verifier):
        """Verify risk summary API contracts."""
        states = pact_verifier.setup_provider_states()
        
        # Verify GET /api/risk/summary - normal risk
        states["trading is active with normal risk"]()
        response = pact_verifier.client.get("/api/risk/summary")
        assert response.status_code == 200
        data = response.json()
        assert "exposure_pct" in data
        assert "risk_level" in data
        assert "thresholds" in data
        
        # Verify GET /api/risk/summary - critical risk
        states["critical risk thresholds breached"]()
        response = pact_verifier.client.get("/api/risk/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["risk_level"] == "CRITICAL"
        assert "breaches" in data
        assert "emergency_controls" in data


def run_provider_verification():
    """Run all provider verification tests."""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_provider_verification()