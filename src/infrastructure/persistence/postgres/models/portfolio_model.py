from sqlalchemy import (
    Column, String, Numeric, DateTime, Boolean, Text, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .base import Base


class PortfolioModel(Base):
    """
    SQLAlchemy model for Portfolio aggregate.
    
    Stores portfolio information with support for futures trading.
    """
    __tablename__ = "portfolios"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Portfolio details
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Account type
    account_type = Column(String(20), default="FUTURES")  # SPOT, FUTURES, MARGIN
    
    # Balances (all in base currency, typically USDT for futures)
    currency = Column(String(10), default="USDT")
    initial_balance = Column(Numeric(20, 8), nullable=False)
    available_balance = Column(Numeric(20, 8), nullable=False)
    reserved_balance = Column(Numeric(20, 8), default=0)
    
    # Futures specific balances
    wallet_balance = Column(Numeric(20, 8), default=0)  # Total wallet balance
    unrealized_pnl = Column(Numeric(20, 8), default=0)  # Unrealized PnL
    realized_pnl = Column(Numeric(20, 8), default=0)    # Realized PnL
    margin_balance = Column(Numeric(20, 8), default=0)  # Available margin
    initial_margin = Column(Numeric(20, 8), default=0)  # Used initial margin
    maintenance_margin = Column(Numeric(20, 8), default=0)  # Required maintenance margin
    
    # Leverage settings
    default_leverage = Column(Integer, default=1)
    max_leverage = Column(Integer, default=20)
    
    # Risk parameters
    max_position_size = Column(Numeric(20, 8), nullable=True)  # Max position value
    max_drawdown = Column(Numeric(10, 4), nullable=True)  # Max drawdown percentage
    daily_loss_limit = Column(Numeric(20, 8), nullable=True)  # Daily loss limit
    
    # Status
    is_active = Column(Boolean, default=True)
    is_live = Column(Boolean, default=False)  # False for paper trading
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Statistics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    largest_win = Column(Numeric(20, 8), default=0)
    largest_loss = Column(Numeric(20, 8), default=0)
    
    # Relationships
    orders = relationship("OrderModel", back_populates="portfolio", cascade="all, delete-orphan")
    positions = relationship("PositionModel", back_populates="portfolio", cascade="all, delete-orphan")
    
    def __repr__(self):
        return (
            f"<Portfolio(id={self.id}, name={self.name}, "
            f"balance={self.available_balance}, pnl={self.unrealized_pnl})>"
        )
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'account_type': self.account_type,
            'currency': self.currency,
            'initial_balance': float(self.initial_balance),
            'available_balance': float(self.available_balance),
            'reserved_balance': float(self.reserved_balance) if self.reserved_balance else 0,
            'wallet_balance': float(self.wallet_balance) if self.wallet_balance else 0,
            'unrealized_pnl': float(self.unrealized_pnl) if self.unrealized_pnl else 0,
            'realized_pnl': float(self.realized_pnl) if self.realized_pnl else 0,
            'margin_balance': float(self.margin_balance) if self.margin_balance else 0,
            'initial_margin': float(self.initial_margin) if self.initial_margin else 0,
            'maintenance_margin': float(self.maintenance_margin) if self.maintenance_margin else 0,
            'default_leverage': self.default_leverage,
            'max_leverage': self.max_leverage,
            'is_active': self.is_active,
            'is_live': self.is_live,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.calculate_win_rate(),
            'total_pnl': self.calculate_total_pnl()
        }
    
    def calculate_win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    def calculate_total_pnl(self) -> float:
        """Calculate total PnL (realized + unrealized)."""
        realized = float(self.realized_pnl) if self.realized_pnl else 0
        unrealized = float(self.unrealized_pnl) if self.unrealized_pnl else 0
        return realized + unrealized
    
    def calculate_margin_ratio(self) -> float:
        """
        Calculate margin ratio for liquidation risk.
        
        Returns:
            Margin ratio as percentage
        """
        if not self.maintenance_margin or self.maintenance_margin == 0:
            return 100.0
        
        margin_balance = float(self.margin_balance) if self.margin_balance else 0
        maintenance = float(self.maintenance_margin)
        
        return (margin_balance / maintenance) * 100
    
    def update_balance_for_order_fill(self, cost: float, fees: float = 0):
        """
        Update balances when an order is filled.
        
        Args:
            cost: Total cost of the order
            fees: Trading fees
        """
        from decimal import Decimal
        
        cost_decimal = Decimal(str(cost))
        fees_decimal = Decimal(str(fees))
        
        # Deduct cost and fees from available balance
        self.available_balance -= (cost_decimal + fees_decimal)
        
        # Release reserved balance if applicable
        if self.reserved_balance > 0:
            # Assume the cost was reserved
            self.reserved_balance = max(Decimal("0"), self.reserved_balance - cost_decimal)
    
    def update_pnl(self, realized: float = None, unrealized: float = None):
        """
        Update PnL values.
        
        Args:
            realized: Realized PnL to add
            unrealized: New unrealized PnL (replaces current)
        """
        from decimal import Decimal
        
        if realized is not None:
            self.realized_pnl = (self.realized_pnl or Decimal("0")) + Decimal(str(realized))
        
        if unrealized is not None:
            self.unrealized_pnl = Decimal(str(unrealized))
    
    @classmethod
    def from_domain(cls, portfolio):
        """
        Create model from domain Portfolio aggregate.
        
        Args:
            portfolio: Domain Portfolio object
            
        Returns:
            PortfolioModel instance
        """
        return cls(
            id=portfolio.id,
            name=portfolio.name,
            currency=portfolio.currency,
            initial_balance=portfolio.available_cash + portfolio.reserved_cash,
            available_balance=portfolio.available_cash,
            reserved_balance=portfolio.reserved_cash
        )