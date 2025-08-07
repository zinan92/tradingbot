"""
Event Bus Configuration
Wires together all event handlers and manages event flow across contexts
"""

from typing import Dict, List, Type, Callable, Any
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from src.infrastructure.event_store.event_store import EventStore, InMemoryEventStore
from src.application.cross_context.strategy_event_handlers import (
    StrategyOrderFilledHandler,
    StrategyPositionClosedHandler,
    StrategyRiskLimitHandler,
    MarketDataToStrategyHandler,
    SignalToOrderHandler
)
from src.application.cross_context.risk_event_handlers import (
    RiskOrderPlacedHandler,
    RiskPositionMonitor,
    RiskMetricsCalculator,
    EmergencyRiskHandler
)

logger = logging.getLogger(__name__)


@dataclass
class EventSubscription:
    """Represents a subscription to an event type"""
    event_type: Type
    handler: Callable
    context: str
    priority: int = 0
    is_async: bool = True


class EnhancedEventBus:
    """
    Enhanced event bus with event store integration and cross-context routing
    
    Features:
    1. Event persistence via EventStore
    2. Priority-based handler execution
    3. Error handling and retry logic
    4. Event replay capability
    5. Metrics and monitoring
    """
    
    def __init__(self, event_store: EventStore = None):
        self.event_store = event_store or InMemoryEventStore()
        self._subscriptions: Dict[Type, List[EventSubscription]] = {}
        self._event_metrics = {
            'published': 0,
            'handled': 0,
            'failed': 0
        }
        self._handler_registry = {}
    
    def subscribe(self, event_type: Type, handler: Callable, context: str, priority: int = 0):
        """
        Subscribe a handler to an event type
        
        Args:
            event_type: The event class to subscribe to
            handler: The handler function/method
            context: The bounded context (e.g., 'trading', 'strategy', 'risk')
            priority: Handler priority (higher = executed first)
        """
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        
        subscription = EventSubscription(
            event_type=event_type,
            handler=handler,
            context=context,
            priority=priority,
            is_async=asyncio.iscoroutinefunction(handler)
        )
        
        self._subscriptions[event_type].append(subscription)
        
        # Sort by priority (descending)
        self._subscriptions[event_type].sort(key=lambda x: x.priority, reverse=True)
        
        logger.info(f"Subscribed {handler.__name__} from {context} to {event_type.__name__}")
    
    async def publish(self, event: Any, stream_id: str = None) -> None:
        """
        Publish an event to all subscribers
        
        Args:
            event: The event to publish
            stream_id: Optional stream ID for event store
        """
        event_type = type(event)
        logger.debug(f"Publishing event: {event_type.__name__}")
        
        # Persist event if stream_id provided
        if stream_id and self.event_store:
            try:
                await self.event_store.append(stream_id, [event])
            except Exception as e:
                logger.error(f"Failed to persist event: {e}")
        
        # Update metrics
        self._event_metrics['published'] += 1
        
        # Get subscribers for this event type
        subscriptions = self._subscriptions.get(event_type, [])
        
        # Also check for base class subscriptions
        for base_class in event_type.__bases__:
            subscriptions.extend(self._subscriptions.get(base_class, []))
        
        # Execute handlers by priority
        for subscription in subscriptions:
            try:
                await self._execute_handler(subscription, event)
                self._event_metrics['handled'] += 1
            except Exception as e:
                self._event_metrics['failed'] += 1
                logger.error(f"Handler {subscription.handler.__name__} failed: {e}")
                
                # Optionally retry or send to dead letter queue
                await self._handle_failure(subscription, event, e)
    
    async def _execute_handler(self, subscription: EventSubscription, event: Any):
        """Execute a single handler"""
        logger.debug(f"Executing {subscription.handler.__name__} for {type(event).__name__}")
        
        if subscription.is_async:
            await subscription.handler(event)
        else:
            # Run sync handler in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, subscription.handler, event)
    
    async def _handle_failure(self, subscription: EventSubscription, event: Any, error: Exception):
        """Handle handler failure"""
        # Log to dead letter queue
        logger.error(f"Failed event: {event}, Handler: {subscription.handler.__name__}, Error: {error}")
        
        # Could implement retry logic here
        # Could send to dead letter queue
        # Could trigger alerts
    
    async def replay_events(self, stream_id: str, from_version: int = 0):
        """
        Replay events from event store
        
        Useful for:
        1. Rebuilding projections
        2. Debugging
        3. Testing
        """
        if not self.event_store:
            raise ValueError("Event store not configured")
        
        events = await self.event_store.get_events(stream_id, from_version)
        
        for stored_event in events:
            # Reconstruct domain event
            # This would need proper deserialization
            await self.publish(stored_event.event_data)
    
    def get_metrics(self) -> Dict[str, int]:
        """Get event bus metrics"""
        return self._event_metrics.copy()
    
    def clear_subscriptions(self):
        """Clear all subscriptions (useful for testing)"""
        self._subscriptions.clear()


