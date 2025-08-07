"""
Cross-context event handlers for Risk domain
These handlers monitor events from other contexts and enforce risk rules
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
import logging

from src.domain.trading.events.order_events import OrderPlaced, OrderFilled
from src.domain.trading.events.portfolio_events import (
    PositionOpened,
    PositionUpdated,
    OrderPlacedFromPortfolio
)
from src.domain.strategy.events import SignalGenerated

logger = logging.getLogger(__name__)


class RiskOrderPlacedHandler:
    """
    Monitors OrderPlaced events for risk violations
    
    Checks:
    1. Position concentration limits
    2. Daily loss limits
    3. Correlation limits
    4. Leverage limits
    """
    
    def __init__(self, risk_repository, portfolio_repository, market_data_service, event_bus):
        self.risk_repository = risk_repository
        self.portfolio_repository = portfolio_repository
        self.market_data_service = market_data_service
        self.event_bus = event_bus
    
    async def handle(self, event: OrderPlaced) -> None:
        """Check order against risk limits"""
        logger.info(f"Risk checking OrderPlaced: {event.order_id}")
        
        # Get risk profile for portfolio
        risk_profile = await self.risk_repository.get_by_portfolio(event.portfolio_id)
        if not risk_profile:
            logger.warning(f"No risk profile for portfolio {event.portfolio_id}")
            return
        
        portfolio = await self.portfolio_repository.get(event.portfolio_id)
        
        # Check position concentration
        current_position = portfolio.get_position(event.symbol)
        new_position = current_position + event.quantity
        
        portfolio_value = await self._calculate_portfolio_value(portfolio)
        position_value = new_position * await self._get_current_price(event.symbol)
        concentration = position_value / portfolio_value if portfolio_value > 0 else Decimal("1")
        
        if concentration > risk_profile.max_position_concentration:
            await self._handle_limit_breach(
                event=event,
                limit_type="POSITION_CONCENTRATION",
                current_value=concentration,
                limit_value=risk_profile.max_position_concentration
            )
        
        # Check daily loss limit
        daily_pnl = await self._calculate_daily_pnl(portfolio)
        if daily_pnl < -risk_profile.max_daily_loss:
            await self._handle_limit_breach(
                event=event,
                limit_type="DAILY_LOSS",
                current_value=daily_pnl,
                limit_value=-risk_profile.max_daily_loss
            )
        
        # Check correlation limits
        if await self._exceeds_correlation_limit(portfolio, event.symbol, risk_profile):
            await self._handle_limit_breach(
                event=event,
                limit_type="CORRELATION",
                current_value=Decimal("0"),  # Placeholder
                limit_value=risk_profile.max_correlation
            )
    
    async def _handle_limit_breach(self, event, limit_type: str, current_value: Decimal, limit_value: Decimal):
        """Handle risk limit breach"""
        from src.domain.risk.events import RiskLimitBreached, OrderRejectedByRisk
        
        logger.warning(f"Risk limit breached: {limit_type} - Current: {current_value}, Limit: {limit_value}")
        
        # Publish risk limit breach event
        breach_event = RiskLimitBreached(
            portfolio_id=event.portfolio_id,
            order_id=event.order_id,
            limit_type=limit_type,
            current_value=current_value,
            limit_value=limit_value,
            action_taken="ORDER_REJECTED",
            occurred_at=datetime.utcnow()
        )
        await self.event_bus.publish(breach_event)
        
        # Publish order rejection event
        reject_event = OrderRejectedByRisk(
            order_id=event.order_id,
            reason=f"{limit_type} limit exceeded",
            occurred_at=datetime.utcnow()
        )
        await self.event_bus.publish(reject_event)
    
    async def _calculate_portfolio_value(self, portfolio) -> Decimal:
        """Calculate total portfolio value including positions"""
        total = portfolio.available_cash + portfolio.reserved_cash
        
        for symbol, quantity in portfolio.positions.items():
            price = await self._get_current_price(symbol)
            total += Decimal(str(quantity)) * price
        
        return total
    
    async def _get_current_price(self, symbol: str) -> Decimal:
        """Get current market price for symbol"""
        price_data = await self.market_data_service.get_latest_price(symbol)
        return price_data.price if price_data else Decimal("0")
    
    async def _calculate_daily_pnl(self, portfolio) -> Decimal:
        """Calculate today's P&L"""
        # This would query historical data
        # For now, return placeholder
        return Decimal("0")
    
    async def _exceeds_correlation_limit(self, portfolio, symbol: str, risk_profile) -> bool:
        """Check if adding position would exceed correlation limits"""
        # Would calculate correlation matrix
        # For now, return False
        return False


