"""
Core Risk Engine

Core domain logic for risk management following hexagonal architecture.
Validates trades, manages position sizes, and enforces risk limits.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Protocol, Tuple
import logging

logger = logging.getLogger(__name__)


class RiskAction(Enum):
    """Risk action decisions"""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REDUCE = "REDUCE"
    WARN = "WARN"


class RiskLevel(Enum):
    """Risk levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskRule:
    """Risk management rule"""
    rule_id: str
    name: str
    description: str
    enabled: bool = True
    severity: RiskLevel = RiskLevel.MEDIUM
    parameters: Dict = field(default_factory=dict)


@dataclass
class RiskViolation:
    """Risk rule violation"""
    violation_id: str
    rule_id: str
    rule_name: str
    severity: RiskLevel
    message: str
    suggested_action: RiskAction
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)


@dataclass
class RiskAssessment:
    """Risk assessment result"""
    assessment_id: str
    overall_risk: RiskLevel
    recommended_action: RiskAction
    violations: List[RiskViolation]
    warnings: List[str]
    position_size_adjustment: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TradingSignal:
    """Trading signal for risk validation"""
    signal_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: Decimal
    price: Optional[Decimal]
    signal_type: str = "MARKET"
    strategy_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Portfolio:
    """Portfolio state for risk assessment"""
    portfolio_id: str
    total_balance: Decimal
    available_balance: Decimal
    unrealized_pnl: Decimal
    positions: Dict[str, Dict] = field(default_factory=dict)
    open_orders: List[Dict] = field(default_factory=list)
    daily_pnl: Decimal = Decimal('0')
    max_drawdown: Decimal = Decimal('0')
    updated_at: datetime = field(default_factory=datetime.utcnow)