class EventBusConfigurator:
    """
    Configures and wires up all event handlers
    """
    
    def __init__(self):
        self.event_bus = None
        self.event_store = None
    
    def configure(self, dependencies: Dict[str, Any]) -> EnhancedEventBus:
        """
        Configure event bus with all handlers
        
        Args:
            dependencies: Dictionary of service dependencies
        """
        # Create event store
        self.event_store = dependencies.get('event_store', InMemoryEventStore())
        
        # Create event bus
        self.event_bus = EnhancedEventBus(self.event_store)
        
        # Configure Trading context handlers
        self._configure_trading_handlers(dependencies)
        
        # Configure Strategy context handlers
        self._configure_strategy_handlers(dependencies)
        
        # Configure Risk context handlers
        self._configure_risk_handlers(dependencies)
        
        # Configure cross-context handlers
        self._configure_cross_context_handlers(dependencies)
        
        logger.info("Event bus configuration completed")
        return self.event_bus
    
    def _configure_trading_handlers(self, dependencies):
        """Configure Trading context event handlers"""
        from src.domain.trading.events.order_events import OrderPlaced, OrderFilled, OrderCancelled
        from src.application.trading.events.order_filled_handler import OrderFilledHandler
        
        # Order filled handler
        if 'order_repository' in dependencies:
            handler = OrderFilledHandler(
                order_repository=dependencies['order_repository'],
                portfolio_repository=dependencies['portfolio_repository'],
                event_bus=self.event_bus
            )
            self.event_bus.subscribe(OrderFilled, handler.handle, 'trading', priority=10)
    
    def _configure_strategy_handlers(self, dependencies):
        """Configure Strategy context event handlers"""
        from src.domain.trading.events.order_events import OrderFilled
        from src.domain.trading.events.portfolio_events import PositionClosed, RiskLimitExceeded
        
        if 'strategy_repository' in dependencies:
            # Order filled in strategy
            handler = StrategyOrderFilledHandler(
                strategy_repository=dependencies['strategy_repository'],
                event_bus=self.event_bus
            )
            self.event_bus.subscribe(OrderFilled, handler.handle, 'strategy', priority=5)
            
            # Position closed performance tracking
            if 'metrics_service' in dependencies:
                handler = StrategyPositionClosedHandler(
                    strategy_repository=dependencies['strategy_repository'],
                    metrics_service=dependencies['metrics_service'],
                    event_bus=self.event_bus
                )
                self.event_bus.subscribe(PositionClosed, handler.handle, 'strategy', priority=5)
            
            # Risk limit handling
            handler = StrategyRiskLimitHandler(
                strategy_repository=dependencies['strategy_repository'],
                event_bus=self.event_bus
            )
            self.event_bus.subscribe(RiskLimitExceeded, handler.handle, 'strategy', priority=8)
    
    def _configure_risk_handlers(self, dependencies):
        """Configure Risk context event handlers"""
        from src.domain.trading.events.order_events import OrderPlaced
        from src.domain.trading.events.portfolio_events import PositionUpdated
        
        if 'risk_repository' in dependencies:
            # Order risk checking
            handler = RiskOrderPlacedHandler(
                risk_repository=dependencies['risk_repository'],
                portfolio_repository=dependencies['portfolio_repository'],
                market_data_service=dependencies.get('market_data_service'),
                event_bus=self.event_bus
            )
            self.event_bus.subscribe(OrderPlaced, handler.handle, 'risk', priority=15)
            
            # Position monitoring
            if 'position_service' in dependencies:
                handler = RiskPositionMonitor(
                    risk_repository=dependencies['risk_repository'],
                    position_service=dependencies['position_service'],
                    order_service=dependencies.get('order_service'),
                    event_bus=self.event_bus
                )
                self.event_bus.subscribe(PositionUpdated, handler.handle, 'risk', priority=10)
    
    def _configure_cross_context_handlers(self, dependencies):
        """Configure cross-context event handlers"""
        # Market data to strategy
        if 'strategy_repository' in dependencies and 'signal_service' in dependencies:
            from src.domain.shared.contracts.core_events import MarketDataReceived
            
            handler = MarketDataToStrategyHandler(
                strategy_repository=dependencies['strategy_repository'],
                signal_service=dependencies['signal_service'],
                event_bus=self.event_bus
            )
            self.event_bus.subscribe(MarketDataReceived, handler.handle, 'cross-context', priority=5)
        
        # Signal to order conversion
        if all(k in dependencies for k in ['order_service', 'portfolio_repository', 'risk_service']):
            from src.domain.strategy.events import SignalGenerated
            
            handler = SignalToOrderHandler(
                order_service=dependencies['order_service'],
                portfolio_repository=dependencies['portfolio_repository'],
                risk_service=dependencies['risk_service'],
                event_bus=self.event_bus
            )
            self.event_bus.subscribe(SignalGenerated, handler.handle, 'cross-context', priority=10)


def create_event_bus_with_defaults() -> EnhancedEventBus:
    """
    Create event bus with default configuration for testing
    """
    configurator = EventBusConfigurator()
    
    # Create minimal dependencies
    dependencies = {
        'event_store': InMemoryEventStore(),
        # Add mock repositories as needed
    }
    
    return configurator.configure(dependencies)


# Singleton instance for application
_event_bus_instance = None

def get_event_bus() -> EnhancedEventBus:
    """Get or create singleton event bus instance"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = create_event_bus_with_defaults()
    return _event_bus_instance