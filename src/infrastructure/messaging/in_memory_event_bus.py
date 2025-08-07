from typing import List, Dict, Callable, Any, Type, Optional
from collections import defaultdict
import asyncio
import inspect
from pydantic import BaseModel

from src.domain.shared.ports.event_bus import IEventBus, InvalidHandlerError


class InMemoryEventBus(IEventBus):
    """
    In-memory implementation of IEventBus for testing and development.
    
    Provides simple pub/sub functionality for domain events.
    Implements the IEventBus port from hexagonal architecture.
    """
    
    def __init__(self):
        self._handlers: Dict[Type[BaseModel], List[Callable]] = defaultdict(list)
        self._global_handlers: List[Callable] = []
        self._published_events: List[BaseModel] = []
        self._async_handlers: Dict[Type[BaseModel], List[Callable]] = defaultdict(list)
    
    def publish(self, event: BaseModel) -> None:
        """
        Publish a domain event synchronously.
        
        Args:
            event: The domain event to publish (must be a Pydantic model)
        """
        if not isinstance(event, BaseModel):
            raise InvalidHandlerError(f"Event must be a Pydantic BaseModel, got {type(event)}")
        
        # Store for testing/debugging
        self._published_events.append(event)
        
        # Call type-specific handlers
        event_type = type(event)
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                # Log error but don't stop other handlers
                print(f"Handler error: {e}")
        
        # Call global handlers
        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Global handler error: {e}")
    
    async def publish_async(self, event: BaseModel) -> None:
        """
        Publish a domain event asynchronously.
        
        Args:
            event: The domain event to publish
        """
        if not isinstance(event, BaseModel):
            raise InvalidHandlerError(f"Event must be a Pydantic BaseModel, got {type(event)}")
        
        # Store for testing/debugging
        self._published_events.append(event)
        
        # Gather all async tasks
        tasks = []
        
        # Type-specific async handlers
        event_type = type(event)
        for handler in self._async_handlers.get(event_type, []):
            if asyncio.iscoroutinefunction(handler):
                tasks.append(handler(event))
            else:
                # Wrap sync handler in async
                tasks.append(asyncio.create_task(asyncio.to_thread(handler, event)))
        
        # Execute all handlers concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def subscribe(self, event_type: Type[BaseModel], handler: Callable[[BaseModel], None]) -> None:
        """
        Subscribe a handler to a specific event type.
        
        Args:
            event_type: The Pydantic model class of events to handle
            handler: Function to call when event is published
        """
        # Validate handler signature
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        
        if len(params) != 1:
            raise InvalidHandlerError(f"Handler must accept exactly one parameter, got {len(params)}")
        
        # Store handler
        if asyncio.iscoroutinefunction(handler):
            self._async_handlers[event_type].append(handler)
        else:
            self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: Type[BaseModel], handler: Callable[[BaseModel], None]) -> None:
        """
        Unsubscribe a handler from an event type.
        
        Args:
            event_type: The event type to unsubscribe from
            handler: The handler to remove
        """
        if handler in self._handlers.get(event_type, []):
            self._handlers[event_type].remove(handler)
        if handler in self._async_handlers.get(event_type, []):
            self._async_handlers[event_type].remove(handler)
    
    def subscribe_to_all(self, handler: Callable[[BaseModel], None]) -> None:
        """
        Subscribe a handler to all events.
        
        Args:
            handler: Function to call for every published event
        """
        # Validate handler signature
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        
        if len(params) != 1:
            raise InvalidHandlerError(f"Handler must accept exactly one parameter, got {len(params)}")
        
        self._global_handlers.append(handler)
    
    def get_published_events(self) -> List[BaseModel]:
        """Get all published events (useful for testing)"""
        return self._published_events.copy()
    
    def get_events_of_type(self, event_type: Type[BaseModel]) -> List[BaseModel]:
        """Get all published events of a specific type (useful for testing)"""
        return [e for e in self._published_events if isinstance(e, event_type)]
    
    def clear(self) -> None:
        """Clear all handlers and events (useful for testing)"""
        self._handlers.clear()
        self._async_handlers.clear()
        self._global_handlers.clear()
        self._published_events.clear()
    
    def handler_count(self, event_type: Optional[Type[BaseModel]] = None) -> int:
        """Get count of registered handlers (useful for testing)"""
        if event_type:
            return len(self._handlers.get(event_type, [])) + len(self._async_handlers.get(event_type, []))
        return sum(len(h) for h in self._handlers.values()) + \
               sum(len(h) for h in self._async_handlers.values()) + \
               len(self._global_handlers)