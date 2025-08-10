"""
Risk Management API Router

Provides endpoints for risk monitoring and management.
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from decimal import Decimal

from src.domain.shared.ports import RiskPort

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["risk"])


class RiskSummary(BaseModel):
    """Risk summary response model"""
    exposure_pct: float = Field(..., description="Current exposure as percentage of capital")
    daily_loss_pct: float = Field(..., description="Today's loss as percentage")
    drawdown_pct: float = Field(..., description="Current drawdown percentage")
    risk_level: str = Field(..., description="Overall risk level (low/medium/high/critical)")
    thresholds: Dict[str, float] = Field(..., description="Risk thresholds being monitored")


# Dependency injection for risk port
async def get_risk_port() -> RiskPort:
    """Get risk port instance (would be injected in production)"""
    # This should be configured with proper dependency injection
    # For now, return a placeholder
    from src.infrastructure.risk.risk_manager import RiskManager
    from src.config.trading_config import TradingConfig
    
    config = TradingConfig.from_env()
    return RiskManager(config.risk)


@router.get("/summary", response_model=RiskSummary)
async def get_risk_summary(
    risk_port: RiskPort = Depends(get_risk_port)
) -> RiskSummary:
    """
    Get current risk summary
    
    Returns comprehensive risk metrics for monitoring.
    """
    try:
        # Get risk summary from port
        summary = await risk_port.get_risk_summary()
        
        return RiskSummary(
            exposure_pct=float(summary.get("exposure_pct", 0)),
            daily_loss_pct=float(summary.get("daily_loss_pct", 0)),
            drawdown_pct=float(summary.get("drawdown_pct", 0)),
            risk_level=summary.get("risk_level", "unknown"),
            thresholds=summary.get("thresholds", {})
        )
        
    except Exception as e:
        logger.error(f"Failed to get risk summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve risk summary")


@router.get("/exposure")
async def get_exposure_details(
    risk_port: RiskPort = Depends(get_risk_port)
) -> Dict[str, Any]:
    """
    Get detailed exposure information
    
    Returns breakdown of exposure by symbol and position.
    """
    try:
        # This would get more detailed exposure info
        portfolio_state = {
            "positions": [],
            "balance": Decimal("10000"),
            "equity": Decimal("10000"),
            "margin_used": Decimal("0"),
            "exposure": Decimal("0")
        }
        
        exposure_info = await risk_port.check_exposure_limits(portfolio_state)
        return exposure_info
        
    except Exception as e:
        logger.error(f"Failed to get exposure details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve exposure details")


@router.get("/metrics")
async def get_risk_metrics(
    risk_port: RiskPort = Depends(get_risk_port)
) -> Dict[str, Any]:
    """
    Get comprehensive risk metrics
    
    Returns detailed risk metrics including VaR, Sharpe ratio, etc.
    """
    try:
        # This would get comprehensive metrics
        portfolio_state = {
            "positions": [],
            "balance": Decimal("10000"),
            "equity": Decimal("10000"),
            "margin_used": Decimal("0"),
            "exposure": Decimal("0")
        }
        
        metrics = await risk_port.get_risk_metrics(portfolio_state)
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get risk metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve risk metrics")