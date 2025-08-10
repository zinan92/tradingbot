"""
Risk Manager Implementation

Concrete implementation of RiskPort for production use.
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta

from src.domain.shared.ports import RiskPort, RiskAction
from src.config.trading_config import RiskConfig

logger = logging.getLogger(__name__)


class RiskManager(RiskPort):
    """
    Concrete implementation of risk management
    
    Validates trades against configurable risk parameters.
    """
    
    def __init__(self, config: RiskConfig):
        """
        Initialize risk manager
        
        Args:
            config: Risk configuration
        """
        self.config = config
        
        # Track daily metrics
        self.daily_pnl = Decimal("0")
        self.daily_trades = 0
        self.last_reset = datetime.utcnow().date()
        
        # Track current exposure
        self.current_positions: Dict[str, Dict[str, Any]] = {}
        self.total_exposure = Decimal("0")
        
        # Track drawdown
        self.peak_equity = Decimal("0")
        self.current_drawdown = Decimal("0")
        
        logger.info(f"RiskManager initialized with limits: "
                   f"max_leverage={config.max_leverage}, "
                   f"max_position=${config.max_position_size_usdt}, "
                   f"daily_loss_limit=${config.daily_loss_limit_usdt}")
    
    async def validate_trade(
        self,
        order: Dict[str, Any],
        portfolio_state: Dict[str, Any]
    ) -> Tuple[RiskAction, str, Optional[Dict[str, Any]]]:
        """
        Validate trade against risk rules
        
        Checks:
        1. Position size limits
        2. Leverage limits
        3. Daily loss limits
        4. Maximum positions
        5. Margin requirements
        6. Correlation limits (simplified)
        """
        # Reset daily metrics if needed
        self._check_daily_reset()
        
        # Extract order details
        symbol = order.get('symbol', '')
        side = order.get('side', '')
        quantity = Decimal(str(order.get('quantity', 0)))
        price = Decimal(str(order.get('price', 100)))
        leverage = order.get('leverage', 1)
        
        # Calculate position value
        position_value = quantity * price
        
        # Check 1: Position size limit
        if position_value > self.config.max_position_size_usdt:
            return (
                RiskAction.BLOCK,
                f"Position size ${position_value:.2f} exceeds maximum ${self.config.max_position_size_usdt}",
                None
            )
        
        # Check 2: Leverage limit
        if leverage > self.config.max_leverage:
            # Try to adjust leverage down
            adjusted_leverage = self.config.max_leverage
            return (
                RiskAction.ADJUST,
                f"Leverage adjusted from {leverage}x to {adjusted_leverage}x",
                {"leverage": adjusted_leverage}
            )
        
        # Check 3: Daily loss limit
        if abs(self.daily_pnl) >= self.config.daily_loss_limit_usdt:
            return (
                RiskAction.BLOCK,
                f"Daily loss limit ${self.config.daily_loss_limit_usdt} reached (current: ${abs(self.daily_pnl):.2f})",
                None
            )
        
        # Check 4: Maximum positions
        current_positions = len(portfolio_state.get('positions', []))
        if current_positions >= self.config.max_positions:
            return (
                RiskAction.BLOCK,
                f"Maximum positions limit ({self.config.max_positions}) reached",
                None
            )
        
        # Check 5: Margin requirements
        required_margin = position_value / leverage if leverage > 0 else position_value
        available_balance = portfolio_state.get('balance', Decimal("0"))
        
        if required_margin > available_balance:
            # Try to reduce position size
            affordable_value = available_balance * leverage * Decimal("0.95")  # 95% to leave buffer
            adjusted_quantity = affordable_value / price
            
            if adjusted_quantity < quantity * Decimal("0.1"):  # Less than 10% of original
                return (
                    RiskAction.BLOCK,
                    f"Insufficient margin: required ${required_margin:.2f}, available ${available_balance:.2f}",
                    None
                )
            else:
                return (
                    RiskAction.ADJUST,
                    f"Position size reduced to fit available margin",
                    {"quantity": float(adjusted_quantity)}
                )
        
        # Check 6: Correlation (simplified - check if same symbol already exists)
        existing_positions = portfolio_state.get('positions', [])
        for pos in existing_positions:
            if pos.get('symbol') == symbol:
                # Already have position in this symbol
                existing_value = Decimal(str(pos.get('quantity', 0))) * Decimal(str(pos.get('entry_price', 0)))
                combined_value = existing_value + position_value
                
                if combined_value > self.config.max_position_size_usdt:
                    return (
                        RiskAction.BLOCK,
                        f"Combined position in {symbol} would exceed maximum size",
                        None
                    )
        
        # Check 7: Drawdown limit
        current_equity = portfolio_state.get('equity', Decimal("0"))
        if self.peak_equity > 0:
            drawdown_pct = ((self.peak_equity - current_equity) / self.peak_equity) * 100
            if drawdown_pct > self.config.max_drawdown_percent:
                return (
                    RiskAction.BLOCK,
                    f"Maximum drawdown {self.config.max_drawdown_percent}% exceeded (current: {drawdown_pct:.2f}%)",
                    None
                )
        
        # All checks passed
        return (RiskAction.ALLOW, "Trade approved by risk management", None)
    
    async def calculate_position_size(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Optional[Decimal],
        portfolio_value: Decimal,
        risk_per_trade: Decimal
    ) -> Decimal:
        """Calculate optimal position size using risk-based sizing"""
        if stop_loss and stop_loss != entry_price:
            # Risk-based position sizing
            risk_amount = portfolio_value * risk_per_trade
            price_risk = abs(entry_price - stop_loss)
            position_size = risk_amount / price_risk
            
            # Apply maximum position size limit
            max_size = self.config.max_position_size_usdt / entry_price
            return min(position_size, max_size)
        else:
            # Fixed percentage sizing
            position_value = portfolio_value * risk_per_trade
            position_size = position_value / entry_price
            
            # Apply maximum position size limit
            max_size = self.config.max_position_size_usdt / entry_price
            return min(position_size, max_size)
    
    async def check_exposure_limits(
        self,
        portfolio_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check current exposure against limits"""
        positions = portfolio_state.get('positions', [])
        equity = portfolio_state.get('equity', Decimal("1"))
        
        # Calculate total exposure
        total_exposure = Decimal("0")
        exposure_by_symbol = {}
        
        for pos in positions:
            symbol = pos.get('symbol', '')
            quantity = Decimal(str(pos.get('quantity', 0)))
            price = Decimal(str(pos.get('current_price', 0)))
            position_value = quantity * price
            
            total_exposure += position_value
            exposure_by_symbol[symbol] = position_value
        
        # Calculate metrics
        max_allowed_exposure = equity * Decimal(str(self.config.max_leverage))
        exposure_ratio = total_exposure / max_allowed_exposure if max_allowed_exposure > 0 else Decimal("0")
        
        return {
            "total_exposure": float(total_exposure),
            "max_allowed_exposure": float(max_allowed_exposure),
            "exposure_ratio": float(exposure_ratio),
            "exposure_by_symbol": {k: float(v) for k, v in exposure_by_symbol.items()},
            "within_limits": exposure_ratio <= 1,
            "positions_count": len(positions),
            "max_positions": self.config.max_positions
        }
    
    async def calculate_var(
        self,
        positions: List[Dict[str, Any]],
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ) -> Decimal:
        """
        Calculate Value at Risk (simplified)
        
        Uses historical volatility approach
        """
        if not positions:
            return Decimal("0")
        
        # Calculate portfolio value
        portfolio_value = Decimal("0")
        for pos in positions:
            quantity = Decimal(str(pos.get('quantity', 0)))
            price = Decimal(str(pos.get('current_price', 0)))
            portfolio_value += quantity * price
        
        # Use simplified volatility assumption (2% daily for crypto)
        daily_volatility = Decimal("0.02")
        
        # Z-score for confidence level
        z_scores = {
            0.90: Decimal("1.282"),
            0.95: Decimal("1.645"),
            0.99: Decimal("2.326")
        }
        z_score = z_scores.get(confidence_level, Decimal("1.645"))
        
        # Calculate VaR
        var = portfolio_value * daily_volatility * z_score * Decimal(str(time_horizon ** 0.5))
        
        return var
    
    async def get_risk_metrics(
        self,
        portfolio_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get comprehensive risk metrics"""
        positions = portfolio_state.get('positions', [])
        equity = portfolio_state.get('equity', Decimal("1"))
        balance = portfolio_state.get('balance', Decimal("0"))
        
        # Calculate exposure
        total_exposure = Decimal("0")
        for pos in positions:
            quantity = Decimal(str(pos.get('quantity', 0)))
            price = Decimal(str(pos.get('current_price', 0)))
            total_exposure += quantity * price
        
        # Calculate leverage
        leverage = total_exposure / equity if equity > 0 else Decimal("0")
        
        # Calculate drawdown
        if equity > self.peak_equity:
            self.peak_equity = equity
        
        drawdown = ((self.peak_equity - equity) / self.peak_equity * 100) if self.peak_equity > 0 else Decimal("0")
        
        # Calculate risk score (0-100)
        risk_score = self._calculate_risk_score(
            leverage=float(leverage),
            drawdown=float(drawdown),
            daily_loss=float(abs(self.daily_pnl)),
            positions_count=len(positions)
        )
        
        # Calculate Sharpe ratio (simplified - would need returns history)
        sharpe_ratio = 1.5  # Placeholder
        
        return {
            "total_exposure": float(total_exposure),
            "leverage": float(leverage),
            "max_drawdown": float(drawdown),
            "sharpe_ratio": sharpe_ratio,
            "risk_score": risk_score,
            "daily_pnl": float(self.daily_pnl),
            "positions_count": len(positions),
            "available_margin": float(balance)
        }
    
    async def validate_stop_loss(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        position_side: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate stop loss placement"""
        if position_side.lower() == "long":
            if stop_loss >= entry_price:
                return False, "Stop loss must be below entry price for long positions"
            
            # Check minimum distance (e.g., 0.5%)
            min_distance = entry_price * Decimal("0.005")
            if entry_price - stop_loss < min_distance:
                return False, f"Stop loss too close to entry (minimum 0.5% distance required)"
                
        elif position_side.lower() == "short":
            if stop_loss <= entry_price:
                return False, "Stop loss must be above entry price for short positions"
            
            # Check minimum distance
            min_distance = entry_price * Decimal("0.005")
            if stop_loss - entry_price < min_distance:
                return False, f"Stop loss too close to entry (minimum 0.5% distance required)"
        
        return True, None
    
    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary for monitoring"""
        # Calculate current metrics
        exposure_pct = (self.total_exposure / (self.config.max_position_size_usdt * self.config.max_positions) * 100) \
            if self.config.max_position_size_usdt > 0 else 0
        
        daily_loss_pct = (abs(self.daily_pnl) / self.config.daily_loss_limit_usdt * 100) \
            if self.config.daily_loss_limit_usdt > 0 else 0
        
        drawdown_pct = float(self.current_drawdown)
        
        # Determine risk level
        risk_level = self._determine_risk_level(
            exposure_pct=float(exposure_pct),
            daily_loss_pct=float(daily_loss_pct),
            drawdown_pct=drawdown_pct
        )
        
        return {
            "exposure_pct": float(exposure_pct),
            "daily_loss_pct": float(daily_loss_pct),
            "drawdown_pct": drawdown_pct,
            "risk_level": risk_level,
            "thresholds": {
                "max_position_size": float(self.config.max_position_size_usdt),
                "max_leverage": float(self.config.max_leverage),
                "daily_loss_limit": float(self.config.daily_loss_limit_usdt),
                "max_drawdown": float(self.config.max_drawdown_percent),
                "max_positions": self.config.max_positions
            }
        }
    
    def _check_daily_reset(self):
        """Reset daily metrics if new day"""
        current_date = datetime.utcnow().date()
        if current_date > self.last_reset:
            self.daily_pnl = Decimal("0")
            self.daily_trades = 0
            self.last_reset = current_date
            logger.info("Daily risk metrics reset")
    
    def _calculate_risk_score(
        self,
        leverage: float,
        drawdown: float,
        daily_loss: float,
        positions_count: int
    ) -> int:
        """
        Calculate overall risk score (0-100)
        
        Higher score = higher risk
        """
        score = 0
        
        # Leverage component (0-30 points)
        leverage_ratio = leverage / self.config.max_leverage if self.config.max_leverage > 0 else 0
        score += min(30, int(leverage_ratio * 30))
        
        # Drawdown component (0-30 points)
        drawdown_ratio = drawdown / float(self.config.max_drawdown_percent) if self.config.max_drawdown_percent > 0 else 0
        score += min(30, int(drawdown_ratio * 30))
        
        # Daily loss component (0-25 points)
        loss_ratio = daily_loss / float(self.config.daily_loss_limit_usdt) if self.config.daily_loss_limit_usdt > 0 else 0
        score += min(25, int(loss_ratio * 25))
        
        # Position count component (0-15 points)
        position_ratio = positions_count / self.config.max_positions if self.config.max_positions > 0 else 0
        score += min(15, int(position_ratio * 15))
        
        return min(100, score)
    
    def _determine_risk_level(
        self,
        exposure_pct: float,
        daily_loss_pct: float,
        drawdown_pct: float
    ) -> str:
        """Determine overall risk level based on metrics"""
        # Get maximum risk indicator
        max_pct = max(exposure_pct, daily_loss_pct, drawdown_pct)
        
        if max_pct < 40:
            return "low"
        elif max_pct < 70:
            return "medium"
        elif max_pct < 90:
            return "high"
        else:
            return "critical"
    
    def update_daily_pnl(self, pnl: Decimal):
        """Update daily P&L (called by trading service)"""
        self.daily_pnl += pnl
        self.daily_trades += 1
    
    def update_positions(self, positions: List[Dict[str, Any]]):
        """Update current positions for tracking"""
        self.current_positions.clear()
        self.total_exposure = Decimal("0")
        
        for pos in positions:
            symbol = pos.get('symbol', '')
            quantity = Decimal(str(pos.get('quantity', 0)))
            price = Decimal(str(pos.get('current_price', 0)))
            
            self.current_positions[symbol] = pos
            self.total_exposure += quantity * price