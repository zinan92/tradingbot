"""
Position Contracts

Pydantic models for position-related data transfer objects.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class PositionSide(str, Enum):
    """Position side enumeration"""
    LONG = "long"
    SHORT = "short"


class Position(BaseModel):
    """Position data transfer object"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    symbol: str = Field(..., description="Trading pair symbol")
    side: PositionSide = Field(..., description="Position side (long/short)")
    quantity: Decimal = Field(..., description="Position size")
    entry_price: Decimal = Field(..., description="Average entry price")
    current_price: Decimal = Field(..., description="Current market price")
    mark_price: Optional[Decimal] = Field(None, description="Mark price for futures")
    liquidation_price: Optional[Decimal] = Field(None, description="Liquidation price")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss")
    realized_pnl: Decimal = Field(Decimal("0"), description="Realized profit/loss")
    margin_used: Optional[Decimal] = Field(None, description="Margin used")
    leverage: Optional[Decimal] = Field(None, description="Position leverage")
    opened_at: datetime = Field(..., description="Position open time")
    updated_at: datetime = Field(..., description="Last update time")
    
    @property
    def pnl_percentage(self) -> Decimal:
        """Calculate PnL percentage"""
        if self.entry_price == 0:
            return Decimal("0")
        return ((self.current_price - self.entry_price) / self.entry_price) * 100
    
    @property
    def value(self) -> Decimal:
        """Calculate position value"""
        return self.quantity * self.current_price


class PositionUpdate(BaseModel):
    """Position update notification"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    symbol: str = Field(..., description="Trading pair symbol")
    side: PositionSide = Field(..., description="Position side")
    previous_quantity: Decimal = Field(..., description="Previous position size")
    new_quantity: Decimal = Field(..., description="New position size")
    entry_price: Decimal = Field(..., description="Updated entry price")
    realized_pnl: Decimal = Field(..., description="Realized PnL from update")
    reason: str = Field(..., description="Update reason")
    timestamp: datetime = Field(..., description="Update timestamp")


class PortfolioState(BaseModel):
    """Portfolio state snapshot"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    account_id: str = Field(..., description="Account identifier")
    balance: Decimal = Field(..., description="Available balance")
    equity: Decimal = Field(..., description="Total equity")
    margin_used: Decimal = Field(Decimal("0"), description="Used margin")
    margin_available: Decimal = Field(..., description="Available margin")
    positions: List[Position] = Field(default_factory=list, description="Open positions")
    total_unrealized_pnl: Decimal = Field(Decimal("0"), description="Total unrealized PnL")
    total_realized_pnl: Decimal = Field(Decimal("0"), description="Total realized PnL")
    leverage: Decimal = Field(Decimal("1"), description="Account leverage")
    timestamp: datetime = Field(..., description="State timestamp")
    
    @property
    def margin_level(self) -> Optional[Decimal]:
        """Calculate margin level percentage"""
        if self.margin_used == 0:
            return None
        return (self.equity / self.margin_used) * 100
    
    @property
    def free_margin(self) -> Decimal:
        """Calculate free margin"""
        return self.equity - self.margin_used