"""
Base Domain Events using Pydantic v2

Provides base classes and common event types for the trading domain.
Uses Pydantic v2 for strict runtime validation and serialization.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from decimal import Decimal
from typing import Optional, ClassVar
from uuid import UUID, uuid4


class DomainEvent(BaseModel):
    """
    Base class for all domain events.
    
    Uses Pydantic v2 for validation and serialization.
    Implements immutability and proper event metadata.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Make events immutable
        validate_assignment=True,
        arbitrary_types_allowed=True,
        json_encoders={
            UUID: str,
            Decimal: str,
            datetime: lambda v: v.isoformat()
        },
        str_strip_whitespace=True
    )
    
    # Event metadata
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_name: ClassVar[str] = "DomainEvent"  # Override in subclasses
    occurred_at: datetime = Field(default_factory=datetime.utcnow, description="When the event occurred")
    correlation_id: Optional[UUID] = Field(None, description="Correlation ID for event tracing")
    causation_id: Optional[UUID] = Field(None, description="ID of the event that caused this one")
    
    @property
    def aggregate_type(self) -> str:
        """Get the aggregate type this event belongs to"""
        return self.__class__.__module__.split('.')[-2]  # e.g., 'trading', 'risk', etc.
    
    def to_integration_event(self) -> dict:
        """Convert to integration event format for external systems"""
        return {
            "event_id": str(self.event_id),
            "event_name": self.event_name,
            "occurred_at": self.occurred_at.isoformat(),
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "payload": self.model_dump(exclude={"event_id", "occurred_at", "correlation_id", "causation_id"})
        }


class TradingEvent(DomainEvent):
    """Base class for trading domain events"""
    pass


class OrderEvent(TradingEvent):
    """Base class for order-related events"""
    
    order_id: UUID = Field(..., description="The order aggregate ID")
    
    @field_validator('order_id')
    @classmethod
    def validate_order_id(cls, v: UUID) -> UUID:
        """Ensure order_id is not a null UUID"""
        if v == UUID(int=0):
            raise ValueError("Order ID cannot be null UUID")
        return v


class PortfolioEvent(TradingEvent):
    """Base class for portfolio-related events"""
    
    portfolio_id: UUID = Field(..., description="The portfolio aggregate ID")
    
    @field_validator('portfolio_id')
    @classmethod
    def validate_portfolio_id(cls, v: UUID) -> UUID:
        """Ensure portfolio_id is not a null UUID"""
        if v == UUID(int=0):
            raise ValueError("Portfolio ID cannot be null UUID")
        return v