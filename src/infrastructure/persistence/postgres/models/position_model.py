from sqlalchemy import (
    Column, String, Numeric, DateTime, Boolean, ForeignKey, Enum, Integer, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from .base import Base


class PositionSideEnum(enum.Enum):
    """Position side enumeration for database."""
    LONG = "LONG"
    SHORT = "SHORT"


class MarginTypeEnum(enum.Enum):
    """Margin type enumeration for database."""
    ISOLATED = "ISOLATED"
    CROSS = "CROSS"


class PositionModel(Base):
    """
    SQLAlchemy model for futures positions.
    
    Tracks open positions with PnL and margin calculations.
    """
    __tablename__ = "positions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Portfolio relationship
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False)
    
    # Position identifiers
    symbol = Column(String(20), nullable=False, index=True)
    position_side = Column(Enum(PositionSideEnum), nullable=False)
    
    # Position details
    quantity = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    mark_price = Column(Numeric(20, 8), nullable=False)
    liquidation_price = Column(Numeric(20, 8), nullable=True)
    
    # Leverage and margin
    leverage = Column(Integer, nullable=False, default=1)
    margin_type = Column(Enum(MarginTypeEnum), nullable=False, default=MarginTypeEnum.ISOLATED)
    initial_margin = Column(Numeric(20, 8), nullable=False)
    maintenance_margin = Column(Numeric(20, 8), nullable=False)
    margin_ratio = Column(Numeric(10, 4), nullable=True)  # Percentage
    
    # PnL tracking
    unrealized_pnl = Column(Numeric(20, 8), default=0)
    realized_pnl = Column(Numeric(20, 8), default=0)
    commission_paid = Column(Numeric(20, 8), default=0)
    
    # Risk metrics
    max_notional = Column(Numeric(20, 8), nullable=True)  # Maximum position value
    stop_loss_price = Column(Numeric(20, 8), nullable=True)
    take_profit_price = Column(Numeric(20, 8), nullable=True)
    trailing_stop_distance = Column(Numeric(20, 8), nullable=True)
    
    # Status
    is_open = Column(Boolean, default=True)
    is_hedged = Column(Boolean, default=False)  # For hedge mode
    auto_add_margin = Column(Boolean, default=False)  # Auto add margin to avoid liquidation
    
    # Timestamps
    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Order tracking
    opening_order_id = Column(UUID(as_uuid=True), nullable=True)
    closing_order_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Additional data
    metadata = Column(Text, nullable=True)  # JSON string for additional data
    notes = Column(Text, nullable=True)  # Trading notes
    
    # Relationships
    portfolio = relationship("PortfolioModel", back_populates="positions")
    
    def __repr__(self):
        return (
            f"<Position(id={self.id}, symbol={self.symbol}, "
            f"side={self.position_side.value if self.position_side else None}, "
            f"qty={self.quantity}, pnl={self.unrealized_pnl})>"
        )
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'portfolio_id': str(self.portfolio_id),
            'symbol': self.symbol,
            'position_side': self.position_side.value if self.position_side else None,
            'quantity': float(self.quantity),
            'entry_price': float(self.entry_price),
            'mark_price': float(self.mark_price),
            'liquidation_price': float(self.liquidation_price) if self.liquidation_price else None,
            'leverage': self.leverage,
            'margin_type': self.margin_type.value if self.margin_type else None,
            'initial_margin': float(self.initial_margin),
            'maintenance_margin': float(self.maintenance_margin),
            'margin_ratio': float(self.margin_ratio) if self.margin_ratio else None,
            'unrealized_pnl': float(self.unrealized_pnl) if self.unrealized_pnl else 0,
            'realized_pnl': float(self.realized_pnl) if self.realized_pnl else 0,
            'commission_paid': float(self.commission_paid) if self.commission_paid else 0,
            'stop_loss_price': float(self.stop_loss_price) if self.stop_loss_price else None,
            'take_profit_price': float(self.take_profit_price) if self.take_profit_price else None,
            'is_open': self.is_open,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'pnl_percentage': self.calculate_pnl_percentage(),
            'position_value': self.calculate_position_value(),
            'is_profitable': self.is_profitable()
        }
    
    def calculate_position_value(self) -> float:
        """Calculate current position value."""
        return float(self.quantity * self.mark_price)
    
    def calculate_pnl_percentage(self) -> float:
        """Calculate PnL as percentage of initial margin."""
        if not self.initial_margin or self.initial_margin == 0:
            return 0.0
        
        unrealized = float(self.unrealized_pnl) if self.unrealized_pnl else 0
        initial = float(self.initial_margin)
        
        return (unrealized / initial) * 100
    
    def is_profitable(self) -> bool:
        """Check if position is currently profitable."""
        return self.unrealized_pnl and self.unrealized_pnl > 0
    
    def is_at_risk(self, threshold: float = 150.0) -> bool:
        """
        Check if position is at risk of liquidation.
        
        Args:
            threshold: Margin ratio threshold (default 150%)
            
        Returns:
            True if margin ratio is below threshold
        """
        if not self.margin_ratio:
            return False
        return float(self.margin_ratio) < threshold
    
    def update_mark_price(self, new_price: float):
        """
        Update mark price and recalculate PnL.
        
        Args:
            new_price: New mark price
        """
        from decimal import Decimal
        
        self.mark_price = Decimal(str(new_price))
        
        # Recalculate unrealized PnL
        price_diff = self.mark_price - self.entry_price
        
        if self.position_side == PositionSideEnum.LONG:
            # Long positions profit when price increases
            self.unrealized_pnl = self.quantity * price_diff
        else:  # SHORT
            # Short positions profit when price decreases
            self.unrealized_pnl = self.quantity * (-price_diff)
        
        # Update margin ratio
        self.update_margin_ratio()
    
    def update_margin_ratio(self):
        """Recalculate margin ratio."""
        if not self.maintenance_margin or self.maintenance_margin == 0:
            self.margin_ratio = Decimal("100.0")
            return
        
        # Calculate account margin (initial margin + unrealized PnL)
        account_margin = self.initial_margin + (self.unrealized_pnl or Decimal("0"))
        
        # Calculate margin ratio
        self.margin_ratio = (account_margin / self.maintenance_margin) * Decimal("100")
    
    def close_position(self, exit_price: float, closing_order_id: uuid.UUID = None):
        """
        Close the position.
        
        Args:
            exit_price: Price at which position was closed
            closing_order_id: ID of the order that closed the position
        """
        from decimal import Decimal
        
        # Calculate final PnL
        price_diff = Decimal(str(exit_price)) - self.entry_price
        
        if self.position_side == PositionSideEnum.LONG:
            final_pnl = self.quantity * price_diff
        else:  # SHORT
            final_pnl = self.quantity * (-price_diff)
        
        # Move unrealized to realized
        self.realized_pnl = (self.realized_pnl or Decimal("0")) + final_pnl
        self.unrealized_pnl = Decimal("0")
        
        # Update status
        self.is_open = False
        self.closed_at = datetime.utcnow()
        self.closing_order_id = closing_order_id
        
        # Clear risk parameters
        self.quantity = Decimal("0")
        self.initial_margin = Decimal("0")
        self.maintenance_margin = Decimal("0")
    
    def add_to_position(self, additional_quantity: float, new_entry_price: float):
        """
        Add to existing position (averaging).
        
        Args:
            additional_quantity: Quantity to add
            new_entry_price: Price of the new entry
        """
        from decimal import Decimal
        
        add_qty = Decimal(str(additional_quantity))
        new_price = Decimal(str(new_entry_price))
        
        # Calculate new average entry price
        total_cost = (self.quantity * self.entry_price) + (add_qty * new_price)
        new_total_quantity = self.quantity + add_qty
        
        self.entry_price = total_cost / new_total_quantity
        self.quantity = new_total_quantity
        
        # Recalculate margins
        self.initial_margin = (self.quantity * self.entry_price) / Decimal(str(self.leverage))
        self.maintenance_margin = self.calculate_maintenance_margin()
        
        # Update PnL
        self.update_mark_price(float(self.mark_price))
    
    def reduce_position(self, reduce_quantity: float, exit_price: float):
        """
        Partially close position.
        
        Args:
            reduce_quantity: Quantity to reduce
            exit_price: Price at which to reduce
        """
        from decimal import Decimal
        
        reduce_qty = Decimal(str(reduce_quantity))
        exit_p = Decimal(str(exit_price))
        
        if reduce_qty >= self.quantity:
            # Full close
            self.close_position(exit_price)
            return
        
        # Calculate realized PnL for the reduced portion
        price_diff = exit_p - self.entry_price
        
        if self.position_side == PositionSideEnum.LONG:
            partial_pnl = reduce_qty * price_diff
        else:  # SHORT
            partial_pnl = reduce_qty * (-price_diff)
        
        # Update realized PnL
        self.realized_pnl = (self.realized_pnl or Decimal("0")) + partial_pnl
        
        # Reduce quantity
        self.quantity -= reduce_qty
        
        # Recalculate margins
        self.initial_margin = (self.quantity * self.entry_price) / Decimal(str(self.leverage))
        self.maintenance_margin = self.calculate_maintenance_margin()
        
        # Update unrealized PnL for remaining position
        self.update_mark_price(float(self.mark_price))
    
    def calculate_maintenance_margin(self) -> 'Decimal':
        """
        Calculate maintenance margin based on position value.
        
        Uses simplified tiered system.
        """
        from decimal import Decimal
        
        position_value = self.quantity * self.mark_price
        
        if position_value < 50000:
            rate = Decimal("0.004")  # 0.4%
        elif position_value < 250000:
            rate = Decimal("0.005")  # 0.5%
        elif position_value < 1000000:
            rate = Decimal("0.01")   # 1%
        elif position_value < 5000000:
            rate = Decimal("0.025")  # 2.5%
        else:
            rate = Decimal("0.05")   # 5%
        
        return position_value * rate