class RiskEngine:
    """
    Core risk management engine that evaluates trading decisions
    """
    
    def __init__(self):
        self.rules: Dict[str, RiskRule] = {}
        self._initialize_default_rules()
    
    def _initialize_default_rules(self):
        """Initialize default risk management rules"""
        
        # Position size limits
        self.add_rule(RiskRule(
            rule_id="max_position_size",
            name="Maximum Position Size",
            description="Limit individual position size as % of portfolio",
            parameters={
                "max_position_pct": 10.0,  # 10% max per position
                "critical_threshold": 15.0  # Critical if > 15%
            }
        ))
        
        # Daily loss limits
        self.add_rule(RiskRule(
            rule_id="daily_loss_limit",
            name="Daily Loss Limit",
            description="Maximum daily loss allowed",
            parameters={
                "max_daily_loss_pct": 5.0,  # 5% max daily loss
                "critical_threshold": 3.0   # Critical if > 3%
            }
        ))
        
        # Total exposure limits
        self.add_rule(RiskRule(
            rule_id="total_exposure_limit",
            name="Total Portfolio Exposure",
            description="Maximum total portfolio exposure",
            parameters={
                "max_exposure_pct": 80.0,   # 80% max exposure
                "warning_threshold": 70.0   # Warning if > 70%
            }
        ))
        
        # Drawdown protection
        self.add_rule(RiskRule(
            rule_id="max_drawdown_limit",
            name="Maximum Drawdown Protection",
            description="Protect against excessive drawdowns",
            parameters={
                "max_drawdown_pct": 20.0,   # 20% max drawdown
                "critical_threshold": 15.0  # Critical if > 15%
            }
        ))
        
        # Concentration risk
        self.add_rule(RiskRule(
            rule_id="symbol_concentration",
            name="Symbol Concentration Limit",
            description="Prevent over-concentration in single symbol",
            parameters={
                "max_symbol_exposure_pct": 25.0,  # 25% max per symbol
                "warning_threshold": 20.0         # Warning if > 20%
            }
        ))
        
        # Order frequency limits
        self.add_rule(RiskRule(
            rule_id="order_frequency_limit",
            name="Order Frequency Limit",
            description="Prevent excessive trading frequency",
            parameters={
                "max_orders_per_hour": 50,     # Max 50 orders per hour
                "max_orders_per_day": 500      # Max 500 orders per day
            }
        ))
    
    def add_rule(self, rule: RiskRule) -> None:
        """Add a risk management rule"""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added risk rule: {rule.name}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a risk management rule"""
        if rule_id in self.rules:
            rule = self.rules.pop(rule_id)
            logger.info(f"Removed risk rule: {rule.name}")
            return True
        return False
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a risk rule"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a risk rule"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False
    
    def assess_signal(self, signal: TradingSignal, portfolio: Portfolio) -> RiskAssessment:
        """
        Assess risk for a trading signal
        
        Args:
            signal: Trading signal to assess
            portfolio: Current portfolio state
            
        Returns:
            Risk assessment with recommendations
        """
        assessment_id = f"assessment_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
        violations = []
        warnings = []
        
        # Evaluate each enabled rule
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            try:
                violation = self._evaluate_rule(rule, signal, portfolio)
                if violation:
                    violations.append(violation)
                    
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {str(e)}")
                warnings.append(f"Rule evaluation error: {rule.name}")
        
        # Determine overall risk and action
        overall_risk, recommended_action = self._calculate_overall_risk(violations)
        
        # Calculate position size adjustment if needed
        position_adjustment = self._calculate_position_adjustment(signal, portfolio, violations)
        
        return RiskAssessment(
            assessment_id=assessment_id,
            overall_risk=overall_risk,
            recommended_action=recommended_action,
            violations=violations,
            warnings=warnings,
            position_size_adjustment=position_adjustment
        )
    
    def _evaluate_rule(self, rule: RiskRule, signal: TradingSignal, portfolio: Portfolio) -> Optional[RiskViolation]:
        """Evaluate a specific risk rule"""
        
        if rule.rule_id == "max_position_size":
            return self._check_position_size(rule, signal, portfolio)
        elif rule.rule_id == "daily_loss_limit":
            return self._check_daily_loss(rule, signal, portfolio)
        elif rule.rule_id == "total_exposure_limit":
            return self._check_total_exposure(rule, signal, portfolio)
        elif rule.rule_id == "max_drawdown_limit":
            return self._check_drawdown(rule, signal, portfolio)
        elif rule.rule_id == "symbol_concentration":
            return self._check_symbol_concentration(rule, signal, portfolio)
        elif rule.rule_id == "order_frequency_limit":
            return self._check_order_frequency(rule, signal, portfolio)
        
        return None
    
    def _check_position_size(self, rule: RiskRule, signal: TradingSignal, portfolio: Portfolio) -> Optional[RiskViolation]:
        """Check position size limits"""
        if portfolio.total_balance <= 0:
            return None
        
        signal_value = signal.quantity * (signal.price or Decimal('50000'))  # Default price
        position_pct = (signal_value / portfolio.total_balance) * 100
        
        max_pct = Decimal(str(rule.parameters.get('max_position_pct', 10.0)))
        critical_pct = Decimal(str(rule.parameters.get('critical_threshold', 15.0)))
        
        if position_pct > critical_pct:
            return RiskViolation(
                violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=RiskLevel.CRITICAL,
                message=f"Position size {position_pct:.2f}% exceeds critical limit {critical_pct}%",
                suggested_action=RiskAction.BLOCK,
                timestamp=datetime.utcnow(),
                metadata={
                    "position_pct": float(position_pct),
                    "limit": float(critical_pct),
                    "signal_value": float(signal_value)
                }
            )
        elif position_pct > max_pct:
            return RiskViolation(
                violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=RiskLevel.HIGH,
                message=f"Position size {position_pct:.2f}% exceeds limit {max_pct}%",
                suggested_action=RiskAction.REDUCE,
                timestamp=datetime.utcnow(),
                metadata={
                    "position_pct": float(position_pct),
                    "limit": float(max_pct),
                    "signal_value": float(signal_value)
                }
            )
        
        return None
    
    def _check_daily_loss(self, rule: RiskRule, signal: TradingSignal, portfolio: Portfolio) -> Optional[RiskViolation]:
        """Check daily loss limits"""
        if portfolio.total_balance <= 0:
            return None
        
        daily_loss_pct = abs(portfolio.daily_pnl / portfolio.total_balance) * 100
        max_loss_pct = Decimal(str(rule.parameters.get('max_daily_loss_pct', 5.0)))
        critical_pct = Decimal(str(rule.parameters.get('critical_threshold', 3.0)))
        
        if portfolio.daily_pnl < 0:  # Only check if in loss
            if daily_loss_pct > max_loss_pct:
                return RiskViolation(
                    violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    severity=RiskLevel.CRITICAL,
                    message=f"Daily loss {daily_loss_pct:.2f}% exceeds limit {max_loss_pct}%",
                    suggested_action=RiskAction.BLOCK,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "daily_loss_pct": float(daily_loss_pct),
                        "limit": float(max_loss_pct),
                        "daily_pnl": float(portfolio.daily_pnl)
                    }
                )
            elif daily_loss_pct > critical_pct:
                return RiskViolation(
                    violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    severity=RiskLevel.HIGH,
                    message=f"Daily loss {daily_loss_pct:.2f}% approaching limit",
                    suggested_action=RiskAction.WARN,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "daily_loss_pct": float(daily_loss_pct),
                        "limit": float(max_loss_pct),
                        "daily_pnl": float(portfolio.daily_pnl)
                    }
                )
        
        return None
    
    def _check_total_exposure(self, rule: RiskRule, signal: TradingSignal, portfolio: Portfolio) -> Optional[RiskViolation]:
        """Check total portfolio exposure limits"""
        # Calculate current exposure (simplified)
        current_exposure = sum(
            abs(Decimal(str(pos.get('value', 0))))
            for pos in portfolio.positions.values()
        )
        
        if portfolio.total_balance <= 0:
            return None
        
        exposure_pct = (current_exposure / portfolio.total_balance) * 100
        max_exposure = Decimal(str(rule.parameters.get('max_exposure_pct', 80.0)))
        warning_threshold = Decimal(str(rule.parameters.get('warning_threshold', 70.0)))
        
        if exposure_pct > max_exposure:
            return RiskViolation(
                violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=RiskLevel.HIGH,
                message=f"Total exposure {exposure_pct:.2f}% exceeds limit {max_exposure}%",
                suggested_action=RiskAction.BLOCK,
                timestamp=datetime.utcnow(),
                metadata={
                    "exposure_pct": float(exposure_pct),
                    "limit": float(max_exposure),
                    "current_exposure": float(current_exposure)
                }
            )
        elif exposure_pct > warning_threshold:
            return RiskViolation(
                violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=RiskLevel.MEDIUM,
                message=f"Total exposure {exposure_pct:.2f}% approaching limit",
                suggested_action=RiskAction.WARN,
                timestamp=datetime.utcnow(),
                metadata={
                    "exposure_pct": float(exposure_pct),
                    "limit": float(max_exposure),
                    "current_exposure": float(current_exposure)
                }
            )
        
        return None
    
    def _check_drawdown(self, rule: RiskRule, signal: TradingSignal, portfolio: Portfolio) -> Optional[RiskViolation]:
        """Check maximum drawdown limits"""
        if portfolio.total_balance <= 0:
            return None
        
        drawdown_pct = abs(portfolio.max_drawdown / portfolio.total_balance) * 100
        max_drawdown = Decimal(str(rule.parameters.get('max_drawdown_pct', 20.0)))
        critical_threshold = Decimal(str(rule.parameters.get('critical_threshold', 15.0)))
        
        if drawdown_pct > max_drawdown:
            return RiskViolation(
                violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=RiskLevel.CRITICAL,
                message=f"Drawdown {drawdown_pct:.2f}% exceeds limit {max_drawdown}%",
                suggested_action=RiskAction.BLOCK,
                timestamp=datetime.utcnow(),
                metadata={
                    "drawdown_pct": float(drawdown_pct),
                    "limit": float(max_drawdown),
                    "max_drawdown": float(portfolio.max_drawdown)
                }
            )
        elif drawdown_pct > critical_threshold:
            return RiskViolation(
                violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=RiskLevel.HIGH,
                message=f"Drawdown {drawdown_pct:.2f}% approaching limit",
                suggested_action=RiskAction.WARN,
                timestamp=datetime.utcnow(),
                metadata={
                    "drawdown_pct": float(drawdown_pct),
                    "limit": float(max_drawdown),
                    "max_drawdown": float(portfolio.max_drawdown)
                }
            )
        
        return None
    
    def _check_symbol_concentration(self, rule: RiskRule, signal: TradingSignal, portfolio: Portfolio) -> Optional[RiskViolation]:
        """Check symbol concentration limits"""
        symbol_exposure = Decimal('0')
        
        # Get current exposure to this symbol
        if signal.symbol in portfolio.positions:
            symbol_exposure = abs(Decimal(str(portfolio.positions[signal.symbol].get('value', 0))))
        
        # Add signal value
        signal_value = signal.quantity * (signal.price or Decimal('50000'))
        total_symbol_exposure = symbol_exposure + signal_value
        
        if portfolio.total_balance <= 0:
            return None
        
        concentration_pct = (total_symbol_exposure / portfolio.total_balance) * 100
        max_concentration = Decimal(str(rule.parameters.get('max_symbol_exposure_pct', 25.0)))
        warning_threshold = Decimal(str(rule.parameters.get('warning_threshold', 20.0)))
        
        if concentration_pct > max_concentration:
            return RiskViolation(
                violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=RiskLevel.HIGH,
                message=f"Symbol concentration {concentration_pct:.2f}% exceeds limit {max_concentration}%",
                suggested_action=RiskAction.REDUCE,
                timestamp=datetime.utcnow(),
                metadata={
                    "symbol": signal.symbol,
                    "concentration_pct": float(concentration_pct),
                    "limit": float(max_concentration),
                    "total_exposure": float(total_symbol_exposure)
                }
            )
        elif concentration_pct > warning_threshold:
            return RiskViolation(
                violation_id=f"violation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                severity=RiskLevel.MEDIUM,
                message=f"Symbol concentration {concentration_pct:.2f}% approaching limit",
                suggested_action=RiskAction.WARN,
                timestamp=datetime.utcnow(),
                metadata={
                    "symbol": signal.symbol,
                    "concentration_pct": float(concentration_pct),
                    "limit": float(max_concentration),
                    "total_exposure": float(total_symbol_exposure)
                }
            )
        
        return None
    
    def _check_order_frequency(self, rule: RiskRule, signal: TradingSignal, portfolio: Portfolio) -> Optional[RiskViolation]:
        """Check order frequency limits"""
        # This would require order history tracking in a real implementation
        # For now, just return None as we don't have the order history
        return None
    
    def _calculate_overall_risk(self, violations: List[RiskViolation]) -> Tuple[RiskLevel, RiskAction]:
        """Calculate overall risk level and recommended action"""
        if not violations:
            return RiskLevel.LOW, RiskAction.ALLOW
        
        # Find highest severity
        max_severity = max(v.severity for v in violations)
        
        # Find most restrictive action
        actions = [v.suggested_action for v in violations]
        
        if RiskAction.BLOCK in actions:
            recommended_action = RiskAction.BLOCK
        elif RiskAction.REDUCE in actions:
            recommended_action = RiskAction.REDUCE
        elif RiskAction.WARN in actions:
            recommended_action = RiskAction.WARN
        else:
            recommended_action = RiskAction.ALLOW
        
        return max_severity, recommended_action
    
    def _calculate_position_adjustment(self, signal: TradingSignal, portfolio: Portfolio, violations: List[RiskViolation]) -> Optional[Decimal]:
        """Calculate position size adjustment if needed"""
        
        for violation in violations:
            if violation.suggested_action == RiskAction.REDUCE:
                if violation.rule_id == "max_position_size":
                    # Reduce to maximum allowed
                    max_pct = Decimal(str(self.rules[violation.rule_id].parameters.get('max_position_pct', 10.0)))
                    max_value = portfolio.total_balance * max_pct / 100
                    
                    if signal.price:
                        return max_value / signal.price
                    
                elif violation.rule_id == "symbol_concentration":
                    # Reduce to stay within concentration limits
                    max_pct = Decimal(str(self.rules[violation.rule_id].parameters.get('max_symbol_exposure_pct', 25.0)))
                    max_value = portfolio.total_balance * max_pct / 100
                    
                    # Subtract existing exposure
                    existing_exposure = Decimal('0')
                    if signal.symbol in portfolio.positions:
                        existing_exposure = abs(Decimal(str(portfolio.positions[signal.symbol].get('value', 0))))
                    
                    available_value = max_value - existing_exposure
                    
                    if signal.price and available_value > 0:
                        return available_value / signal.price
        
        return None
    
    def get_risk_summary(self, portfolio: Portfolio) -> Dict:
        """Get current risk summary for portfolio"""
        
        # Calculate key risk metrics
        if portfolio.total_balance <= 0:
            return {"status": "invalid", "message": "Invalid portfolio balance"}
        
        # Total exposure
        total_exposure = sum(
            abs(Decimal(str(pos.get('value', 0))))
            for pos in portfolio.positions.values()
        )
        exposure_pct = (total_exposure / portfolio.total_balance) * 100
        
        # Daily P&L percentage
        daily_pnl_pct = (portfolio.daily_pnl / portfolio.total_balance) * 100
        
        # Drawdown percentage
        drawdown_pct = abs(portfolio.max_drawdown / portfolio.total_balance) * 100
        
        # Available margin
        available_margin = portfolio.available_balance / portfolio.total_balance * 100
        
        return {
            "portfolio_id": portfolio.portfolio_id,
            "total_balance": float(portfolio.total_balance),
            "available_balance": float(portfolio.available_balance),
            "exposure_pct": float(exposure_pct),
            "daily_pnl_pct": float(daily_pnl_pct),
            "drawdown_pct": float(drawdown_pct),
            "available_margin_pct": float(available_margin),
            "open_positions": len(portfolio.positions),
            "pending_orders": len(portfolio.open_orders),
            "updated_at": portfolio.updated_at.isoformat()
        }