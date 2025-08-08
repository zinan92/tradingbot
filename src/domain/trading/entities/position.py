from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID, uuid4

from ..value_objects.price import Price
from ..value_objects.quantity import Quantity
from ..value_objects.leverage import Leverage
from ..value_objects.side import PositionSide, FuturesPosition


@dataclass
class Position:
    """
    Position Entity
    
    Represents an open trading position in futures markets.
    Tracks entry, current state, PnL, and risk metrics.
    """
    id: UUID
    symbol: str
    side: PositionSide
    quantity: Quantity
    entry_price: Price
    leverage: Leverage
    
    # Current market data
    mark_price: Price = None
    last_update: datetime = field(default_factory=datetime.utcnow)
    
    # Margin details
    initial_margin: Decimal = field(default_factory=lambda: Decimal("0"))
    maintenance_margin: Decimal = field(default_factory=lambda: Decimal("0"))
    margin_ratio: Decimal = field(default_factory=lambda: Decimal("0"))
    
    # PnL tracking
    unrealized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    realized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    
    # Risk metrics
    liquidation_price: Optional[Price] = None
    
    # Metadata
    portfolio_id: Optional[UUID] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    is_open: bool = True
    
    # Event sourcing support
    _events: List = field(default_factory=list, init=False)
    
    @classmethod
    def open_position(
        cls,
        symbol: str,
        side: PositionSide,
        quantity: Quantity,
        entry_price: Price,
        leverage: Leverage,
        portfolio_id: Optional[UUID] = None
    ):
        """
        Factory method to open a new position.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            side: Position side (LONG or SHORT)
            quantity: Position size
            entry_price: Entry price
            leverage: Leverage to use
            portfolio_id: Optional portfolio ID
            
        Returns:
            New Position instance
        """
        position_id = uuid4()
        
        # Calculate initial margin
        position_value = entry_price.value * Decimal(str(quantity.value))
        initial_margin = leverage.calculate_initial_margin(position_value)
        
        # Calculate liquidation price (simplified - using initial margin as wallet balance)
        liquidation_price_value = leverage.calculate_liquidation_price(
            entry_price=entry_price.value,
            position_side=side.value,
            wallet_balance=initial_margin,
            position_quantity=Decimal(str(quantity.value))
        )
        
        liquidation_price = Price(liquidation_price_value) if liquidation_price_value else None
        
        position = cls(
            id=position_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            leverage=leverage,
            mark_price=entry_price,  # Initially same as entry
            initial_margin=initial_margin,
            liquidation_price=liquidation_price,
            portfolio_id=portfolio_id
        )
        
        # TODO: Add PositionOpened event
        
        return position
    
    def update_mark_price(self, new_price: Price) -> None:
        """
        Update position with new market price.
        
        Args:
            new_price: Current market price
        """
        self.mark_price = new_price
        self.last_update = datetime.utcnow()
        
        # Recalculate unrealized PnL
        self.unrealized_pnl = self.calculate_unrealized_pnl(new_price)
        
        # Update margin ratio
        self.margin_ratio = self.calculate_margin_ratio(new_price)
        
        # Check if approaching liquidation
        if self.is_near_liquidation():
            # TODO: Emit LiquidationWarning event
            pass
    
    def calculate_unrealized_pnl(self, current_price: Optional[Price] = None) -> Decimal:
        """
        Calculate unrealized PnL.
        
        Args:
            current_price: Price to use for calculation (defaults to mark_price)
            
        Returns:
            Unrealized PnL amount
        """
        price = current_price or self.mark_price
        if not price:
            return Decimal("0")
        
        # Create FuturesPosition value object for calculation
        futures_pos = FuturesPosition(
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity.value,
            entry_price=self.entry_price.value,
            current_price=price.value,
            leverage=self.leverage.value
        )
        
        return futures_pos.calculate_pnl()
    
    def calculate_margin_ratio(self, current_price: Optional[Price] = None) -> Decimal:
        """
        Calculate current margin ratio.
        
        Args:
            current_price: Price to use for calculation
            
        Returns:
            Margin ratio as decimal (e.g., 0.05 = 5%)
        """
        price = current_price or self.mark_price
        if not price or self.initial_margin == 0:
            return Decimal("0")
        
        # Calculate based on unrealized PnL
        pnl = self.calculate_unrealized_pnl(price)
        
        # Margin ratio = (Initial Margin + PnL) / Position Value
        position_value = price.value * Decimal(str(self.quantity.value))
        available_margin = self.initial_margin + pnl
        
        if position_value == 0:
            return Decimal("0")
        
        return available_margin / position_value
    
    def is_near_liquidation(self, threshold: Decimal = Decimal("0.02")) -> bool:
        """
        Check if position is near liquidation.
        
        Args:
            threshold: Margin ratio threshold (default 2%)
            
        Returns:
            True if near liquidation
        """
        return self.margin_ratio <= threshold and self.margin_ratio > 0
    
    def add_to_position(self, additional_quantity: Quantity, price: Price) -> None:
        """
        Add to existing position (pyramiding).
        
        Args:
            additional_quantity: Quantity to add
            price: Execution price for addition
        """
        if not self.is_open:
            raise PositionClosedError("Cannot add to closed position")
        
        # Calculate new average entry price
        total_value = (self.entry_price.value * Decimal(str(self.quantity.value)) +
                      price.value * Decimal(str(additional_quantity.value)))
        new_quantity = self.quantity.value + additional_quantity.value
        
        new_entry_price = Price(total_value / Decimal(str(new_quantity)))
        
        # Update position
        self.quantity = Quantity(new_quantity)
        self.entry_price = new_entry_price
        
        # Recalculate margin and liquidation price
        position_value = new_entry_price.value * Decimal(str(new_quantity))
        self.initial_margin = self.leverage.calculate_initial_margin(position_value)
        
        liquidation_price_value = self.leverage.calculate_liquidation_price(
            entry_price=new_entry_price.value,
            position_side=self.side.value,
            wallet_balance=self.initial_margin,
            position_quantity=Decimal(str(new_quantity))
        )
        
        self.liquidation_price = Price(liquidation_price_value) if liquidation_price_value else None
        
        # TODO: Emit PositionIncreased event
    
    def reduce_position(self, reduce_quantity: Quantity, price: Price) -> Decimal:
        """
        Reduce position size (partial close).
        
        Args:
            reduce_quantity: Quantity to reduce
            price: Execution price for reduction
            
        Returns:
            Realized PnL from reduction
        """
        if not self.is_open:
            raise PositionClosedError("Cannot reduce closed position")
        
        if reduce_quantity.value > self.quantity.value:
            raise InvalidPositionOperationError("Cannot reduce more than position size")
        
        # Calculate PnL for reduced portion
        futures_pos = FuturesPosition(
            symbol=self.symbol,
            side=self.side,
            quantity=reduce_quantity.value,
            entry_price=self.entry_price.value,
            current_price=price.value,
            leverage=self.leverage.value
        )
        
        partial_pnl = futures_pos.calculate_pnl()
        
        # Update position
        remaining_quantity = self.quantity.value - reduce_quantity.value
        
        if remaining_quantity == 0:
            # Position fully closed
            self.close_position(price)
        else:
            # Update quantity and margins
            self.quantity = Quantity(remaining_quantity)
            position_value = self.entry_price.value * Decimal(str(remaining_quantity))
            self.initial_margin = self.leverage.calculate_initial_margin(position_value)
            
            # Add to realized PnL
            self.realized_pnl += partial_pnl
        
        # TODO: Emit PositionReduced event
        
        return partial_pnl
    
    def close_position(self, close_price: Price) -> Decimal:
        """
        Close the entire position.
        
        Args:
            close_price: Execution price for close
            
        Returns:
            Total realized PnL
        """
        if not self.is_open:
            raise PositionClosedError("Position already closed")
        
        # Calculate final PnL
        final_pnl = self.calculate_unrealized_pnl(close_price)
        self.realized_pnl += final_pnl
        
        # Mark as closed
        self.is_open = False
        self.closed_at = datetime.utcnow()
        self.unrealized_pnl = Decimal("0")
        
        # TODO: Emit PositionClosed event
        
        return self.realized_pnl
    
    def calculate_return_on_margin(self) -> Decimal:
        """
        Calculate return on margin (ROI).
        
        Returns:
            ROI as decimal (e.g., 0.5 = 50% return)
        """
        if self.initial_margin == 0:
            return Decimal("0")
        
        total_pnl = self.realized_pnl + self.unrealized_pnl
        return total_pnl / self.initial_margin
    
    def to_futures_position(self) -> FuturesPosition:
        """
        Convert to FuturesPosition value object.
        
        Returns:
            FuturesPosition value object
        """
        return FuturesPosition(
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity.value,
            entry_price=self.entry_price.value,
            current_price=self.mark_price.value if self.mark_price else self.entry_price.value,
            leverage=self.leverage.value
        )
    
    def pull_events(self) -> List:
        """Return and clear domain events."""
        events = self._events.copy()
        self._events.clear()
        return events
    
    def _add_event(self, event) -> None:
        """Add a domain event to be published."""
        self._events.append(event)


# Domain Exceptions
class PositionDomainError(Exception):
    """Base exception for Position domain errors."""
    pass


class PositionClosedError(PositionDomainError):
    """Raised when operation attempted on closed position."""
    pass


class InvalidPositionOperationError(PositionDomainError):
    """Raised when invalid operation attempted on position."""
    pass