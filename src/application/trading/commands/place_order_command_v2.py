"""
Place Order Command with Pydantic v2 validation

This module implements the Place Order command with strong type safety
using Pydantic v2 models and proper value objects.
"""
from typing import Optional
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from src.domain.trading.value_objects import Symbol, Money
from src.domain.trading.value_objects.quantity import Quantity
from src.domain.trading.value_objects.price import Price
from src.domain.trading.value_objects.order_type import OrderType
from src.domain.trading.aggregates.order import Order
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.repositories import IOrderRepository, IPortfolioRepository
from src.domain.trading.events import OrderPlaced
from src.domain.shared.ports.event_bus import IEventBus
from src.domain.shared.ports.broker_service import IBrokerService


class PlaceOrderCommand(BaseModel):
    """
    Place Order Command with strict Pydantic v2 validation
    
    This command encapsulates all data needed to place a trading order,
    with strong type safety and validation at the application boundary.
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutable command
        str_strip_whitespace=True,  # Auto-strip whitespace
        validate_assignment=True,  # Validate on assignment
        use_enum_values=False,  # Keep enums as objects
        arbitrary_types_allowed=True  # Allow custom value objects
    )
    
    portfolio_id: UUID = Field(
        ...,
        description="UUID of the portfolio placing the order"
    )
    
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Trading symbol (e.g., AAPL, BTCUSDT)"
    )
    
    quantity: Quantity = Field(
        ...,
        description="Quantity to trade as value object"
    )
    
    order_type: OrderType = Field(
        ...,
        description="Type of order (MARKET or LIMIT)"
    )
    
    price: Optional[Price] = Field(
        None,
        description="Price for limit orders"
    )
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate and normalize symbol"""
        v = v.strip().upper()
        if not v:
            raise ValueError("Symbol cannot be empty")
        if not v.replace('-', '').replace('/', '').replace('_', '').isalnum():
            raise ValueError(f"Invalid symbol format: {v}")
        return v
    
    @field_validator('quantity', mode='before')
    @classmethod
    def convert_quantity(cls, v):
        """Convert raw value to Quantity value object"""
        if isinstance(v, Quantity):
            return v
        return Quantity(v)
    
    @field_validator('order_type', mode='before')
    @classmethod
    def convert_order_type(cls, v):
        """Convert string to OrderType value object"""
        if isinstance(v, OrderType):
            return v
        if isinstance(v, str):
            return OrderType.from_string(v)
        raise ValueError(f"Invalid order type: {v}")
    
    @field_validator('price', mode='before')
    @classmethod
    def convert_price(cls, v):
        """Convert raw value to Price value object if provided"""
        if v is None:
            return None
        if isinstance(v, Price):
            return v
        # Assume USD for now - in production, get from portfolio/config
        return Price(v, currency="USD")
    
    @model_validator(mode='after')
    def validate_limit_order_price(self):
        """Ensure limit orders have a price"""
        if self.order_type.is_limit() and self.price is None:
            raise ValueError("Price is required for LIMIT orders")
        if self.order_type.is_market() and self.price is not None:
            raise ValueError("Price should not be specified for MARKET orders")
        return self


class PlaceOrderCommandHandler:
    """
    Handler for PlaceOrderCommand with proper dependency injection
    
    Follows hexagonal architecture with clear separation between
    application logic and infrastructure concerns.
    """
    
    def __init__(self,
                 portfolio_repo: IPortfolioRepository,
                 order_repo: IOrderRepository,
                 broker_service: IBrokerService,
                 event_bus: IEventBus):
        """
        Initialize handler with injected dependencies
        
        All dependencies are abstractions (interfaces), not concrete implementations,
        following the Dependency Inversion Principle.
        """
        self._portfolio_repo = portfolio_repo
        self._order_repo = order_repo
        self._broker_service = broker_service
        self._event_bus = event_bus
    
    def handle(self, command: PlaceOrderCommand) -> UUID:
        """
        Execute the place order use case
        
        Steps:
        1. Load portfolio from repository
        2. Create order through portfolio (domain logic)
        3. Save order to repository
        4. Submit order to broker
        5. Update order with broker ID
        6. Publish domain events
        7. Save updated portfolio
        
        Args:
            command: Validated PlaceOrderCommand
            
        Returns:
            UUID: The order ID
            
        Raises:
            PortfolioNotFoundError: If portfolio doesn't exist
            InsufficientFundsError: If portfolio lacks funds
            BrokerError: If broker submission fails
        """
        # Step 1: Load portfolio
        portfolio = self._load_portfolio(command.portfolio_id)
        
        # Step 2: Create order (domain logic)
        order = self._create_order(portfolio, command)
        
        # Step 3: Save order
        self._order_repo.save(order)
        
        try:
            # Step 4: Submit to broker
            broker_order_id = self._submit_to_broker(order)
            
            # Step 5: Update order with broker ID
            order.set_broker_order_id(broker_order_id)
            self._order_repo.save(order)
            
        except Exception as e:
            # If broker submission fails, we still have the order saved
            # Could implement compensation logic here
            raise BrokerSubmissionError(f"Failed to submit order to broker: {e}")
        
        # Step 6: Publish events
        self._publish_events(order, portfolio)
        
        # Step 7: Save portfolio with updated state
        self._portfolio_repo.save(portfolio)
        
        return order.id
    
    def _load_portfolio(self, portfolio_id: UUID) -> Portfolio:
        """Load portfolio from repository"""
        portfolio = self._portfolio_repo.get(portfolio_id)
        if not portfolio:
            raise PortfolioNotFoundError(f"Portfolio {portfolio_id} not found")
        return portfolio
    
    def _create_order(self, portfolio: Portfolio, command: PlaceOrderCommand) -> Order:
        """
        Create order through portfolio domain logic
        
        The portfolio is responsible for:
        - Checking available funds
        - Reserving funds for the order
        - Creating the order with proper state
        """
        # Convert value objects to domain format
        symbol = Symbol(command.symbol)
        
        # Let portfolio create the order (domain logic)
        order = portfolio.place_order(
            symbol=symbol.value,
            quantity=command.quantity.to_int(),  # Convert to int for now
            order_type=command.order_type.value,
            price=command.price.to_float() if command.price else None
        )
        
        return order
    
    def _submit_to_broker(self, order: Order) -> str:
        """Submit order to broker service"""
        return self._broker_service.submit_order_sync(order)
    
    def _publish_events(self, order: Order, portfolio: Portfolio):
        """Publish domain events to event bus"""
        # Publish order events
        for event in order.pull_events():
            self._event_bus.publish(event)
        
        # Publish portfolio events
        for event in portfolio.pull_events():
            self._event_bus.publish(event)


# Domain Exceptions (should be in domain layer)
class PlaceOrderError(Exception):
    """Base exception for place order use case"""
    pass


class PortfolioNotFoundError(PlaceOrderError):
    """Raised when portfolio doesn't exist"""
    pass


class InsufficientFundsError(PlaceOrderError):
    """Raised when portfolio lacks funds for order"""
    pass


class BrokerSubmissionError(PlaceOrderError):
    """Raised when broker submission fails"""
    pass