class RiskPositionMonitor:
    """
    Monitors position changes and enforces risk limits
    
    Features:
    1. Stop-loss monitoring
    2. Take-profit monitoring
    3. Trailing stop adjustments
    4. Portfolio rebalancing triggers
    """
    
    def __init__(self, risk_repository, position_service, order_service, event_bus):
        self.risk_repository = risk_repository
        self.position_service = position_service
        self.order_service = order_service
        self.event_bus = event_bus
    
    async def handle(self, event: PositionUpdated) -> None:
        """Monitor position changes and enforce stops"""
        logger.info(f"Risk monitoring position update: {event.symbol}")
        
        # Get risk profile
        risk_profile = await self.risk_repository.get_by_portfolio(event.portfolio_id)
        if not risk_profile:
            return
        
        # Get position details
        position = await self.position_service.get_position(
            portfolio_id=event.portfolio_id,
            symbol=event.symbol
        )
        
        if not position:
            return
        
        current_price = await self._get_current_price(event.symbol)
        
        # Check stop-loss
        if risk_profile.use_stop_loss:
            stop_price = position.entry_price * (Decimal("1") - risk_profile.stop_loss_percentage)
            
            if current_price <= stop_price:
                await self._trigger_stop_loss(position, stop_price)
        
        # Check take-profit
        if risk_profile.use_take_profit:
            target_price = position.entry_price * (Decimal("1") + risk_profile.take_profit_percentage)
            
            if current_price >= target_price:
                await self._trigger_take_profit(position, target_price)
        
        # Update trailing stop if needed
        if risk_profile.use_trailing_stop:
            await self._update_trailing_stop(position, current_price, risk_profile)
    
    async def _trigger_stop_loss(self, position, stop_price: Decimal):
        """Create stop-loss order"""
        from src.domain.risk.events import StopLossTriggered
        
        logger.warning(f"Stop-loss triggered for {position.symbol} at {stop_price}")
        
        # Create market sell order
        order = await self.order_service.create_market_order(
            portfolio_id=position.portfolio_id,
            symbol=position.symbol,
            quantity=position.quantity,
            side="SELL",
            reason="STOP_LOSS"
        )
        
        # Publish stop-loss event
        stop_event = StopLossTriggered(
            portfolio_id=position.portfolio_id,
            position_id=position.id,
            symbol=position.symbol,
            stop_price=stop_price,
            quantity=position.quantity,
            occurred_at=datetime.utcnow()
        )
        await self.event_bus.publish(stop_event)
    
    async def _trigger_take_profit(self, position, target_price: Decimal):
        """Create take-profit order"""
        from src.domain.risk.events import TakeProfitTriggered
        
        logger.info(f"Take-profit triggered for {position.symbol} at {target_price}")
        
        # Create limit sell order
        order = await self.order_service.create_limit_order(
            portfolio_id=position.portfolio_id,
            symbol=position.symbol,
            quantity=position.quantity,
            side="SELL",
            price=target_price,
            reason="TAKE_PROFIT"
        )
        
        # Publish take-profit event
        profit_event = TakeProfitTriggered(
            portfolio_id=position.portfolio_id,
            position_id=position.id,
            symbol=position.symbol,
            target_price=target_price,
            quantity=position.quantity,
            occurred_at=datetime.utcnow()
        )
        await self.event_bus.publish(profit_event)
    
    async def _update_trailing_stop(self, position, current_price: Decimal, risk_profile):
        """Adjust trailing stop based on price movement"""
        trail_percentage = risk_profile.trailing_stop_percentage
        new_stop = current_price * (Decimal("1") - trail_percentage)
        
        if new_stop > position.trailing_stop_price:
            position.trailing_stop_price = new_stop
            await self.position_service.save(position)
            
            from src.domain.risk.events import TrailingStopAdjusted
            adjust_event = TrailingStopAdjusted(
                position_id=position.id,
                symbol=position.symbol,
                old_stop=position.trailing_stop_price,
                new_stop=new_stop,
                occurred_at=datetime.utcnow()
            )
            await self.event_bus.publish(adjust_event)
    
    async def _get_current_price(self, symbol: str) -> Decimal:
        """Get current market price"""
        # Implementation would fetch from market data service
        return Decimal("100")


