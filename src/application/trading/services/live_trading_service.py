"""
Live Trading Service

Manages live trading sessions, coordinates between signals and execution,
and maintains trading state.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

from src.config.trading_config import TradingConfig, get_config
from src.domain.trading.aggregates.portfolio import Portfolio
from src.domain.trading.entities.position import Position
from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.strategy.events import SignalGenerated
from src.infrastructure.brokers.binance_futures_broker import BinanceFuturesBroker
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)


class TradingSessionStatus(Enum):
    """Trading session status"""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


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
    
    def update_stats(self, pnl: Decimal) -> None:
        """Update session statistics"""
        self.total_trades += 1
        self.total_pnl += pnl
        
        if pnl > 0:
            self.winning_trades += 1
        elif pnl < 0:
            self.losing_trades += 1
        
        # Track drawdown
        if self.total_pnl < self.max_drawdown:
            self.max_drawdown = self.total_pnl
    
    def get_win_rate(self) -> Decimal:
        """Calculate win rate"""
        if self.total_trades == 0:
            return Decimal("0")
        return Decimal(str(self.winning_trades)) / Decimal(str(self.total_trades))


class LiveTradingService:
    """
    Main service for managing live trading operations.
    
    Responsibilities:
    - Session lifecycle management
    - Signal processing and order generation
    - Position and risk monitoring
    - Error handling and recovery
    """
    
    def __init__(
        self,
        portfolio_repository,
        order_repository,
        position_repository,
        event_bus: Optional[InMemoryEventBus] = None,
        config: Optional[TradingConfig] = None
    ):
        """
        Initialize live trading service.
        
        Args:
            portfolio_repository: Repository for portfolio operations
            order_repository: Repository for order operations
            position_repository: Repository for position operations
            event_bus: Event bus for publishing/subscribing to events
            config: Trading configuration
        """
        self.portfolio_repo = portfolio_repository
        self.order_repo = order_repository
        self.position_repo = position_repository
        self.event_bus = event_bus or InMemoryEventBus()
        self.config = config or get_config()
        
        # Session management
        self.current_session: Optional[TradingSession] = None
        self.broker: Optional[BinanceFuturesBroker] = None
        
        # Tracking
        self.active_orders: Dict[UUID, Order] = {}
        self.active_positions: Dict[str, Position] = {}
        self.monitored_symbols: Set[str] = set()
        
        # Background tasks
        self._monitor_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # Subscribe to events
        self._setup_event_handlers()
        
        logger.info("LiveTradingService initialized")
    
    def _setup_event_handlers(self) -> None:
        """Set up event subscriptions"""
        # Subscribe to signal events
        self.event_bus.subscribe(SignalGenerated, self._handle_signal)
        
        # Subscribe to order events
        from src.domain.trading.events.order_events import OrderFilled, OrderRejected
        self.event_bus.subscribe(OrderFilled, self._handle_order_filled)
        self.event_bus.subscribe(OrderRejected, self._handle_order_rejected)
    
    async def start_session(self, portfolio_id: UUID) -> TradingSession:
        """
        Start a new trading session.
        
        Args:
            portfolio_id: Portfolio to trade with
            
        Returns:
            New trading session
            
        Raises:
            RuntimeError: If session already active or config invalid
        """
        if self.current_session and self.current_session.status == TradingSessionStatus.RUNNING:
            raise RuntimeError("Trading session already active")
        
        if not self.config.enabled:
            raise RuntimeError("Trading is disabled in configuration")
        
        if not self.config.validate():
            raise RuntimeError("Invalid trading configuration")
        
        logger.info(f"Starting trading session for portfolio {portfolio_id}")
        
        # Create new session
        self.current_session = TradingSession(
            id=uuid4(),
            portfolio_id=portfolio_id,
            status=TradingSessionStatus.STARTING,
            started_at=datetime.utcnow()
        )
        
        try:
            # Initialize broker
            await self._initialize_broker()
            
            # Load portfolio
            portfolio = await self.portfolio_repo.find_by_id(portfolio_id)
            if not portfolio:
                raise ValueError(f"Portfolio {portfolio_id} not found")
            
            # Load existing positions
            await self._load_positions(portfolio_id)
            
            # Start monitoring tasks
            self._monitor_task = asyncio.create_task(self._monitor_positions())
            self._heartbeat_task = asyncio.create_task(self._heartbeat())
            
            # Update session status
            self.current_session.status = TradingSessionStatus.RUNNING
            
            logger.info(f"Trading session {self.current_session.id} started successfully")
            
            # Publish session started event
            await self._publish_session_started()
            
            return self.current_session
            
        except Exception as e:
            logger.error(f"Failed to start trading session: {e}")
            self.current_session.status = TradingSessionStatus.ERROR
            self.current_session.error_message = str(e)
            raise
    
    async def stop_session(self, reason: str = "User requested") -> None:
        """
        Stop the current trading session.
        
        Args:
            reason: Reason for stopping
        """
        if not self.current_session:
            logger.warning("No active session to stop")
            return
        
        logger.info(f"Stopping trading session: {reason}")
        
        self.current_session.status = TradingSessionStatus.STOPPING
        
        try:
            # Cancel all pending orders
            await self._cancel_all_orders()
            
            # Close all positions if configured
            if self.config.risk.max_drawdown_percent > 0:
                await self._close_all_positions()
            
            # Stop monitoring tasks
            if self._monitor_task:
                self._monitor_task.cancel()
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            
            # Disconnect broker
            if self.broker:
                await self.broker.disconnect()
            
            # Update session
            self.current_session.status = TradingSessionStatus.STOPPED
            self.current_session.stopped_at = datetime.utcnow()
            
            # Publish session stopped event
            await self._publish_session_stopped(reason)
            
            logger.info(f"Trading session {self.current_session.id} stopped")
            
        except Exception as e:
            logger.error(f"Error stopping session: {e}")
            self.current_session.status = TradingSessionStatus.ERROR
            self.current_session.error_message = str(e)
    
    async def pause_session(self, reason: str = "User requested") -> None:
        """Pause trading without closing positions"""
        if not self.current_session or self.current_session.status != TradingSessionStatus.RUNNING:
            raise RuntimeError("No active session to pause")
        
        logger.info(f"Pausing trading session: {reason}")
        
        self.current_session.status = TradingSessionStatus.PAUSED
        
        # Cancel pending orders but keep positions
        await self._cancel_all_orders()
        
        # Publish pause event
        await self._publish_session_paused(reason)
    
    async def resume_session(self) -> None:
        """Resume paused trading session"""
        if not self.current_session or self.current_session.status != TradingSessionStatus.PAUSED:
            raise RuntimeError("No paused session to resume")
        
        logger.info("Resuming trading session")
        
        self.current_session.status = TradingSessionStatus.RUNNING
        
        # Reload positions in case they changed
        await self._load_positions(self.current_session.portfolio_id)
        
        # Publish resume event
        await self._publish_session_resumed()
    
    async def _initialize_broker(self) -> None:
        """Initialize broker connection"""
        self.broker = BinanceFuturesBroker(
            api_key=self.config.binance.api_key,
            api_secret=self.config.binance.api_secret,
            testnet=self.config.binance.testnet,
            event_bus=self.event_bus
        )
        
        await self.broker.connect()
        logger.info(f"Connected to Binance {'Testnet' if self.config.binance.testnet else 'Mainnet'}")
    
    async def _load_positions(self, portfolio_id: UUID) -> None:
        """Load existing positions from repository"""
        positions = await self.position_repo.find_open_positions(portfolio_id=portfolio_id)
        
        self.active_positions = {pos.symbol: pos for pos in positions}
        self.monitored_symbols = {pos.symbol for pos in positions}
        
        logger.info(f"Loaded {len(positions)} open positions")
    
    async def _handle_signal(self, event: SignalGenerated) -> None:
        """
        Handle signal generated by strategy.
        
        Args:
            event: SignalGenerated event
        """
        if not self.current_session or self.current_session.status != TradingSessionStatus.RUNNING:
            logger.debug("Ignoring signal - session not running")
            return
        
        if not self.config.signal.auto_execute:
            logger.info(f"Signal received but auto-execute disabled: {event.symbol} {event.signal_type}")
            return
        
        # Check signal thresholds
        if event.confidence < self.config.signal.confidence_threshold:
            logger.info(f"Signal confidence {event.confidence} below threshold {self.config.signal.confidence_threshold}")
            return
        
        if event.strength < self.config.signal.strength_threshold:
            logger.info(f"Signal strength {event.strength} below threshold {self.config.signal.strength_threshold}")
            return
        
        logger.info(f"Processing signal: {event.symbol} {event.signal_type} "
                   f"(strength: {event.strength}, confidence: {event.confidence})")
        
        try:
            # Generate order from signal
            order = await self._create_order_from_signal(event)
            
            if order:
                # Submit order to broker
                await self._submit_order(order)
                
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
    
    async def _create_order_from_signal(self, signal: SignalGenerated) -> Optional[Order]:
        """
        Create order from trading signal.
        
        Args:
            signal: Trading signal event
            
        Returns:
            Order object or None if order should not be placed
        """
        # Get signal mapping
        mapping = self.config.signal.signal_mappings.get(signal.signal_type)
        
        if not mapping:
            logger.warning(f"No mapping for signal type: {signal.signal_type}")
            return None
        
        if mapping.get("action") == "none":
            logger.debug(f"Signal type {signal.signal_type} mapped to no action")
            return None
        
        # Calculate position size
        portfolio = await self.portfolio_repo.find_by_id(self.current_session.portfolio_id)
        position_size = await self._calculate_position_size(
            portfolio=portfolio,
            signal=signal,
            size_multiplier=mapping.get("size_multiplier", 1.0)
        )
        
        if position_size <= 0:
            logger.info("Position size is 0, skipping order")
            return None
        
        # Create order
        order = Order.create(
            symbol=signal.symbol,
            quantity=position_size,
            order_type=mapping.get("order_type", "MARKET"),
            side="BUY" if "BUY" in signal.signal_type else "SELL",
            portfolio_id=self.current_session.portfolio_id,
            leverage=self.config.risk.max_leverage,
            position_side=mapping.get("position_side"),
            reduce_only=mapping.get("reduce_only", False)
        )
        
        return order
    
    async def _calculate_position_size(
        self,
        portfolio: Portfolio,
        signal: SignalGenerated,
        size_multiplier: float
    ) -> int:
        """
        Calculate position size based on portfolio and signal.
        
        Args:
            portfolio: Trading portfolio
            signal: Trading signal
            size_multiplier: Size adjustment from signal mapping
            
        Returns:
            Position size in units
        """
        # Get current price (would come from market data in production)
        current_price = Decimal(str(signal.parameters.get("current_price", 100)))
        
        # Base position value
        if self.config.position_sizing.use_kelly_criterion:
            # Kelly criterion sizing (simplified)
            win_prob = float(signal.confidence)
            win_loss_ratio = 2.0  # Assume 2:1 reward/risk
            kelly_fraction = (win_prob * win_loss_ratio - (1 - win_prob)) / win_loss_ratio
            kelly_fraction = min(kelly_fraction, float(self.config.position_sizing.kelly_fraction))
            position_value = portfolio.available_cash * Decimal(str(kelly_fraction))
        else:
            # Fixed percentage sizing
            position_value = portfolio.available_cash * (
                self.config.position_sizing.default_position_size_percent / 100
            )
        
        # Apply signal strength multiplier
        position_value *= Decimal(str(size_multiplier))
        position_value *= signal.strength
        
        # Apply maximum position size limit
        position_value = min(position_value, self.config.risk.max_position_size_usdt)
        
        # Calculate quantity
        quantity = int(position_value / current_price)
        
        return quantity
    
    async def _submit_order(self, order: Order) -> None:
        """
        Submit order to broker.
        
        Args:
            order: Order to submit
        """
        try:
            # Save order
            await self.order_repo.save(order)
            
            # Submit to broker
            broker_order_id = await self.broker.submit_order(order)
            order.set_broker_order_id(broker_order_id)
            
            # Track active order
            self.active_orders[order.id] = order
            
            # Update order repository
            await self.order_repo.save(order)
            
            logger.info(f"Order submitted: {order.id} -> {broker_order_id}")
            
        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            raise
    
    async def _handle_order_filled(self, event) -> None:
        """Handle order fill event"""
        if event.order_id in self.active_orders:
            order = self.active_orders.pop(event.order_id)
            
            # Update session stats
            if self.current_session:
                # This would need actual PnL calculation
                self.current_session.update_stats(Decimal("0"))
            
            logger.info(f"Order filled: {event.order_id}")
    
    async def _handle_order_rejected(self, event) -> None:
        """Handle order rejection event"""
        if event.order_id in self.active_orders:
            self.active_orders.pop(event.order_id)
            logger.warning(f"Order rejected: {event.order_id} - {event.reason}")
    
    async def _monitor_positions(self) -> None:
        """Monitor positions and risk metrics"""
        while True:
            try:
                if self.current_session and self.current_session.status == TradingSessionStatus.RUNNING:
                    # Check positions
                    for symbol, position in self.active_positions.items():
                        if position.is_near_liquidation():
                            logger.warning(f"Position near liquidation: {symbol}")
                            # Could auto-close or reduce position
                    
                    # Check daily loss limit
                    if abs(self.current_session.total_pnl) > self.config.risk.daily_loss_limit_usdt:
                        logger.error("Daily loss limit exceeded - stopping session")
                        await self.stop_session("Daily loss limit exceeded")
                        break
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in position monitor: {e}")
    
    async def _heartbeat(self) -> None:
        """Maintain connection heartbeat"""
        while True:
            try:
                await asyncio.sleep(self.config.websocket.heartbeat_interval)
                
                if self.broker:
                    # Ping broker to keep connection alive
                    pass
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def _cancel_all_orders(self) -> None:
        """Cancel all pending orders"""
        for order_id, order in list(self.active_orders.items()):
            try:
                if order.is_pending():
                    await self.broker.cancel_order(order.broker_order_id)
                    self.active_orders.pop(order_id)
                    logger.info(f"Cancelled order: {order_id}")
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")
    
    async def _close_all_positions(self) -> None:
        """Close all open positions"""
        for symbol, position in list(self.active_positions.items()):
            try:
                if position.is_open:
                    # Create market order to close
                    close_order = Order.create(
                        symbol=symbol,
                        quantity=position.quantity.value,
                        order_type="MARKET",
                        side="SELL" if position.side.value == "LONG" else "BUY",
                        portfolio_id=self.current_session.portfolio_id,
                        reduce_only=True
                    )
                    
                    await self._submit_order(close_order)
                    logger.info(f"Closing position: {symbol}")
                    
            except Exception as e:
                logger.error(f"Failed to close position {symbol}: {e}")
    
    async def _publish_session_started(self) -> None:
        """Publish session started event"""
        # Would publish a custom SessionStarted event
        pass
    
    async def _publish_session_stopped(self, reason: str) -> None:
        """Publish session stopped event"""
        # Would publish a custom SessionStopped event
        pass
    
    async def _publish_session_paused(self, reason: str) -> None:
        """Publish session paused event"""
        # Would publish a custom SessionPaused event
        pass
    
    async def _publish_session_resumed(self) -> None:
        """Publish session resumed event"""
        # Would publish a custom SessionResumed event
        pass
    
    def get_session_status(self) -> Optional[Dict]:
        """Get current session status"""
        if not self.current_session:
            return None
        
        return {
            "session_id": str(self.current_session.id),
            "status": self.current_session.status.value,
            "started_at": self.current_session.started_at.isoformat() if self.current_session.started_at else None,
            "total_trades": self.current_session.total_trades,
            "win_rate": float(self.current_session.get_win_rate()),
            "total_pnl": float(self.current_session.total_pnl),
            "active_orders": len(self.active_orders),
            "active_positions": len(self.active_positions)
        }