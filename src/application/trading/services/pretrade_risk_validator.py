"""
Pre-Trade Risk Validator

Validates orders against risk limits before execution.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from src.config.trading_config import TradingConfig, get_config
from src.domain.trading.aggregates.order import Order
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.entities.position import Position

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result of risk validation"""
    passed: bool
    reason: Optional[str] = None
    checks_performed: List[str] = None
    risk_score: Decimal = Decimal("0")
    
    def __post_init__(self):
        if self.checks_performed is None:
            self.checks_performed = []


class PreTradeRiskValidator:
    """
    Validates orders against risk limits before submission.
    
    Checks:
    - Position limits
    - Leverage limits
    - Margin requirements
    - Daily loss limits
    - Concentration limits
    - Correlation limits
    """
    
    def __init__(
        self,
        portfolio_repository,
        position_repository,
        order_repository,
        config: Optional[TradingConfig] = None
    ):
        """
        Initialize risk validator.
        
        Args:
            portfolio_repository: Portfolio repository
            position_repository: Position repository
            order_repository: Order repository
            config: Trading configuration
        """
        self.portfolio_repo = portfolio_repository
        self.position_repo = position_repository
        self.order_repo = order_repository
        self.config = config or get_config()
        
        # Track daily metrics
        self.daily_losses: Dict[UUID, Decimal] = {}
        self.daily_trade_count: Dict[UUID, int] = {}
        self.last_reset = datetime.utcnow().date()
        
        logger.info("PreTradeRiskValidator initialized")
    
    async def validate_order(
        self,
        order: Order,
        portfolio: Portfolio,
        current_prices: Dict[str, Decimal]
    ) -> RiskCheckResult:
        """
        Validate order against all risk checks.
        
        Args:
            order: Order to validate
            portfolio: Current portfolio state
            current_prices: Current market prices
            
        Returns:
            RiskCheckResult with validation outcome
        """
        logger.debug(f"Validating order: {order.id}")
        
        # Reset daily counters if needed
        self._check_daily_reset()
        
        result = RiskCheckResult(passed=True)
        
        # Run all risk checks
        checks = [
            ("leverage_limit", self._check_leverage_limit(order)),
            ("margin_requirement", await self._check_margin_requirement(order, portfolio, current_prices)),
            ("position_limit", await self._check_position_limit(portfolio)),
            ("position_size", self._check_position_size(order, current_prices)),
            ("daily_loss", self._check_daily_loss_limit(portfolio)),
            ("concentration", await self._check_concentration_limit(order, portfolio)),
            ("correlation", await self._check_correlation_limit(order, portfolio)),
            ("max_drawdown", self._check_max_drawdown(portfolio))
        ]
        
        for check_name, check_result in checks:
            result.checks_performed.append(check_name)
            
            if not check_result[0]:  # Check failed
                result.passed = False
                result.reason = check_result[1]
                logger.warning(f"Risk check failed: {check_name} - {result.reason}")
                break
        
        # Calculate overall risk score
        if result.passed:
            result.risk_score = await self._calculate_risk_score(order, portfolio)
        
        logger.info(f"Risk validation {'passed' if result.passed else 'failed'}: {result.reason or 'All checks passed'}")
        
        return result
    
    def _check_leverage_limit(self, order: Order) -> tuple[bool, Optional[str]]:
        """
        Check if order leverage is within limits.
        
        Args:
            order: Order to check
            
        Returns:
            Tuple of (passed, reason)
        """
        if order.leverage:
            if order.leverage.value > self.config.risk.max_leverage:
                return False, f"Leverage {order.leverage.value}x exceeds limit {self.config.risk.max_leverage}x"
        
        return True, None
    
    async def _check_margin_requirement(
        self,
        order: Order,
        portfolio: Portfolio,
        current_prices: Dict[str, Decimal]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if portfolio has sufficient margin for order.
        
        Args:
            order: Order to check
            portfolio: Current portfolio
            current_prices: Current prices
            
        Returns:
            Tuple of (passed, reason)
        """
        # Get current price
        price = current_prices.get(order.symbol.value)
        if not price:
            return False, f"No price available for {order.symbol.value}"
        
        # Calculate required margin
        position_value = price * Decimal(str(order.quantity.value))
        leverage = order.leverage.value if order.leverage else 1
        required_margin = position_value / Decimal(str(leverage))
        
        # Check available margin
        available_margin = portfolio.available_cash - portfolio.initial_margin
        
        if required_margin > available_margin:
            return False, f"Insufficient margin: need {required_margin}, have {available_margin}"
        
        # Check margin utilization
        total_margin = portfolio.initial_margin + required_margin
        margin_utilization = total_margin / portfolio.available_cash if portfolio.available_cash > 0 else Decimal("1")
        
        if margin_utilization > Decimal("0.9"):  # 90% margin utilization limit
            return False, f"Margin utilization would be {margin_utilization:.1%} (limit: 90%)"
        
        return True, None
    
    async def _check_position_limit(self, portfolio: Portfolio) -> tuple[bool, Optional[str]]:
        """
        Check if portfolio is within position limits.
        
        Args:
            portfolio: Current portfolio
            
        Returns:
            Tuple of (passed, reason)
        """
        # Count open positions
        open_positions = await self.position_repo.find_open_positions(portfolio_id=portfolio.id)
        position_count = len(open_positions)
        
        if position_count >= self.config.risk.max_positions:
            return False, f"Already have {position_count} positions (limit: {self.config.risk.max_positions})"
        
        return True, None
    
    def _check_position_size(
        self,
        order: Order,
        current_prices: Dict[str, Decimal]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if order size is within limits.
        
        Args:
            order: Order to check
            current_prices: Current prices
            
        Returns:
            Tuple of (passed, reason)
        """
        price = current_prices.get(order.symbol.value)
        if not price:
            return False, f"No price available for {order.symbol.value}"
        
        position_value = price * Decimal(str(order.quantity.value))
        
        if position_value > self.config.risk.max_position_size_usdt:
            return False, f"Position value {position_value} exceeds limit {self.config.risk.max_position_size_usdt}"
        
        # Check minimum position size (avoid dust)
        min_position_value = Decimal("10")  # $10 minimum
        if position_value < min_position_value:
            return False, f"Position value {position_value} below minimum {min_position_value}"
        
        return True, None
    
    def _check_daily_loss_limit(self, portfolio: Portfolio) -> tuple[bool, Optional[str]]:
        """
        Check if portfolio is within daily loss limits.
        
        Args:
            portfolio: Current portfolio
            
        Returns:
            Tuple of (passed, reason)
        """
        # Get daily loss for portfolio
        daily_loss = self.daily_losses.get(portfolio.id, Decimal("0"))
        
        if abs(daily_loss) >= self.config.risk.daily_loss_limit_usdt:
            return False, f"Daily loss {abs(daily_loss)} at limit {self.config.risk.daily_loss_limit_usdt}"
        
        # Also check if we're close to the limit (90%)
        if abs(daily_loss) >= self.config.risk.daily_loss_limit_usdt * Decimal("0.9"):
            logger.warning(f"Daily loss {abs(daily_loss)} approaching limit")
        
        return True, None
    
    async def _check_concentration_limit(
        self,
        order: Order,
        portfolio: Portfolio
    ) -> tuple[bool, Optional[str]]:
        """
        Check portfolio concentration limits.
        
        Args:
            order: Order to check
            portfolio: Current portfolio
            
        Returns:
            Tuple of (passed, reason)
        """
        # Get current positions
        positions = await self.position_repo.find_open_positions(portfolio_id=portfolio.id)
        
        # Calculate exposure by symbol
        symbol_exposure: Dict[str, Decimal] = {}
        total_exposure = Decimal("0")
        
        for position in positions:
            value = position.mark_price.value * Decimal(str(position.quantity.value))
            symbol_exposure[position.symbol] = symbol_exposure.get(position.symbol, Decimal("0")) + value
            total_exposure += value
        
        # Add new order to exposure
        if order.symbol.value in symbol_exposure:
            # Would increase concentration
            current_concentration = symbol_exposure[order.symbol.value] / total_exposure if total_exposure > 0 else Decimal("0")
            
            # Check if already too concentrated (>30% in one symbol)
            max_concentration = Decimal("0.3")
            if current_concentration > max_concentration:
                return False, f"Position in {order.symbol.value} already {current_concentration:.1%} of portfolio (limit: {max_concentration:.1%})"
        
        return True, None
    
    async def _check_correlation_limit(
        self,
        order: Order,
        portfolio: Portfolio
    ) -> tuple[bool, Optional[str]]:
        """
        Check correlation between positions.
        
        Args:
            order: Order to check
            portfolio: Current portfolio
            
        Returns:
            Tuple of (passed, reason)
        """
        # Get current positions
        positions = await self.position_repo.find_open_positions(portfolio_id=portfolio.id)
        
        # Group by correlated assets (simplified - in production use correlation matrix)
        crypto_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        
        if order.symbol.value in crypto_symbols:
            # Count existing crypto positions
            crypto_positions = [p for p in positions if p.symbol in crypto_symbols]
            
            if len(crypto_positions) >= 2:
                return False, "Already have maximum correlated crypto positions"
        
        return True, None
    
    def _check_max_drawdown(self, portfolio: Portfolio) -> tuple[bool, Optional[str]]:
        """
        Check if portfolio is within drawdown limits.
        
        Args:
            portfolio: Current portfolio
            
        Returns:
            Tuple of (passed, reason)
        """
        # Calculate current drawdown
        # This would need historical peak tracking in production
        initial_value = portfolio.available_cash + portfolio.initial_margin
        current_value = portfolio.get_total_value()
        
        if initial_value > 0:
            drawdown = (initial_value - current_value) / initial_value * 100
            
            if drawdown > self.config.risk.max_drawdown_percent:
                return False, f"Drawdown {drawdown:.1f}% exceeds limit {self.config.risk.max_drawdown_percent}%"
        
        return True, None
    
    async def _calculate_risk_score(
        self,
        order: Order,
        portfolio: Portfolio
    ) -> Decimal:
        """
        Calculate overall risk score for order.
        
        Args:
            order: Order to score
            portfolio: Current portfolio
            
        Returns:
            Risk score (0-1, higher is riskier)
        """
        score = Decimal("0")
        weights = Decimal("0")
        
        # Leverage component (weight: 0.3)
        if order.leverage:
            leverage_score = Decimal(str(order.leverage.value)) / Decimal("125")
            score += leverage_score * Decimal("0.3")
            weights += Decimal("0.3")
        
        # Position concentration (weight: 0.2)
        positions = await self.position_repo.find_open_positions(portfolio_id=portfolio.id)
        concentration_score = Decimal(str(len(positions))) / Decimal(str(self.config.risk.max_positions))
        score += concentration_score * Decimal("0.2")
        weights += Decimal("0.2")
        
        # Margin utilization (weight: 0.3)
        if portfolio.available_cash > 0:
            margin_score = portfolio.initial_margin / portfolio.available_cash
            score += margin_score * Decimal("0.3")
            weights += Decimal("0.3")
        
        # Daily loss (weight: 0.2)
        daily_loss = abs(self.daily_losses.get(portfolio.id, Decimal("0")))
        if self.config.risk.daily_loss_limit_usdt > 0:
            loss_score = daily_loss / self.config.risk.daily_loss_limit_usdt
            score += loss_score * Decimal("0.2")
            weights += Decimal("0.2")
        
        # Normalize
        if weights > 0:
            score = score / weights
        
        return min(score, Decimal("1"))  # Cap at 1
    
    def _check_daily_reset(self) -> None:
        """Reset daily counters if new day"""
        current_date = datetime.utcnow().date()
        
        if current_date > self.last_reset:
            logger.info("Resetting daily risk counters")
            self.daily_losses.clear()
            self.daily_trade_count.clear()
            self.last_reset = current_date
    
    def update_daily_loss(self, portfolio_id: UUID, pnl: Decimal) -> None:
        """
        Update daily loss tracking.
        
        Args:
            portfolio_id: Portfolio ID
            pnl: Profit/loss amount
        """
        self._check_daily_reset()
        
        current_loss = self.daily_losses.get(portfolio_id, Decimal("0"))
        self.daily_losses[portfolio_id] = current_loss + pnl
        
        logger.debug(f"Portfolio {portfolio_id} daily P&L: {self.daily_losses[portfolio_id]}")
    
    def get_risk_metrics(self, portfolio_id: UUID) -> Dict:
        """
        Get current risk metrics for portfolio.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            Dictionary of risk metrics
        """
        daily_loss = self.daily_losses.get(portfolio_id, Decimal("0"))
        daily_trades = self.daily_trade_count.get(portfolio_id, 0)
        
        return {
            "daily_loss": float(daily_loss),
            "daily_loss_limit": float(self.config.risk.daily_loss_limit_usdt),
            "daily_loss_utilization": float(abs(daily_loss) / self.config.risk.daily_loss_limit_usdt) if self.config.risk.daily_loss_limit_usdt > 0 else 0,
            "daily_trades": daily_trades,
            "max_leverage": self.config.risk.max_leverage,
            "max_positions": self.config.risk.max_positions,
            "max_position_size": float(self.config.risk.max_position_size_usdt)
        }