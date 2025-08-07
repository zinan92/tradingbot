from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Boolean, ForeignKey, Enum, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from .base import Base


class OrderStatusEnum(enum.Enum):
    """Order status enumeration for database."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    CANCELLED_CONFIRMED = "CANCELLED_CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderTypeEnum(enum.Enum):
    """Order type enumeration for database."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class OrderSideEnum(enum.Enum):
    """Order side enumeration for database."""
    BUY = "BUY"
    SELL = "SELL"


class PositionSideEnum(enum.Enum):
    """Position side for futures orders."""
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class OrderModel(Base):
    """
    SQLAlchemy model for Order aggregate.
    
    Stores order information with support for futures trading.
    """
    __tablename__ = "orders"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Order identifiers
    broker_order_id = Column(String(100), index=True, nullable=True)
    client_order_id = Column(String(100), unique=True, nullable=True)
    
    # Portfolio relationship
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=True)
    
    # Order details
    symbol = Column(String(20), nullable=False, index=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    filled_quantity = Column(Numeric(20, 8), default=0)
    
    # Order type and side
    order_type = Column(Enum(OrderTypeEnum), nullable=False)
    order_side = Column(Enum(OrderSideEnum), nullable=False)
    position_side = Column(Enum(PositionSideEnum), nullable=True)  # For futures
    
    # Prices
    price = Column(Numeric(20, 8), nullable=True)  # Limit price
    stop_price = Column(Numeric(20, 8), nullable=True)  # Stop price
    average_fill_price = Column(Numeric(20, 8), nullable=True)
    
    # Futures specific
    leverage = Column(Integer, default=1)
    reduce_only = Column(Boolean, default=False)
    close_position = Column(Boolean, default=False)
    
    # Status and timestamps
    status = Column(Enum(OrderStatusEnum), nullable=False, default=OrderStatusEnum.PENDING)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    filled_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    
    # Cancellation details
    cancellation_reason = Column(Text, nullable=True)
    cancelled_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Fees and commissions
    commission = Column(Numeric(20, 8), default=0)
    commission_asset = Column(String(10), default="USDT")
    
    # Time in force
    time_in_force = Column(String(10), default="GTC")
    
    # Additional metadata
    metadata = Column(Text, nullable=True)  # JSON string for additional data
    
    # Relationships
    portfolio = relationship("PortfolioModel", back_populates="orders")
    
    def __repr__(self):
        return (
            f"<Order(id={self.id}, symbol={self.symbol}, "
            f"type={self.order_type.value if self.order_type else None}, "
            f"side={self.order_side.value if self.order_side else None}, "
            f"qty={self.quantity}, status={self.status.value if self.status else None})>"
        )
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'broker_order_id': self.broker_order_id,
            'portfolio_id': str(self.portfolio_id) if self.portfolio_id else None,
            'symbol': self.symbol,
            'quantity': float(self.quantity),
            'filled_quantity': float(self.filled_quantity) if self.filled_quantity else 0,
            'order_type': self.order_type.value if self.order_type else None,
            'order_side': self.order_side.value if self.order_side else None,
            'position_side': self.position_side.value if self.position_side else None,
            'price': float(self.price) if self.price else None,
            'stop_price': float(self.stop_price) if self.stop_price else None,
            'average_fill_price': float(self.average_fill_price) if self.average_fill_price else None,
            'leverage': self.leverage,
            'reduce_only': self.reduce_only,
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'commission': float(self.commission) if self.commission else 0,
            'time_in_force': self.time_in_force
        }
    
    @classmethod
    def from_domain(cls, order):
        """
        Create model from domain Order aggregate.
        
        Args:
            order: Domain Order object
            
        Returns:
            OrderModel instance
        """
        return cls(
            id=order.id,
            broker_order_id=order.broker_order_id,
            symbol=order.symbol,
            quantity=order.quantity,
            order_type=OrderTypeEnum[order.order_type.upper()],
            order_side=OrderSideEnum.BUY,  # Default, should be determined from context
            price=order.price,
            status=OrderStatusEnum[order.status.value],
            created_at=order.created_at,
            filled_at=order.filled_at,
            cancelled_at=order.cancelled_at,
            cancellation_reason=order.cancellation_reason
        )