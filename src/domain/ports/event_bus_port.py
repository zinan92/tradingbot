"""
Event bus port interface.

Defines the contract for event publishing and subscription.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DomainEvent:
    """Base class for domain events."""
    event_id: str
    occurred_at: datetime
    aggregate_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.__class__.__name__,
            "occurred_at": self.occurred_at.isoformat(),
            "aggregate_id": self.aggregate_id
        }


class EventHandler(ABC):
    """Base class for event handlers."""
    
    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """
        Handle a domain event.
        
        Args:
            event: Event to handle
        """
        pass


class EventBusPort(ABC):
    """
    Port interface for event bus.
    
    All event bus implementations must implement this interface.
    """
    
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """
        Publish an event.
        
        Args:
            event: Event to publish
        """
        pass
    
    @abstractmethod
    async def publish_batch(self, events: List[DomainEvent]) -> None:
        """
        Publish multiple events.
        
        Args:
            events: List of events to publish
        """
        pass
    
    @abstractmethod
    def subscribe(
        self,
        event_type: Type[DomainEvent],
        handler: EventHandler
    ) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Handler for the event
        """
        pass
    
    @abstractmethod
    def unsubscribe(
        self,
        event_type: Type[DomainEvent],
        handler: EventHandler
    ) -> None:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler to remove
        """
        pass
    
    @abstractmethod
    def subscribe_callback(
        self,
        event_type: Type[DomainEvent],
        callback: Callable[[DomainEvent], None]
    ) -> None:
        """
        Subscribe a callback function to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Callback function
        """
        pass
    
    @abstractmethod
    def unsubscribe_callback(
        self,
        event_type: Type[DomainEvent],
        callback: Callable[[DomainEvent], None]
    ) -> None:
        """
        Unsubscribe a callback function from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback function to remove
        """
        pass
    
    @abstractmethod
    async def wait_for(
        self,
        event_type: Type[DomainEvent],
        timeout: Optional[float] = None
    ) -> Optional[DomainEvent]:
        """
        Wait for an event of specific type.
        
        Args:
            event_type: Type of event to wait for
            timeout: Timeout in seconds
            
        Returns:
            Event if received within timeout, None otherwise
        """
        pass
    
    @abstractmethod
    def get_handlers(self, event_type: Type[DomainEvent]) -> List[EventHandler]:
        """
        Get all handlers for an event type.
        
        Args:
            event_type: Type of event
            
        Returns:
            List of handlers
        """
        pass
    
    @abstractmethod
    def clear_handlers(self, event_type: Optional[Type[DomainEvent]] = None) -> None:
        """
        Clear handlers for an event type or all handlers.
        
        Args:
            event_type: Optional event type to clear handlers for
        """
        pass
    
    @abstractmethod
    def get_event_history(
        self,
        event_type: Optional[Type[DomainEvent]] = None,
        limit: int = 100
    ) -> List[DomainEvent]:
        """
        Get event history.
        
        Args:
            event_type: Optional filter by event type
            limit: Maximum number of events
            
        Returns:
            List of historical events
        """
        pass