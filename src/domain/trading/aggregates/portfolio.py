from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID, uuid4
import logging

from .order import Order
from ..entities.position import Position
from ..value_objects.leverage import Leverage
from ..value_objects.price import Price
from ..value_objects.quantity import Quantity
from ..value_objects.side import PositionSide
from ..events.portfolio_events import (
    PortfolioCreated,
    FundsReserved,
    FundsReleased,
    PositionOpened,
    PositionClosed,
    PositionUpdated,
    OrderPlacedFromPortfolio,
    OrderFilledInPortfolio
)

logger = logging.getLogger(__name__)


@dataclass
class Portfolio:
    """
    Portfolio Aggregate Root
    
    Manages trading portfolio with cash balance and positions.
    Enforces business rules around fund availability and order placement.
    """
    id: UUID
    name: str
    available_cash: Decimal  # TODO: Replace with Money value object
    reserved_cash: Decimal = field(default_factory=lambda: Decimal("0"))
    currency: str = "USDT"  # Default to USDT for futures
    
    # Spot positions (symbol -> quantity)
    spot_positions: Dict[str, int] = field(default_factory=dict)
    
    # Futures positions (symbol -> Position entity)
    futures_positions: Dict[str, Position] = field(default_factory=dict)
    
    # Margin tracking for futures
    initial_margin: Decimal = field(default_factory=lambda: Decimal("0"))
    maintenance_margin: Decimal = field(default_factory=lambda: Decimal("0"))
    margin_ratio: Decimal = field(default_factory=lambda: Decimal("0"))
    
    # Risk limits
    max_leverage: int = 20  # Maximum allowed leverage
    max_position_size: Decimal = field(default_factory=lambda: Decimal("100000"))  # Max position value in USDT
    
    # Event sourcing support
    _events: List = field(default_factory=list, init=False)
    
    @classmethod
    def create(cls, name: str, initial_cash: Decimal, currency: str = "USD"):
        """Factory method to create a new portfolio"""
        portfolio_id = uuid4()
        
        if initial_cash < 0:
            raise InvalidInitialCashError("Initial cash cannot be negative")
        
        portfolio = cls(
            id=portfolio_id,
            name=name,
            available_cash=initial_cash,
            currency=currency
        )
        
        # Record domain event
        event = PortfolioCreated(
            portfolio_id=portfolio_id,
            name=name,
            initial_cash=initial_cash,
            currency=currency,
            occurred_at=datetime.utcnow()
        )
        portfolio._add_event(event)
        
        return portfolio
    
    def check_sufficient_funds(self, amount: Decimal) -> bool:
        """
        Check if portfolio has sufficient available funds
        
        Returns True if funds are available, False otherwise
        """
        # TODO: When using Money value object, check currency matches
        return self.available_cash >= amount
    
    def reserve_funds(self, amount: Decimal) -> None:
        """
        Reserve funds for a pending order
        
        Business Rule: Cannot reserve more than available cash
        """
        if amount <= 0:
            raise InvalidAmountError("Reserve amount must be positive")
        
        if not self.check_sufficient_funds(amount):
            raise InsufficientFundsError(
                f"Cannot reserve {amount} {self.currency}. "
                f"Available: {self.available_cash} {self.currency}"
            )
        
        self.available_cash -= amount
        self.reserved_cash += amount
        
        # Record domain event
        event = FundsReserved(
            portfolio_id=self.id,
            amount=amount,
            order_id=UUID(int=0),  # Will be updated when order is created
            reason="Order placement",
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
    
    def release_reserved_funds(self, amount: Decimal) -> None:
        """
        Release previously reserved funds (e.g., when order is cancelled)
        """
        if amount <= 0:
            raise InvalidAmountError("Release amount must be positive")
        
        if amount > self.reserved_cash:
            raise InvalidAmountError(
                f"Cannot release {amount} {self.currency}. "
                f"Reserved: {self.reserved_cash} {self.currency}"
            )
        
        self.reserved_cash -= amount
        self.available_cash += amount
        
        # Record domain event
        event = FundsReleased(
            portfolio_id=self.id,
            amount=amount,
            order_id=None,
            reason="Order cancelled or funds released",
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
    
    def place_order(self, 
                   symbol: str,           # TODO: Symbol
                   quantity: int,         # TODO: Quantity
                   order_type: str,       # TODO: OrderType
                   price: Optional[float] = None) -> Order:  # TODO: Optional[Money]
        """
        Place a new order from this portfolio
        
        Business Rules:
        - Must have sufficient funds for the order
        - Reserves funds for pending orders
        """
        # Calculate required funds
        # TODO: Use proper value objects and calculations
        if order_type == "MARKET":
            # For market orders, estimate with a buffer (e.g., 5% above current price)
            # In real implementation, would fetch current market price
            estimated_price = 100.0  # Placeholder
            required_funds = Decimal(str(estimated_price * quantity * 1.05))
        else:  # LIMIT order
            if not price:
                raise InvalidOrderError("Limit orders require a price")
            required_funds = Decimal(str(price * quantity))
        
        # Check and reserve funds
        if not self.check_sufficient_funds(required_funds):
            raise InsufficientFundsError(
                f"Insufficient funds for order. Required: {required_funds} {self.currency}, "
                f"Available: {self.available_cash} {self.currency}"
            )
        
        # Reserve the funds
        self.reserve_funds(required_funds)
        
        # Create the order
        order = Order.create(
            symbol=symbol,
            quantity=quantity,
            order_type=order_type,
            price=price
        )
        
        # Record domain event
        event = OrderPlacedFromPortfolio(
            portfolio_id=self.id,
            order_id=order.id,
            symbol=symbol,
            quantity=quantity,
            order_type=order_type,
            reserved_funds=required_funds,
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
        
        return order
    
    def add_position(self, symbol: str, quantity: int) -> None:
        """Add or update a spot position when an order is filled"""
        if quantity <= 0:
            raise InvalidAmountError("Position quantity must be positive")
        
        if symbol in self.spot_positions:
            self.spot_positions[symbol] += quantity
        else:
            self.spot_positions[symbol] = quantity
        
        # Record domain event
        old_quantity = self.spot_positions.get(symbol, 0)
        event = PositionUpdated(
            portfolio_id=self.id,
            symbol=symbol,
            old_quantity=old_quantity,
            new_quantity=old_quantity + quantity,
            price=Decimal("0"),  # Will be set by caller with actual price
            order_id=UUID(int=0),  # Will be set by caller
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
    
    def get_position(self, symbol: str) -> int:
        """Get current spot position for a symbol"""
        return self.spot_positions.get(symbol, 0)
    
    def complete_order_fill(self, 
                           symbol: str,
                           quantity: int,
                           fill_price: Decimal,
                           order_id) -> None:
        """
        Complete an order fill by adjusting reserved/spent funds
        
        When an order is filled:
        1. The actual cost is calculated from fill_price
        2. Reserved funds are converted to spent funds
        3. Any excess reserved funds are released back to available
        
        Args:
            symbol: The symbol that was filled
            quantity: Number of shares filled
            fill_price: Actual execution price
            order_id: The order that was filled
        """
        actual_cost = fill_price * Decimal(str(quantity))
        
        # We had reserved funds for this order
        # Now we need to adjust for the actual fill price
        # Assuming we reserved the maximum expected cost
        
        # For simplicity, we'll assume all reserved funds were for this order
        # In production, we'd track reserved funds per order
        if self.reserved_cash > 0:
            # Release all reserved funds first
            released = self.reserved_cash
            self.reserved_cash = Decimal("0")
            self.available_cash += released
            
            # Now deduct the actual cost
            if self.available_cash < actual_cost:
                raise InsufficientFundsError(
                    f"Insufficient funds for fill. Cost: {actual_cost}, Available: {self.available_cash}"
                )
            
            self.available_cash -= actual_cost
            
            # Record event
            event = OrderFilledInPortfolio(
                portfolio_id=self.id,
                order_id=order_id,
                symbol=symbol,
                quantity=quantity,
                fill_price=fill_price,
                actual_cost=actual_cost,
                commission=Decimal("0"),  # TODO: Add commission tracking
                occurred_at=datetime.utcnow()
            )
            self._add_event(event)
            
            logger.info(
                f"Portfolio {self.id}: Order filled for {quantity} {symbol} @ {fill_price}. "
                f"Cost: {actual_cost}, Available cash: {self.available_cash}"
            )
    
    def open_futures_position(
        self,
        symbol: str,
        side: PositionSide,
        quantity: int,
        entry_price: Decimal,
        leverage: int = 1
    ) -> Position:
        """
        Open a new futures position.
        
        Args:
            symbol: Trading symbol
            side: LONG or SHORT
            quantity: Position size
            entry_price: Entry price
            leverage: Leverage to use
            
        Returns:
            Position entity
            
        Raises:
            InsufficientFundsError: If insufficient margin
        """
        # Create value objects
        qty_vo = Quantity(quantity)
        price_vo = Price(entry_price)
        leverage_vo = Leverage(leverage)
        
        # Check if position already exists
        if symbol in self.futures_positions and self.futures_positions[symbol].is_open:
            raise InvalidOrderError(f"Position already exists for {symbol}")
        
        # Calculate required margin
        position_value = entry_price * Decimal(str(quantity))
        required_margin = leverage_vo.calculate_initial_margin(position_value)
        
        # Check available funds
        if not self.check_sufficient_funds(required_margin):
            raise InsufficientFundsError(
                f"Insufficient margin. Required: {required_margin} {self.currency}, "
                f"Available: {self.available_cash} {self.currency}"
            )
        
        # Reserve margin
        self.reserve_funds(required_margin)
        
        # Create position
        position = Position.open_position(
            symbol=symbol,
            side=side,
            quantity=qty_vo,
            entry_price=price_vo,
            leverage=leverage_vo,
            portfolio_id=self.id
        )
        
        # Store position
        self.futures_positions[symbol] = position
        
        # Update margin totals
        self.initial_margin += required_margin
        self._update_margin_ratio()
        
        # Record event
        event = PositionOpened(
            portfolio_id=self.id,
            position_id=position.id,
            symbol=symbol,
            side=side.value,
            quantity=quantity,
            entry_price=entry_price,
            leverage=leverage,
            margin_used=required_margin,
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
        
        return position
    
    def close_futures_position(
        self,
        symbol: str,
        close_price: Decimal
    ) -> Decimal:
        """
        Close a futures position.
        
        Args:
            symbol: Trading symbol
            close_price: Closing price
            
        Returns:
            Realized PnL
        """
        if symbol not in self.futures_positions:
            raise InvalidOrderError(f"No position found for {symbol}")
        
        position = self.futures_positions[symbol]
        if not position.is_open:
            raise InvalidOrderError(f"Position for {symbol} is already closed")
        
        # Close position and get PnL
        close_price_vo = Price(close_price)
        realized_pnl = position.close_position(close_price_vo)
        
        # Release margin
        self.release_reserved_funds(position.initial_margin)
        self.initial_margin -= position.initial_margin
        
        # Add PnL to available cash
        self.available_cash += realized_pnl
        
        # Update margin ratio
        self._update_margin_ratio()
        
        # Record event
        event = PositionClosed(
            portfolio_id=self.id,
            position_id=position.id,
            symbol=symbol,
            close_price=close_price,
            realized_pnl=realized_pnl,
            occurred_at=datetime.utcnow()
        )
        self._add_event(event)
        
        logger.info(
            f"Portfolio {self.id}: Closed {symbol} position. "
            f"PnL: {realized_pnl} {self.currency}"
        )
        
        return realized_pnl
    
    def update_position_prices(self, price_updates: Dict[str, Decimal]) -> None:
        """
        Update mark prices for all positions.
        
        Args:
            price_updates: Dictionary of symbol to new price
        """
        total_unrealized_pnl = Decimal("0")
        
        for symbol, price in price_updates.items():
            if symbol in self.futures_positions:
                position = self.futures_positions[symbol]
                if position.is_open:
                    price_vo = Price(price)
                    position.update_mark_price(price_vo)
                    total_unrealized_pnl += position.unrealized_pnl
        
        # Update margin ratio based on new prices
        self._update_margin_ratio()
        
        # Check for margin calls
        if self._is_margin_call():
            # TODO: Emit MarginCall event
            logger.warning(f"MARGIN CALL for portfolio {self.id}! Margin ratio: {self.margin_ratio}")
    
    def _update_margin_ratio(self) -> None:
        """Update portfolio margin ratio based on all positions."""
        if self.initial_margin == 0:
            self.margin_ratio = Decimal("1")
            return
        
        # Calculate total unrealized PnL
        total_unrealized = sum(
            pos.unrealized_pnl for pos in self.futures_positions.values()
            if pos.is_open
        )
        
        # Margin ratio = (Initial Margin + Unrealized PnL) / Initial Margin
        available_margin = self.initial_margin + total_unrealized
        self.margin_ratio = available_margin / self.initial_margin
    
    def _is_margin_call(self, threshold: Decimal = Decimal("0.5")) -> bool:
        """
        Check if portfolio is in margin call.
        
        Args:
            threshold: Margin ratio threshold (default 50%)
            
        Returns:
            True if margin call
        """
        return self.margin_ratio < threshold
    
    def get_total_exposure(self) -> Decimal:
        """Calculate total portfolio exposure across all positions."""
        total = Decimal("0")
        
        for position in self.futures_positions.values():
            if position.is_open:
                position_value = position.mark_price.value * Decimal(str(position.quantity.value))
                total += position_value
        
        return total
    
    def get_leverage_utilization(self) -> Decimal:
        """Calculate how much of available leverage is being used."""
        total_exposure = self.get_total_exposure()
        total_capital = self.available_cash + self.initial_margin
        
        if total_capital == 0:
            return Decimal("0")
        
        return total_exposure / total_capital
    
    def can_open_position(
        self,
        symbol: str,
        quantity: int,
        price: Decimal,
        leverage: int
    ) -> bool:
        """
        Check if portfolio can open a new position.
        
        Args:
            symbol: Trading symbol
            quantity: Position size
            price: Entry price
            leverage: Desired leverage
            
        Returns:
            True if position can be opened
        """
        # Check leverage limit
        if leverage > self.max_leverage:
            return False
        
        # Calculate required margin
        position_value = price * Decimal(str(quantity))
        leverage_vo = Leverage(leverage)
        required_margin = leverage_vo.calculate_initial_margin(position_value)
        
        # Check available funds
        if not self.check_sufficient_funds(required_margin):
            return False
        
        # Check position size limit
        if position_value > self.max_position_size:
            return False
        
        # Check if it would cause excessive leverage
        new_exposure = self.get_total_exposure() + position_value
        total_capital = self.available_cash + self.initial_margin
        
        if total_capital > 0:
            new_leverage_ratio = new_exposure / total_capital
            if new_leverage_ratio > self.max_leverage:
                return False
        
        return True
    
    def get_total_value(self) -> Decimal:
        """
        Calculate total portfolio value including positions.
        """
        # Cash + reserved + unrealized PnL
        total = self.available_cash + self.reserved_cash
        
        # Add unrealized PnL from futures
        for position in self.futures_positions.values():
            if position.is_open:
                total += position.unrealized_pnl
        
        return total
    
    def pull_events(self) -> List:
        """Return and clear domain events"""
        events = self._events.copy()
        self._events.clear()
        return events
    
    def _add_event(self, event) -> None:
        """Add a domain event to be published"""
        self._events.append(event)


# Domain Exceptions
class PortfolioDomainError(Exception):
    """Base exception for Portfolio domain errors"""
    pass


class InsufficientFundsError(PortfolioDomainError):
    """Raised when portfolio has insufficient funds for an operation"""
    pass


class InvalidAmountError(PortfolioDomainError):
    """Raised when an invalid amount is provided"""
    pass


class InvalidInitialCashError(PortfolioDomainError):
    """Raised when initial cash is invalid"""
    pass


class InvalidOrderError(PortfolioDomainError):
    """Raised when order parameters are invalid"""
    pass