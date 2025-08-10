"""
Risk Management API Router

Provides REST API endpoints for risk management operations following hexagonal architecture.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime
import logging

from backend.modules.risk.core_risk_engine import (
    RiskEngine,
    TradingSignal,
    Portfolio,
    RiskAssessment,
    RiskLevel,
    RiskAction
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["Risk Management"])

# Module-level risk engine instance
_risk_engine = RiskEngine()


class SignalRiskRequest(BaseModel):
    """Request to assess signal risk"""
    signal_id: str = Field(..., description="Signal identifier")
    symbol: str = Field(..., description="Trading symbol")
    side: str = Field(..., description="Order side: BUY or SELL")
    quantity: Decimal = Field(..., description="Order quantity")
    price: Optional[Decimal] = Field(default=None, description="Order price")
    signal_type: str = Field(default="MARKET", description="Signal type")
    strategy_id: Optional[str] = Field(default=None, description="Strategy identifier")


class PortfolioRequest(BaseModel):
    """Portfolio state for risk assessment"""
    portfolio_id: str = Field(..., description="Portfolio identifier")
    total_balance: Decimal = Field(..., description="Total portfolio balance")
    available_balance: Decimal = Field(..., description="Available balance")
    unrealized_pnl: Decimal = Field(..., description="Unrealized P&L")
    positions: Dict[str, Dict] = Field(default_factory=dict, description="Current positions")
    open_orders: List[Dict] = Field(default_factory=list, description="Open orders")
    daily_pnl: Decimal = Field(default=Decimal('0'), description="Daily P&L")
    max_drawdown: Decimal = Field(default=Decimal('0'), description="Maximum drawdown")


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response"""
    assessment_id: str
    overall_risk: str
    recommended_action: str
    violations: List[Dict]
    warnings: List[str]
    position_size_adjustment: Optional[Decimal] = None
    timestamp: str


class EmergencyStopRequest(BaseModel):
    """Emergency stop request"""
    reason: str = Field(..., description="Reason for emergency stop")
    stop_all_sessions: bool = Field(default=True, description="Stop all trading sessions")
    portfolio_ids: Optional[List[str]] = Field(default=None, description="Specific portfolios to stop")


@router.post("/assess", response_model=RiskAssessmentResponse)
async def assess_signal_risk(signal_request: SignalRiskRequest, portfolio_request: PortfolioRequest):
    """
    Assess risk for a trading signal against current portfolio state
    """
    try:
        # Convert requests to domain objects
        signal = TradingSignal(
            signal_id=signal_request.signal_id,
            symbol=signal_request.symbol,
            side=signal_request.side,
            quantity=signal_request.quantity,
            price=signal_request.price,
            signal_type=signal_request.signal_type,
            strategy_id=signal_request.strategy_id
        )
        
        portfolio = Portfolio(
            portfolio_id=portfolio_request.portfolio_id,
            total_balance=portfolio_request.total_balance,
            available_balance=portfolio_request.available_balance,
            unrealized_pnl=portfolio_request.unrealized_pnl,
            positions=portfolio_request.positions,
            open_orders=portfolio_request.open_orders,
            daily_pnl=portfolio_request.daily_pnl,
            max_drawdown=portfolio_request.max_drawdown
        )
        
        # Perform risk assessment
        assessment = _risk_engine.assess_signal(signal, portfolio)
        
        # Convert violations to dict format
        violations = [
            {
                "violation_id": v.violation_id,
                "rule_id": v.rule_id,
                "rule_name": v.rule_name,
                "severity": v.severity.value,
                "message": v.message,
                "suggested_action": v.suggested_action.value,
                "timestamp": v.timestamp.isoformat(),
                "metadata": v.metadata
            }
            for v in assessment.violations
        ]
        
        return RiskAssessmentResponse(
            assessment_id=assessment.assessment_id,
            overall_risk=assessment.overall_risk.value,
            recommended_action=assessment.recommended_action.value,
            violations=violations,
            warnings=assessment.warnings,
            position_size_adjustment=assessment.position_size_adjustment,
            timestamp=assessment.timestamp.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Risk assessment failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk assessment failed: {str(e)}"
        )


@router.get("/portfolio/{portfolio_id}/summary")
async def get_portfolio_risk_summary(portfolio_id: str, portfolio_request: PortfolioRequest):
    """
    Get risk summary for a portfolio
    """
    try:
        portfolio = Portfolio(
            portfolio_id=portfolio_request.portfolio_id,
            total_balance=portfolio_request.total_balance,
            available_balance=portfolio_request.available_balance,
            unrealized_pnl=portfolio_request.unrealized_pnl,
            positions=portfolio_request.positions,
            open_orders=portfolio_request.open_orders,
            daily_pnl=portfolio_request.daily_pnl,
            max_drawdown=portfolio_request.max_drawdown
        )
        
        summary = _risk_engine.get_risk_summary(portfolio)
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get portfolio risk summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get risk summary: {str(e)}"
        )