class RiskMetricsCalculator:
    """
    Calculates and publishes risk metrics periodically
    
    Metrics:
    1. VaR (Value at Risk)
    2. Sharpe Ratio
    3. Maximum Drawdown
    4. Beta
    5. Correlation Matrix
    """
    
    def __init__(self, portfolio_repository, market_data_service, event_bus):
        self.portfolio_repository = portfolio_repository
        self.market_data_service = market_data_service
        self.event_bus = event_bus
    
    async def calculate_portfolio_metrics(self, portfolio_id: UUID):
        """Calculate comprehensive risk metrics for portfolio"""
        portfolio = await self.portfolio_repository.get(portfolio_id)
        
        # Calculate VaR
        var_95 = await self._calculate_var(portfolio, confidence=0.95)
        var_99 = await self._calculate_var(portfolio, confidence=0.99)
        
        # Calculate Sharpe Ratio
        sharpe = await self._calculate_sharpe_ratio(portfolio)
        
        # Calculate Maximum Drawdown
        max_drawdown = await self._calculate_max_drawdown(portfolio)
        
        # Calculate Beta
        beta = await self._calculate_beta(portfolio)
        
        # Publish metrics event
        from src.domain.risk.events import RiskMetricsCalculated
        metrics_event = RiskMetricsCalculated(
            portfolio_id=portfolio_id,
            var_95=var_95,
            var_99=var_99,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            beta=beta,
            calculated_at=datetime.utcnow()
        )
        await self.event_bus.publish(metrics_event)
        
        return {
            'var_95': var_95,
            'var_99': var_99,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'beta': beta
        }
    
    async def _calculate_var(self, portfolio, confidence: float) -> Decimal:
        """Calculate Value at Risk"""
        # Would use historical simulation or Monte Carlo
        # Placeholder implementation
        portfolio_value = await self._get_portfolio_value(portfolio)
        return portfolio_value * Decimal("0.05")  # 5% VaR
    
    async def _calculate_sharpe_ratio(self, portfolio) -> Decimal:
        """Calculate Sharpe Ratio"""
        # Would calculate from returns history
        # Placeholder implementation
        return Decimal("1.5")
    
    async def _calculate_max_drawdown(self, portfolio) -> Decimal:
        """Calculate Maximum Drawdown"""
        # Would analyze historical equity curve
        # Placeholder implementation
        return Decimal("0.15")  # 15% max drawdown
    
    async def _calculate_beta(self, portfolio) -> Decimal:
        """Calculate portfolio beta vs market"""
        # Would calculate vs market index
        # Placeholder implementation
        return Decimal("1.2")
    
    async def _get_portfolio_value(self, portfolio) -> Decimal:
        """Get total portfolio value"""
        total = portfolio.available_cash + portfolio.reserved_cash
        
        for symbol, quantity in portfolio.positions.items():
            price = await self.market_data_service.get_latest_price(symbol)
            if price:
                total += Decimal(str(quantity)) * price.price
        
        return total


class EmergencyRiskHandler:
    """
    Handles emergency risk situations
    
    Actions:
    1. Circuit breaker activation
    2. Emergency position liquidation
    3. Trading halt
    4. Risk limit override
    """
    
    def __init__(self, order_service, portfolio_repository, event_bus):
        self.order_service = order_service
        self.portfolio_repository = portfolio_repository
        self.event_bus = event_bus
        self._circuit_breaker_active = False
    
    async def activate_circuit_breaker(self, reason: str):
        """Activate trading circuit breaker"""
        self._circuit_breaker_active = True
        
        from src.domain.risk.events import CircuitBreakerActivated
        event = CircuitBreakerActivated(
            reason=reason,
            activated_at=datetime.utcnow()
        )
        await self.event_bus.publish(event)
        
        logger.critical(f"CIRCUIT BREAKER ACTIVATED: {reason}")
    
    async def emergency_liquidate(self, portfolio_id: UUID, reason: str):
        """Liquidate all positions immediately"""
        logger.critical(f"EMERGENCY LIQUIDATION for portfolio {portfolio_id}: {reason}")
        
        portfolio = await self.portfolio_repository.get(portfolio_id)
        
        # Cancel all pending orders
        await self.order_service.cancel_all_pending(portfolio_id)
        
        # Liquidate all positions
        for symbol, quantity in portfolio.positions.items():
            if quantity > 0:
                # Create market sell order
                order = await self.order_service.create_market_order(
                    portfolio_id=portfolio_id,
                    symbol=symbol,
                    quantity=quantity,
                    side="SELL",
                    reason="EMERGENCY_LIQUIDATION"
                )
        
        from src.domain.risk.events import EmergencyLiquidation
        event = EmergencyLiquidation(
            portfolio_id=portfolio_id,
            reason=reason,
            positions_liquidated=len(portfolio.positions),
            occurred_at=datetime.utcnow()
        )
        await self.event_bus.publish(event)