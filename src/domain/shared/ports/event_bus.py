"""
Event Bus Port (Interface)

Defines the contract for event bus implementations.
Part of the hexagonal architecture's port layer.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Type
from pydantic import BaseModel


class IEventBus(ABC):
    """
    Event Bus interface for publishing and subscribing to domain events.
    
    This is a port in hexagonal architecture - implementations
    should be in the infrastructure layer.
    """
    
    @abstractmethod
    def publish(self, event: BaseModel) -> None:
        """
        Publish a domain event synchronously.
        
        Args:
            event: The domain event to publish (must be a Pydantic model)
            
        Raises:
            EventPublishError: If event cannot be published
        """
        pass
    
    @abstractmethod
    async def publish_async(self, event: BaseModel) -> None:
        """
        Publish a domain event asynchronously.
        
        Args:
            event: The domain event to publish
            
        Raises:
            EventPublishError: If event cannot be published
        """
        pass
    
    @abstractmethod
    def subscribe(self, event_type: Type[BaseModel], handler: Callable[[BaseModel], None]) -> None:
        """
        Subscribe a handler to a specific event type.
        
        Args:
            event_type: The Pydantic model class of events to handle
            handler: Function to call when event is published
            
        Raises:
            InvalidHandlerError: If handler signature is invalid
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, event_type: Type[BaseModel], handler: Callable[[BaseModel], None]) -> None:
        """
        Unsubscribe a handler from an event type.
        
        Args:
            event_type: The event type to unsubscribe from
            handler: The handler to remove
        """
        pass
    
    @abstractmethod
    def subscribe_to_all(self, handler: Callable[[BaseModel], None]) -> None:
        """
        Subscribe a handler to all events.
        
        Useful for logging, auditing, or event store implementations.
        
        Args:
            handler: Function to call for every published event
        """
        pass


class IEventStore(ABC):
    """
    Event Store interface for persisting domain events.
    
    Supports event sourcing patterns and audit trails.
    """
    
    @abstractmethod
    async def append(self, stream_id: str, events: List[BaseModel]) -> None:
        """
        Append events to a stream.
        
        Args:
            stream_id: The aggregate/stream identifier
            events: List of domain events to append
            
        Raises:
            ConcurrencyError: If optimistic concurrency check fails
        """
        pass
    
    @abstractmethod
    async def load_stream(self, stream_id: str, from_version: int = 0) -> List[BaseModel]:
        """
        Load events from a stream.
        
        Args:
            stream_id: The aggregate/stream identifier
            from_version: Start loading from this version (0 = beginning)
            
        Returns:
            List of domain events in order
        """
        pass
    
    @abstractmethod
    async def get_snapshot(self, stream_id: str) -> Optional[dict]:
        """
        Get the latest snapshot for a stream.
        
        Args:
            stream_id: The aggregate/stream identifier
            
        Returns:
            Snapshot data or None if no snapshot exists
        """
        pass
    
    @abstractmethod
    async def save_snapshot(self, stream_id: str, version: int, data: dict) -> None:
        """
        Save a snapshot for a stream.
        
        Args:
            stream_id: The aggregate/stream identifier
            version: The version number of the snapshot
            data: The snapshot data
        """
        pass


class EventBusError(Exception):
    """Base exception for event bus errors"""
    pass


class EventPublishError(EventBusError):
    """Raised when an event cannot be published"""
    pass


class InvalidHandlerError(EventBusError):
    """Raised when a handler has invalid signature"""
    pass


class ConcurrencyError(Exception):
    """Raised when optimistic concurrency check fails"""
    pass