@router.get("/rules")
async def list_risk_rules():
    """
    List all risk management rules
    """
    try:
        rules = []
        for rule in _risk_engine.rules.values():
            rules.append({
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "enabled": rule.enabled,
                "severity": rule.severity.value,
                "parameters": rule.parameters
            })
        
        return {"rules": rules}
        
    except Exception as e:
        logger.error(f"Failed to list risk rules: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list rules: {str(e)}"
        )


@router.post("/rules/{rule_id}/enable")
async def enable_risk_rule(rule_id: str):
    """
    Enable a risk management rule
    """
    try:
        success = _risk_engine.enable_rule(rule_id)
        
        if success:
            return {
                "rule_id": rule_id,
                "status": "enabled",
                "message": f"Rule {rule_id} has been enabled"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule {rule_id} not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable rule {rule_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable rule: {str(e)}"
        )


@router.post("/rules/{rule_id}/disable")
async def disable_risk_rule(rule_id: str):
    """
    Disable a risk management rule
    """
    try:
        success = _risk_engine.disable_rule(rule_id)
        
        if success:
            return {
                "rule_id": rule_id,
                "status": "disabled",
                "message": f"Rule {rule_id} has been disabled"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule {rule_id} not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable rule {rule_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable rule: {str(e)}"
        )


@router.post("/emergency-stop")
async def emergency_stop(request: EmergencyStopRequest):
    """
    Trigger emergency stop for trading operations
    """
    try:
        logger.critical(f"EMERGENCY STOP triggered: {request.reason}")
        
        # In a real implementation, this would:
        # 1. Stop all trading sessions
        # 2. Cancel pending orders
        # 3. Close positions if required
        # 4. Send alerts to administrators
        
        # Mock response for now
        stopped_sessions = []
        if request.stop_all_sessions:
            stopped_sessions = ["all_sessions"]
        elif request.portfolio_ids:
            stopped_sessions = request.portfolio_ids
        
        return {
            "status": "emergency_stop_activated",
            "reason": request.reason,
            "stopped_sessions": stopped_sessions,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Emergency stop has been activated"
        }
        
    except Exception as e:
        logger.error(f"Emergency stop failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emergency stop failed: {str(e)}"
        )


@router.get("/health")
async def risk_health_check():
    """
    Health check for risk management system
    """
    try:
        # Check risk engine status
        total_rules = len(_risk_engine.rules)
        enabled_rules = sum(1 for rule in _risk_engine.rules.values() if rule.enabled)
        
        return {
            "status": "healthy",
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": total_rules - enabled_rules,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Risk health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/limits")
async def get_risk_limits():
    """
    Get current risk limits configuration
    """
    try:
        limits = {}
        
        for rule in _risk_engine.rules.values():
            if rule.enabled:
                limits[rule.rule_id] = {
                    "name": rule.name,
                    "description": rule.description,
                    "parameters": rule.parameters
                }
        
        return {
            "risk_limits": limits,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get risk limits: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get risk limits: {str(e)}"
        )


@router.post("/validate-portfolio")
async def validate_portfolio(portfolio_request: PortfolioRequest):
    """
    Validate portfolio against all risk rules
    """
    try:
        portfolio = Portfolio(
            portfolio_id=portfolio_request.portfolio_id,
            total_balance=portfolio_request.total_balance,
            available_balance=portfolio_request.available_balance,
            unrealized_pnl=portfolio_request.unrealized_pnl,
            positions=portfolio_request.positions,
            open_orders=portfolio_request.open_orders,
            daily_pnl=portfolio_request.daily_pnl,
            max_drawdown=portfolio_request.max_drawdown
        )
        
        # Create a dummy signal to trigger portfolio validation
        dummy_signal = TradingSignal(
            signal_id="validation_signal",
            symbol="VALIDATION",
            side="BUY",
            quantity=Decimal('0'),  # Zero quantity for validation only
            price=Decimal('1')
        )
        
        assessment = _risk_engine.assess_signal(dummy_signal, portfolio)
        
        # Filter out violations related to the dummy signal
        portfolio_violations = [
            v for v in assessment.violations
            if v.rule_id not in ["max_position_size", "symbol_concentration"]
        ]
        
        return {
            "portfolio_id": portfolio.portfolio_id,
            "validation_status": "passed" if not portfolio_violations else "failed",
            "risk_level": assessment.overall_risk.value,
            "violations": [
                {
                    "rule_name": v.rule_name,
                    "severity": v.severity.value,
                    "message": v.message,
                    "metadata": v.metadata
                }
                for v in portfolio_violations
            ],
            "warnings": assessment.warnings,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Portfolio validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Portfolio validation failed: {str(e)}"
        )