"""
Cross-context event handlers for Strategy domain
These handlers listen to events from other contexts and trigger strategy actions
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
import logging

from src.domain.trading.events.order_events import OrderFilled, OrderCancelled
from src.domain.trading.events.portfolio_events import (
    PositionOpened,
    PositionClosed,
    RiskLimitExceeded
)

logger = logging.getLogger(__name__)


class StrategyOrderFilledHandler:
    """
    Handles OrderFilled events and updates strategy state
    
    When an order is filled, the strategy needs to:
    1. Update its internal tracking
    2. Potentially adjust future signals
    3. Record performance metrics
    """
    
    def __init__(self, strategy_repository, event_bus):
        self.strategy_repository = strategy_repository
        self.event_bus = event_bus
    
    async def handle(self, event: OrderFilled) -> None:
        """Process order fill and update strategy"""
        logger.info(f"Strategy handling OrderFilled: {event.order_id}")
        
        # Find strategy that placed this order
        # In production, we'd track order->strategy mapping
        strategies = await self.strategy_repository.get_active_strategies()
        
        for strategy in strategies:
            if await strategy.owns_order(event.order_id):
                # Update strategy state
                await strategy.record_fill(
                    order_id=event.order_id,
                    symbol=event.symbol,
                    quantity=event.quantity,
                    fill_price=event.fill_price
                )
                
                # Check if strategy needs adjustment
                if strategy.requires_rebalancing():
                    from src.domain.strategy.events import RebalanceRequired
                    rebalance_event = RebalanceRequired(
                        strategy_id=strategy.id,
                        reason="Order filled - portfolio drift detected",
                        occurred_at=datetime.utcnow()
                    )
                    await self.event_bus.publish(rebalance_event)
                
                # Save updated strategy
                await self.strategy_repository.save(strategy)
                
                # Publish strategy events
                for evt in strategy.pull_events():
                    await self.event_bus.publish(evt)
                
                break


class StrategyPositionClosedHandler:
    """
    Handles PositionClosed events to track strategy performance
    """
    
    def __init__(self, strategy_repository, metrics_service, event_bus):
        self.strategy_repository = strategy_repository
        self.metrics_service = metrics_service
        self.event_bus = event_bus
    
    async def handle(self, event: PositionClosed) -> None:
        """Process position closure and update metrics"""
        logger.info(f"Strategy handling PositionClosed: {event.symbol}")
        
        # Record trade metrics
        await self.metrics_service.record_trade(
            symbol=event.symbol,
            quantity=event.quantity,
            exit_price=event.exit_price,
            realized_pnl=event.realized_pnl,
            portfolio_id=event.portfolio_id
        )
        
        # Find associated strategy
        strategies = await self.strategy_repository.get_active_strategies()
        
        for strategy in strategies:
            if strategy.portfolio_id == event.portfolio_id:
                # Update strategy performance
                await strategy.record_closed_position(
                    symbol=event.symbol,
                    realized_pnl=event.realized_pnl
                )
                
                # Check if strategy should stop based on performance
                if strategy.should_stop():
                    from src.domain.strategy.events import StrategyStopped
                    stop_event = StrategyStopped(
                        strategy_id=strategy.id,
                        reason="Performance threshold reached",
                        final_pnl=strategy.total_pnl,
                        occurred_at=datetime.utcnow()
                    )
                    await self.event_bus.publish(stop_event)
                    
                    # Deactivate strategy
                    strategy.deactivate()
                
                await self.strategy_repository.save(strategy)
                break


class StrategyRiskLimitHandler:
    """
    Handles RiskLimitExceeded events and adjusts strategy behavior
    """
    
    def __init__(self, strategy_repository, event_bus):
        self.strategy_repository = strategy_repository
        self.event_bus = event_bus
    
    async def handle(self, event: RiskLimitExceeded) -> None:
        """Process risk limit breach and adjust strategies"""
        logger.warning(f"Strategy handling RiskLimitExceeded: {event.limit_type}")
        
        # Find strategies for this portfolio
        strategies = await self.strategy_repository.get_by_portfolio(event.portfolio_id)
        
        for strategy in strategies:
            if event.action_required == "STOP_TRADING":
                # Pause strategy
                strategy.pause(reason=f"Risk limit exceeded: {event.limit_type}")
                
                from src.domain.strategy.events import StrategyPaused
                pause_event = StrategyPaused(
                    strategy_id=strategy.id,
                    reason=f"Risk limit exceeded: {event.limit_type}",
                    occurred_at=datetime.utcnow()
                )
                await self.event_bus.publish(pause_event)
            
            elif event.action_required == "REDUCE_POSITION_SIZE":
                # Adjust strategy parameters
                strategy.reduce_position_sizing(factor=Decimal("0.5"))
                
                from src.domain.strategy.events import StrategyAdjusted
                adjust_event = StrategyAdjusted(
                    strategy_id=strategy.id,
                    adjustment_type="POSITION_SIZE_REDUCED",
                    parameters={"factor": "0.5"},
                    occurred_at=datetime.utcnow()
                )
                await self.event_bus.publish(adjust_event)
            
            await self.strategy_repository.save(strategy)


class MarketDataToStrategyHandler:
    """
    Routes market data events to relevant strategies for signal generation
    """
    
    def __init__(self, strategy_repository, signal_service, event_bus):
        self.strategy_repository = strategy_repository
        self.signal_service = signal_service
        self.event_bus = event_bus
    
    async def handle(self, event) -> None:
        """Process market data and generate signals"""
        from src.domain.shared.contracts.core_events import MarketDataReceived
        
        if not isinstance(event, MarketDataReceived):
            return
        
        logger.debug(f"Routing market data to strategies: {event.symbol}")
        
        # Get active strategies interested in this symbol
        strategies = await self.strategy_repository.get_active_for_symbol(event.symbol)
        
        for strategy in strategies:
            # Update strategy with latest price
            await strategy.update_market_data(
                symbol=event.symbol,
                price=event.price,
                volume=event.volume,
                timestamp=event.timestamp
            )
            
            # Check if strategy should generate signal
            if strategy.should_generate_signal():
                signal = await self.signal_service.generate_signal(
                    strategy=strategy,
                    symbol=event.symbol,
                    current_price=event.price
                )
                
                if signal:
                    from src.domain.strategy.events import SignalGenerated
                    signal_event = SignalGenerated(
                        strategy_id=strategy.id,
                        symbol=event.symbol,
                        signal_type=signal.type,
                        strength=signal.strength,
                        confidence=signal.confidence,
                        parameters=signal.parameters,
                        occurred_at=datetime.utcnow()
                    )
                    await self.event_bus.publish(signal_event)
            
            await self.strategy_repository.save(strategy)


class SignalToOrderHandler:
    """
    Converts trading signals into actual orders
    """
    
    def __init__(self, order_service, portfolio_repository, risk_service, event_bus):
        self.order_service = order_service
        self.portfolio_repository = portfolio_repository
        self.risk_service = risk_service
        self.event_bus = event_bus
    
    async def handle(self, event) -> None:
        """Convert signal to order after risk checks"""
        from src.domain.strategy.events import SignalGenerated
        
        if not isinstance(event, SignalGenerated):
            return
        
        logger.info(f"Converting signal to order: {event.symbol} {event.signal_type}")
        
        # Get portfolio for the strategy
        portfolio = await self.portfolio_repository.get_by_strategy(event.strategy_id)
        if not portfolio:
            logger.error(f"No portfolio found for strategy {event.strategy_id}")
            return
        
        # Calculate position size based on signal strength and portfolio
        position_size = await self.risk_service.calculate_position_size(
            portfolio=portfolio,
            symbol=event.symbol,
            signal_strength=event.strength,
            confidence=event.confidence
        )
        
        if position_size <= 0:
            logger.info(f"Position size is 0, skipping order for {event.symbol}")
            return
        
        # Perform risk checks
        risk_check = await self.risk_service.check_order_risk(
            portfolio=portfolio,
            symbol=event.symbol,
            quantity=position_size,
            order_side=event.signal_type
        )
        
        if not risk_check.approved:
            logger.warning(f"Risk check failed for {event.symbol}: {risk_check.reason}")
            
            from src.domain.risk.events import SignalRejected
            reject_event = SignalRejected(
                signal_id=event.event_id,
                reason=risk_check.reason,
                occurred_at=datetime.utcnow()
            )
            await self.event_bus.publish(reject_event)
            return
        
        # Create order from signal
        order = await self.order_service.create_from_signal(
            portfolio_id=portfolio.id,
            symbol=event.symbol,
            signal_type=event.signal_type,
            quantity=position_size,
            parameters=event.parameters
        )
        
        logger.info(f"Order created from signal: {order.id}")
        
        # Order events will be handled by the order service
        for evt in order.pull_events():
            await self.event_bus.publish(evt)