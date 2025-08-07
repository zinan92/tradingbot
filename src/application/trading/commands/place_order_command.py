from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

from src.domain.trading.value_objects import Symbol, Money
from src.domain.trading.aggregates.order import Order
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.repositories import IOrderRepository, IPortfolioRepository
from src.domain.trading.events import OrderPlaced


@dataclass
class PlaceOrderCommand:
    portfolio_id: UUID
    symbol: str
    quantity: int
    order_type: str = "MARKET"
    price: Optional[Decimal] = None


class PlaceOrderCommandHandler:
    def __init__(self,
                 portfolio_repo: IPortfolioRepository,
                 order_repo: IOrderRepository,
                 broker_service,  # MockBrokerService
                 event_bus):      # InMemoryEventBus
        self._portfolio_repo = portfolio_repo
        self._order_repo = order_repo
        self._broker_service = broker_service
        self._event_bus = event_bus
    
    def handle(self, command: PlaceOrderCommand) -> UUID:
        """
        Execute the place order use case following these steps:
        1. Validate command input
        2. Load portfolio from repository
        3. Check if portfolio has sufficient funds
        4. Create order domain object
        5. Save order to repository
        6. Submit order to broker
        7. Publish OrderPlaced event
        8. Return order ID
        """
        
        # Step 1: Validate command input
        self._validate_command(command)
        
        # Step 2: Load portfolio from repository
        portfolio = self._portfolio_repo.get(command.portfolio_id)
        if not portfolio:
            raise PortfolioNotFoundError(f"Portfolio {command.portfolio_id} not found")
        
        # Step 3 & 4: Check funds and create order (delegated to domain)
        # Create value objects
        symbol = Symbol(command.symbol)
        quantity = command.quantity  # Using int directly for now
        order_type = command.order_type
        price = float(command.price) if command.price else None
        
        # Domain logic: Portfolio creates order and checks business rules
        order = portfolio.place_order(
            symbol=symbol.value,
            quantity=quantity,
            order_type=order_type,
            price=price
        )
        
        # Step 5: Save order to repository
        self._order_repo.save(order)
        
        # Step 6: Submit order to broker
        broker_order_id = self._broker_service.submit_order_sync(order)
        order.set_broker_order_id(broker_order_id)
        
        # Save order again with broker ID
        self._order_repo.save(order)
        
        # Step 7: Publish domain events
        domain_events = order.pull_events()
        for event in domain_events:
            self._event_bus.publish(event)
        
        # Also publish portfolio events
        portfolio_events = portfolio.pull_events()
        for event in portfolio_events:
            self._event_bus.publish(event)
        
        # Save portfolio with updated funds
        self._portfolio_repo.save(portfolio)
        
        # Step 8: Return order ID
        return order.id


    def _validate_command(self, command: PlaceOrderCommand) -> None:
        """Validate command input parameters"""
        if not command.portfolio_id:
            raise ValueError("Portfolio ID is required")
        
        if not command.symbol or len(command.symbol.strip()) == 0:
            raise ValueError("Symbol is required")
        
        if command.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if command.order_type not in ["MARKET", "LIMIT"]:
            raise ValueError("Order type must be MARKET or LIMIT")
        
        if command.order_type == "LIMIT" and not command.price:
            raise ValueError("Price is required for LIMIT orders")
        
        if command.price and command.price <= 0:
            raise ValueError("Price must be positive")


# TODO: Define custom exceptions in domain layer
class PortfolioNotFoundError(Exception):
    pass