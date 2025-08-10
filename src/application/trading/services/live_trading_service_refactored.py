"""
Live Trading Service (Refactored)

Manages live trading sessions using domain ports only.
No direct infrastructure dependencies.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set, Any
from uuid import UUID, uuid4

from src.config.trading_config import TradingConfig
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.entities.position import Position
from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.shared.ports import ExecutionPort, RiskPort, RiskAction
from src.domain.shared.contracts import (
    OrderRequest,
    OrderResponse,
    Position as PositionDTO,
    PortfolioState
)

logger = logging.getLogger(__name__)


class TradingSessionStatus(Enum):
    """Trading session status"""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    ERROR = "ERROR"
    LOCKED = "LOCKED"  # Emergency stop state - requires manual unlock


@dataclass
class TradingSession:
    """Represents a live trading session"""
    id: UUID
    portfolio_id: UUID
    status: TradingSessionStatus
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    max_drawdown: Decimal = field(default_factory=lambda: Decimal("0"))
    error_message: Optional[str] = None


class LiveTradingService:
    """
    Service for managing live trading using domain ports
    
    Uses only abstract ports - no infrastructure dependencies
    """
    
    def __init__(
        self,
        execution_port: ExecutionPort,
        risk_port: RiskPort,
        event_bus,  # Accept any object with publish method
        portfolio_repository,
        order_repository,
        position_repository,
        config: TradingConfig
    ):
        """
        Initialize live trading service with ports
        
        Args:
            execution_port: Port for order execution
            event_bus: Port for event publishing
            portfolio_repository: Portfolio repository
            order_repository: Order repository
            position_repository: Position repository
            config: Trading configuration
        """
        self.execution_port = execution_port
        self.risk_port = risk_port
        self.event_bus = event_bus
        self.portfolio_repository = portfolio_repository
        self.order_repository = order_repository
        self.position_repository = position_repository
        self.config = config
        
        # Session management
        self.current_session: Optional[TradingSession] = None
        self.active_orders: Dict[UUID, Order] = {}
        self.active_positions: Dict[str, Position] = {}
        
        # Control flags
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self.metrics = {
            "orders_placed": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "total_volume": Decimal("0"),
            "total_fees": Decimal("0")
        }
    
    async def start_session(self, portfolio_id: UUID) -> TradingSession:
        """
        Start a new trading session
        
        Args:
            portfolio_id: Portfolio to trade with
            
        Returns:
            Created trading session
        """
        if self.current_session and self.current_session.status == TradingSessionStatus.RUNNING:
            raise ValueError("A trading session is already running")
        
        # Get portfolio
        portfolio = self.portfolio_repository.get(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Create session
        self.current_session = TradingSession(
            id=uuid4(),
            portfolio_id=portfolio_id,
            status=TradingSessionStatus.STARTING,
            started_at=datetime.utcnow()
        )
        
        logger.info(f"Starting trading session {self.current_session.id}")
        
        try:
            # Start background tasks
            self._running = True
            self._tasks = [
                asyncio.create_task(self._position_sync_loop()),
                asyncio.create_task(self._order_sync_loop()),
                asyncio.create_task(self._event_handler_loop())
            ]
            
            # Update session status
            self.current_session.status = TradingSessionStatus.RUNNING
            
            # Publish session started event
            if hasattr(self.event_bus, 'publish_string'):
                await self.event_bus.publish_string(
                    "trading.session.started",
                    {
                        "session_id": str(self.current_session.id),
                        "portfolio_id": str(portfolio_id),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            else:
                await self.event_bus.publish(
                    "trading.session.started",
                    {
                        "session_id": str(self.current_session.id),
                        "portfolio_id": str(portfolio_id),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            
            logger.info(f"Trading session {self.current_session.id} started successfully")
            
        except Exception as e:
            self.current_session.status = TradingSessionStatus.ERROR
            self.current_session.error_message = str(e)
            logger.error(f"Failed to start trading session: {e}")
            raise
        
        return self.current_session
    
    async def emergency_stop(self, reason: str, close_positions: bool = True) -> None:
        """
        Emergency stop - immediately halt all trading activity
        
        Args:
            reason: Reason for emergency stop
            close_positions: Whether to close all open positions
        """
        if not self.current_session:
            logger.warning("No active session for emergency stop")
            return
        
        logger.critical(f"EMERGENCY STOP INITIATED: {reason}")
        
        # Set status to LOCKED immediately
        self.current_session.status = TradingSessionStatus.LOCKED
        self.current_session.error_message = f"EMERGENCY STOP: {reason}"
        self._running = False
        
        try:
            # 1. Cancel all open orders immediately
            logger.info("Cancelling all open orders...")
            cancel_tasks = []
            for order_id, order in list(self.active_orders.items()):
                if order.status == OrderStatus.PENDING:
                    cancel_tasks.append(self._emergency_cancel_order(order_id, order))
            
            if cancel_tasks:
                results = await asyncio.gather(*cancel_tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to cancel order: {result}")
            
            # 2. Close all positions if requested
            if close_positions:
                logger.info("Closing all open positions...")
                positions = await self.execution_port.positions()
                close_tasks = []
                
                for pos in positions:
                    close_tasks.append(self._emergency_close_position(pos))
                
                if close_tasks:
                    results = await asyncio.gather(*close_tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            logger.error(f"Failed to close position: {result}")
            
            # 3. Cancel background tasks
            for task in self._tasks:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
            # 4. Persist session state
            self.current_session.stopped_at = datetime.utcnow()
            # In a real implementation, save to database here
            
            # 5. Publish CRITICAL event
            event_data = {
                "session_id": str(self.current_session.id),
                "reason": reason,
                "positions_closed": close_positions,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "CRITICAL"
            }
            
            if hasattr(self.event_bus, 'publish_string'):
                await self.event_bus.publish_string("trading.emergency_stop", event_data)
            else:
                await self.event_bus.publish("trading.emergency_stop", event_data)
            
            logger.critical(f"Emergency stop completed. Session {self.current_session.id} is LOCKED")
            
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            # Even if there's an error, keep the session locked
            self.current_session.status = TradingSessionStatus.LOCKED
    
    async def _emergency_cancel_order(self, order_id: UUID, order: Order) -> bool:
        """Emergency cancel a single order"""
        try:
            if order.broker_order_id:
                success = await self.execution_port.cancel(order.broker_order_id)
                if success:
                    order.cancel(reason="EMERGENCY STOP", cancelled_by=None)
                    self.order_repository.save(order)
                    del self.active_orders[order_id]
                return success
        except Exception as e:
            logger.error(f"Emergency cancel failed for {order_id}: {e}")
            return False
        return False
    
    async def _emergency_close_position(self, position_data: dict) -> bool:
        """Emergency close a position"""
        try:
            symbol = position_data['symbol']
            quantity = position_data['quantity']
            side = position_data['side']
            
            # Create opposite order to close position
            close_side = "sell" if side == "buy" else "buy"
            
            close_order = {
                "symbol": symbol,
                "side": close_side,
                "quantity": quantity,
                "order_type": "market"
            }
            
            # Submit market order to close
            order_id = await self.execution_port.submit(close_order)
            logger.info(f"Emergency close order placed: {order_id} for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Emergency close failed for position: {e}")
            return False
    
    async def unlock_session(self) -> bool:
        """
        Manually unlock a session after emergency stop
        
        Returns:
            True if unlocked successfully
        """
        if not self.current_session:
            return False
        
        if self.current_session.status != TradingSessionStatus.LOCKED:
            logger.warning(f"Session is not locked (status: {self.current_session.status.value})")
            return False
        
        # Change status back to STOPPED
        self.current_session.status = TradingSessionStatus.STOPPED
        self.current_session.error_message = None
        
        logger.info(f"Session {self.current_session.id} unlocked")
        
        # Publish unlock event
        if hasattr(self.event_bus, 'publish_string'):
            await self.event_bus.publish_string(
                "trading.session.unlocked",
                {
                    "session_id": str(self.current_session.id),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        return True
    
    async def stop_session(self, reason: str = "User requested") -> None:
        """
        Stop the current trading session
        
        Args:
            reason: Reason for stopping
        """
        if not self.current_session:
            logger.warning("No active session to stop")
            return
        
        logger.info(f"Stopping trading session {self.current_session.id}: {reason}")
        
        self.current_session.status = TradingSessionStatus.STOPPING
        self._running = False
        
        # Cancel all pending orders
        for order_id, order in list(self.active_orders.items()):
            if order.status == OrderStatus.PENDING:
                try:
                    await self.cancel_order(order_id)
                except Exception as e:
                    logger.error(f"Failed to cancel order {order_id}: {e}")
        
        # Wait for background tasks to complete
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Update session
        self.current_session.status = TradingSessionStatus.STOPPED
        self.current_session.stopped_at = datetime.utcnow()
        
        # Publish session stopped event
        if hasattr(self.event_bus, 'publish_string'):
            await self.event_bus.publish_string(
                "trading.session.stopped",
                {
                    "session_id": str(self.current_session.id),
                    "reason": reason,
                    "total_trades": self.current_session.total_trades,
                    "total_pnl": str(self.current_session.total_pnl),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            await self.event_bus.publish(
                "trading.session.stopped",
                {
                    "session_id": str(self.current_session.id),
                    "reason": reason,
                    "total_trades": self.current_session.total_trades,
                    "total_pnl": str(self.current_session.total_pnl),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        logger.info(f"Trading session {self.current_session.id} stopped")
    
    async def place_order(self, order_request: OrderRequest) -> OrderResponse:
        """
        Place an order through the execution port with risk validation
        
        Args:
            order_request: Order request DTO
            
        Returns:
            Order response DTO
            
        Raises:
            ValueError: If no active session or risk validation fails
        """
        if not self.current_session:
            raise ValueError("No active trading session")
        
        if self.current_session.status == TradingSessionStatus.LOCKED:
            raise ValueError("Trading is locked due to emergency stop. Manual unlock required.")
        
        if self.current_session.status != TradingSessionStatus.RUNNING:
            raise ValueError(f"Trading session is not running (status: {self.current_session.status.value})")
        
        # Get current portfolio state for risk validation
        portfolio_state = await self._get_portfolio_state_for_risk()
        
        # Validate trade through risk port
        risk_action, reason, adjustments = await self.risk_port.validate_trade(
            order=order_request.model_dump(),
            portfolio_state=portfolio_state
        )
        
        # Handle risk validation result
        if risk_action == RiskAction.BLOCK:
            # Log warning and publish rejection event
            logger.warning(f"Order blocked by risk management: {reason}")
            
            if hasattr(self.event_bus, 'publish_string'):
                await self.event_bus.publish_string(
                    "risk.signal_rejected",
                    {
                        "symbol": order_request.symbol,
                        "side": order_request.side.value,
                        "quantity": str(order_request.quantity),
                        "reason": reason,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            
            # Raise exception with reason (will be caught by API and return 409)
            raise ValueError(f"Risk validation failed: {reason}")
        
        elif risk_action == RiskAction.ADJUST and adjustments:
            # Apply risk adjustments
            logger.info(f"Applying risk adjustments: {adjustments}")
            
            if "quantity" in adjustments:
                order_request.quantity = Decimal(str(adjustments["quantity"]))
            if "price" in adjustments:
                order_request.price = Decimal(str(adjustments["price"]))
            
            # Add adjustment info to metadata
            if not order_request.metadata:
                order_request.metadata = {}
            order_request.metadata["risk_adjusted"] = True
            order_request.metadata["adjustments"] = adjustments
            order_request.metadata["adjustment_reason"] = reason
        
        # Create domain order with potentially adjusted values
        order = Order.create(
            portfolio_id=self.current_session.portfolio_id,
            symbol=order_request.symbol,
            quantity=int(order_request.quantity * 1000),  # Convert to integer units
            order_type=order_request.order_type.value,
            price=float(order_request.price) if order_request.price else None
        )
        
        # Save order
        self.order_repository.save(order)
        self.active_orders[order.id] = order
        
        try:
            # Submit through execution port
            broker_order_id = await self.execution_port.submit(order_request.model_dump())
            
            # Update order with broker ID
            order.set_broker_order_id(broker_order_id)
            self.order_repository.save(order)
            
            # Update metrics
            self.metrics["orders_placed"] += 1
            
            # Publish order placed event
            if hasattr(self.event_bus, 'publish_string'):
                await self.event_bus.publish_string(
                    "trading.order.placed",
                    {
                        "order_id": str(order.id),
                        "broker_order_id": broker_order_id,
                        "symbol": order_request.symbol,
                        "side": order_request.side.value,
                        "quantity": str(order_request.quantity),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            else:
                await self.event_bus.publish(
                    "trading.order.placed",
                    {
                        "order_id": str(order.id),
                        "broker_order_id": broker_order_id,
                        "symbol": order_request.symbol,
                        "side": order_request.side.value,
                        "quantity": str(order_request.quantity),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            
            return OrderResponse(
                order_id=broker_order_id,
                client_order_id=str(order.id),
                symbol=order_request.symbol,
                side=order_request.side,
                order_type=order_request.order_type,
                status="pending",  # Use string value for OrderStatus
                quantity=order_request.quantity,
                filled_quantity=Decimal("0"),
                remaining_quantity=order_request.quantity,
                price=order_request.price,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
        except Exception as e:
            # Cancel order on error
            try:
                order.cancel(reason=str(e))
                self.order_repository.save(order)
            except Exception:
                pass  # Order may not be in cancellable state
            
            # Update metrics
            self.metrics["orders_rejected"] += 1
            
            logger.error(f"Failed to place order: {e}")
            raise
    
    async def cancel_order(self, order_id: UUID) -> bool:
        """
        Cancel an order through the execution port
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        order = self.active_orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        if not order.broker_order_id:
            raise ValueError(f"Order {order_id} has no broker ID")
        
        try:
            # Cancel through execution port
            success = await self.execution_port.cancel(order.broker_order_id)
            
            if success:
                # Update order status
                order.cancel(reason="User requested", cancelled_by=None)
                self.order_repository.save(order)
                
                # Remove from active orders
                del self.active_orders[order_id]
                
                # Update metrics
                self.metrics["orders_cancelled"] += 1
                
                # Publish order cancelled event
                if hasattr(self.event_bus, 'publish_string'):
                    await self.event_bus.publish_string(
                        "trading.order.cancelled",
                        {
                            "order_id": str(order_id),
                            "broker_order_id": order.broker_order_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
                else:
                    await self.event_bus.publish(
                        "trading.order.cancelled",
                        {
                            "order_id": str(order_id),
                            "broker_order_id": order.broker_order_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise
    
    async def get_positions(self) -> List[PositionDTO]:
        """
        Get current positions from execution port
        
        Returns:
            List of position DTOs
        """
        positions_data = await self.execution_port.positions()
        
        positions = []
        for pos_data in positions_data:
            positions.append(PositionDTO(
                symbol=pos_data['symbol'],
                side=pos_data['side'],
                quantity=pos_data['quantity'],
                entry_price=pos_data['entry_price'],
                current_price=pos_data['current_price'],
                unrealized_pnl=pos_data.get('unrealized_pnl', Decimal("0")),
                realized_pnl=pos_data.get('realized_pnl', Decimal("0")),
                margin_used=pos_data.get('margin_used'),
                leverage=pos_data.get('leverage'),
                opened_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ))
        
        return positions
    
    async def get_portfolio_state(self) -> PortfolioState:
        """
        Get current portfolio state
        
        Returns:
            Portfolio state DTO
        """
        if not self.current_session:
            raise ValueError("No active trading session")
        
        # Get portfolio
        portfolio = self.portfolio_repository.get(self.current_session.portfolio_id)
        if not portfolio:
            raise ValueError("Portfolio not found")
        
        # Get positions
        positions = await self.get_positions()
        
        # Get account balance from execution port
        balance_info = await self.execution_port.get_account_balance()
        
        # Calculate totals
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        total_realized_pnl = self.current_session.total_pnl
        
        return PortfolioState(
            account_id=str(self.current_session.portfolio_id),
            balance=balance_info.get('available', Decimal("0")),
            equity=balance_info.get('total', Decimal("0")),
            margin_used=balance_info.get('locked', Decimal("0")),
            margin_available=balance_info.get('available', Decimal("0")),
            positions=positions,
            total_unrealized_pnl=total_unrealized_pnl,
            total_realized_pnl=total_realized_pnl,
            leverage=Decimal("1"),  # Calculate based on positions
            timestamp=datetime.utcnow()
        )
    
    async def _position_sync_loop(self):
        """Background task to sync positions"""
        while self._running:
            try:
                # Get positions from broker
                positions = await self.execution_port.positions()
                
                # Update local cache
                for pos_data in positions:
                    symbol = pos_data['symbol']
                    
                    # Create or update position entity
                    if symbol not in self.active_positions:
                        position = Position(
                            id=uuid4(),
                            portfolio_id=self.current_session.portfolio_id,
                            symbol=symbol,
                            quantity=pos_data['quantity'],
                            entry_price=pos_data['entry_price'],
                            current_price=pos_data['current_price']
                        )
                        self.active_positions[symbol] = position
                    else:
                        position = self.active_positions[symbol]
                        position.current_price = pos_data['current_price']
                        position.unrealized_pnl = pos_data.get('unrealized_pnl', Decimal("0"))
                    
                    # Save to repository
                    if self.position_repository:
                        self.position_repository.save(position)
                
                # Remove closed positions
                open_symbols = {p['symbol'] for p in positions}
                for symbol in list(self.active_positions.keys()):
                    if symbol not in open_symbols:
                        del self.active_positions[symbol]
                
                await asyncio.sleep(5)  # Sync every 5 seconds
                
            except Exception as e:
                logger.error(f"Position sync error: {e}")
                await asyncio.sleep(10)
    
    async def _order_sync_loop(self):
        """Background task to sync order status"""
        while self._running:
            try:
                # Get open orders from broker
                broker_orders = await self.execution_port.orders(status="pending")
                
                # Update local orders
                broker_order_ids = {o['order_id'] for o in broker_orders}
                
                for order_id, order in list(self.active_orders.items()):
                    if order.broker_order_id not in broker_order_ids:
                        # Order is no longer open - check if filled or cancelled
                        broker_order = await self.execution_port.get_order(order.broker_order_id)
                        
                        if broker_order:
                            if broker_order['status'] == 'filled':
                                order.fill(
                                    filled_price=broker_order.get('average_fill_price'),
                                    filled_at=broker_order.get('updated_at')
                                )
                                self.metrics["orders_filled"] += 1
                                self.current_session.total_trades += 1
                            elif broker_order['status'] == 'cancelled':
                                order.cancel("Broker cancelled", None)
                                self.metrics["orders_cancelled"] += 1
                            
                            self.order_repository.save(order)
                            del self.active_orders[order_id]
                
                await asyncio.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Order sync error: {e}")
                await asyncio.sleep(10)
    
    async def _event_handler_loop(self):
        """Background task to handle domain events"""
        while self._running:
            try:
                # This would subscribe to relevant events
                # For now, just sleep
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Event handler error: {e}")
                await asyncio.sleep(5)
    
    def get_session_status(self) -> Optional[Dict[str, any]]:
        """Get current session status"""
        if not self.current_session:
            return None
        
        return {
            "session_id": str(self.current_session.id),
            "status": self.current_session.status.value,
            "started_at": self.current_session.started_at.isoformat() if self.current_session.started_at else None,
            "total_trades": self.current_session.total_trades,
            "total_pnl": str(self.current_session.total_pnl),
            "winning_trades": self.current_session.winning_trades,
            "losing_trades": self.current_session.losing_trades,
            "max_drawdown": str(self.current_session.max_drawdown),
            "metrics": self.metrics
        }
    
    async def _get_portfolio_state_for_risk(self) -> Dict[str, Any]:
        """Get portfolio state for risk validation"""
        # Get account balance
        balance_info = await self.execution_port.get_account_balance()
        
        # Get positions
        positions = await self.execution_port.positions()
        
        # Calculate total exposure
        total_exposure = Decimal("0")
        for pos in positions:
            total_exposure += Decimal(str(pos['quantity'])) * Decimal(str(pos['current_price']))
        
        return {
            "positions": positions,
            "balance": balance_info.get('available', Decimal("0")),
            "equity": balance_info.get('total', Decimal("0")),
            "margin_used": balance_info.get('locked', Decimal("0")),
            "exposure": total_exposure,
            "daily_pnl": self.current_session.total_pnl if self.current_session else Decimal("0")
        }