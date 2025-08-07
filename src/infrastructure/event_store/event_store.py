from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Type
from uuid import UUID
import json
import logging

logger = logging.getLogger(__name__)


class EventSerializer:
    """Handles serialization and deserialization of domain events"""
    
    @staticmethod
    def serialize(event: Any) -> Dict[str, Any]:
        """Convert domain event to dictionary for storage"""
        if hasattr(event, 'to_dict'):
            return event.to_dict()
        
        # Fallback for events without to_dict method
        data = {
            'event_type': event.__class__.__name__,
            'occurred_at': datetime.utcnow().isoformat()
        }
        
        # Convert dataclass to dict
        if hasattr(event, '__dataclass_fields__'):
            event_data = asdict(event)
            # Convert non-serializable types
            for key, value in event_data.items():
                if isinstance(value, UUID):
                    event_data[key] = str(value)
                elif isinstance(value, Decimal):
                    event_data[key] = str(value)
                elif isinstance(value, datetime):
                    event_data[key] = value.isoformat()
            data.update(event_data)
        
        return data
    
    @staticmethod
    def deserialize(data: Dict[str, Any], event_class: Type) -> Any:
        """Reconstruct domain event from stored data"""
        # Remove metadata fields
        event_data = data.copy()
        event_data.pop('event_type', None)
        event_data.pop('stream_id', None)
        event_data.pop('version', None)
        event_data.pop('stored_at', None)
        
        # Convert string UUIDs back to UUID objects
        for key, value in event_data.items():
            if key.endswith('_id') and isinstance(value, str):
                try:
                    event_data[key] = UUID(value)
                except ValueError:
                    pass
            elif key == 'occurred_at' and isinstance(value, str):
                event_data[key] = datetime.fromisoformat(value)
            elif isinstance(value, str) and key in ['amount', 'price', 'quantity']:
                try:
                    event_data[key] = Decimal(value)
                except:
                    pass
        
        return event_class(**event_data)


@dataclass
class StoredEvent:
    """Represents an event stored in the event store"""
    stream_id: str
    version: int
    event_type: str
    event_data: Dict[str, Any]
    stored_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stream_id': self.stream_id,
            'version': self.version,
            'event_type': self.event_type,
            'event_data': self.event_data,
            'stored_at': self.stored_at.isoformat()
        }


class EventStore(ABC):
    """Abstract base class for event stores"""
    
    @abstractmethod
    async def append(self, stream_id: str, events: List[Any], expected_version: Optional[int] = None) -> None:
        """
        Append events to a stream
        
        Args:
            stream_id: Unique identifier for the event stream (e.g., aggregate ID)
            events: List of domain events to append
            expected_version: Expected current version for optimistic concurrency control
        """
        pass
    
    @abstractmethod
    async def get_events(self, stream_id: str, from_version: int = 0) -> List[StoredEvent]:
        """
        Get events from a stream
        
        Args:
            stream_id: Stream identifier
            from_version: Get events after this version (0 for all events)
            
        Returns:
            List of stored events
        """
        pass
    
    @abstractmethod
    async def get_all_streams(self) -> List[str]:
        """Get list of all stream IDs"""
        pass


class InMemoryEventStore(EventStore):
    """In-memory implementation of event store for testing and development"""
    
    def __init__(self):
        self._streams: Dict[str, List[StoredEvent]] = {}
        self._serializer = EventSerializer()
    
    async def append(self, stream_id: str, events: List[Any], expected_version: Optional[int] = None) -> None:
        """Append events to stream with optimistic concurrency control"""
        if stream_id not in self._streams:
            self._streams[stream_id] = []
            current_version = 0
        else:
            current_version = len(self._streams[stream_id])
        
        # Check expected version for optimistic concurrency control
        if expected_version is not None and current_version != expected_version:
            raise ConcurrencyError(
                f"Expected version {expected_version} but current version is {current_version}"
            )
        
        # Append each event
        for event in events:
            current_version += 1
            stored_event = StoredEvent(
                stream_id=stream_id,
                version=current_version,
                event_type=event.__class__.__name__,
                event_data=self._serializer.serialize(event),
                stored_at=datetime.utcnow()
            )
            self._streams[stream_id].append(stored_event)
            
            logger.debug(f"Appended event {event.__class__.__name__} to stream {stream_id} at version {current_version}")
    
    async def get_events(self, stream_id: str, from_version: int = 0) -> List[StoredEvent]:
        """Get events from stream starting from specified version"""
        if stream_id not in self._streams:
            return []
        
        events = self._streams[stream_id]
        return [e for e in events if e.version > from_version]
    
    async def get_all_streams(self) -> List[str]:
        """Get all stream IDs"""
        return list(self._streams.keys())
    
    def clear(self) -> None:
        """Clear all events (for testing)"""
        self._streams.clear()


