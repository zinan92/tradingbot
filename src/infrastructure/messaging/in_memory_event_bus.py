from typing import List, Dict, Callable, Any
from collections import defaultdict


class InMemoryEventBus:
    """
    In-memory event bus for testing
    
    Provides simple pub/sub functionality for domain events.
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._published_events: List[Any] = []
    
    def publish(self, event: Any) -> None:
        """
        Publish an event to all registered handlers
        
        Args:
            event: The domain event to publish
        """
        # Store for testing/debugging
        self._published_events.append(event)
        
        # Get event name (assuming events have event_name property or class name)
        if hasattr(event, 'event_name'):
            event_name = event.event_name
        else:
            event_name = event.__class__.__name__
        
        # Call all registered handlers for this event
        for handler in self._handlers[event_name]:
            handler(event)
    
    def subscribe(self, event_name: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event type
        
        Args:
            event_name: The name of the event to subscribe to
            handler: The function to call when event is published
        """
        self._handlers[event_name].append(handler)
    
    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        """
        Unsubscribe a handler from an event type
        
        Args:
            event_name: The name of the event
            handler: The handler to remove
        """
        if handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)
    
    def get_published_events(self) -> List[Any]:
        """Get all published events (useful for testing)"""
        return self._published_events.copy()
    
    def clear(self) -> None:
        """Clear all handlers and events (useful for testing)"""
        self._handlers.clear()
        self._published_events.clear()