class PostgresEventStore(EventStore):
    """PostgreSQL implementation of event store for production use"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._serializer = EventSerializer()
        # TODO: Initialize database connection pool
    
    async def initialize(self) -> None:
        """Create database tables if they don't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            stream_id VARCHAR(255) NOT NULL,
            version INTEGER NOT NULL,
            event_type VARCHAR(255) NOT NULL,
            event_data JSONB NOT NULL,
            stored_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stream_id, version)
        );
        
        CREATE INDEX IF NOT EXISTS idx_events_stream_id ON events(stream_id);
        CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_stored_at ON events(stored_at);
        """
        # TODO: Execute SQL
    
    async def append(self, stream_id: str, events: List[Any], expected_version: Optional[int] = None) -> None:
        """Append events to stream with database transaction"""
        # TODO: Implement database transaction
        # 1. Start transaction
        # 2. Lock stream row for update
        # 3. Check expected version
        # 4. Insert events
        # 5. Commit transaction
        pass
    
    async def get_events(self, stream_id: str, from_version: int = 0) -> List[StoredEvent]:
        """Query events from database"""
        query = """
        SELECT stream_id, version, event_type, event_data, stored_at
        FROM events
        WHERE stream_id = %s AND version > %s
        ORDER BY version ASC
        """
        # TODO: Execute query and return results
        return []
    
    async def get_all_streams(self) -> List[str]:
        """Get distinct stream IDs from database"""
        query = "SELECT DISTINCT stream_id FROM events"
        # TODO: Execute query and return results
        return []


class EventProjection(ABC):
    """Base class for event projections/read models"""
    
    @abstractmethod
    async def handle(self, event: StoredEvent) -> None:
        """Handle an event and update the projection"""
        pass
    
    @abstractmethod
    async def rebuild(self, events: List[StoredEvent]) -> None:
        """Rebuild projection from event history"""
        pass


class PortfolioSummaryProjection(EventProjection):
    """Projection that maintains portfolio summaries"""
    
    def __init__(self):
        self.summaries: Dict[str, Dict[str, Any]] = {}
    
    async def handle(self, event: StoredEvent) -> None:
        """Update portfolio summary based on event"""
        portfolio_id = event.event_data.get('portfolio_id')
        if not portfolio_id:
            return
        
        if portfolio_id not in self.summaries:
            self.summaries[portfolio_id] = {
                'total_value': Decimal('0'),
                'available_cash': Decimal('0'),
                'positions': {},
                'pending_orders': 0,
                'last_updated': datetime.utcnow()
            }
        
        summary = self.summaries[portfolio_id]
        
        if event.event_type == 'PortfolioCreated':
            summary['available_cash'] = Decimal(event.event_data['initial_cash'])
            summary['total_value'] = Decimal(event.event_data['initial_cash'])
        
        elif event.event_type == 'FundsReserved':
            summary['available_cash'] -= Decimal(event.event_data['amount'])
        
        elif event.event_type == 'FundsReleased':
            summary['available_cash'] += Decimal(event.event_data['amount'])
        
        elif event.event_type == 'PositionUpdated':
            symbol = event.event_data['symbol']
            summary['positions'][symbol] = event.event_data['new_quantity']
        
        summary['last_updated'] = datetime.utcnow()
    
    async def rebuild(self, events: List[StoredEvent]) -> None:
        """Rebuild all summaries from event history"""
        self.summaries.clear()
        for event in events:
            await self.handle(event)
    
    def get_summary(self, portfolio_id: str) -> Optional[Dict[str, Any]]:
        """Get portfolio summary"""
        return self.summaries.get(portfolio_id)


class EventStoreError(Exception):
    """Base exception for event store errors"""
    pass


class ConcurrencyError(EventStoreError):
    """Raised when optimistic concurrency check fails"""
    pass


class StreamNotFoundError(EventStoreError):
    """Raised when stream doesn't exist"""
    pass