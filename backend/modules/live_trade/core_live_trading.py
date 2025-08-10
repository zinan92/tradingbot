"""
Core Live Trading Engine

Core domain logic for live trading operations following hexagonal architecture.
Manages trading sessions, order execution, and portfolio state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Protocol
from uuid import UUID, uuid4
import logging

logger = logging.getLogger(__name__)


class TradingSessionStatus(Enum):
    """Trading session status"""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class OrderSide(Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"


@dataclass
class TradingSignal:
    """Trading signal from strategy"""
    signal_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Optional[Decimal] = None
    order_type: OrderType = OrderType.MARKET
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)


@dataclass
class Order:
    """Trading order"""
    order_id: str
    signal_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal]
    status: OrderStatus
    created_at: datetime
    filled_quantity: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    broker_order_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class Position:
    """Trading position"""
    symbol: str
    side: OrderSide
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal('0')
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Portfolio:
    """Trading portfolio"""
    portfolio_id: str
    total_balance: Decimal
    available_balance: Decimal
    positions: Dict[str, Position] = field(default_factory=dict)
    orders: Dict[str, Order] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class BrokerPort(Protocol):
    """Port interface for broker operations"""
    
    async def place_order(self, order: Order) -> str:
        """Place an order and return broker order ID"""
        pass
    
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """Get order status from broker"""
        pass
    
    async def get_account_balance(self) -> Decimal:
        """Get account balance"""
        pass
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for symbol"""
        pass


class PortfolioPort(Protocol):
    """Port interface for portfolio operations"""
    
    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Get portfolio by ID"""
        pass
    
    async def update_portfolio(self, portfolio: Portfolio) -> None:
        """Update portfolio"""
        pass
    
    async def add_order(self, portfolio_id: str, order: Order) -> None:
        """Add order to portfolio"""
        pass
    
    async def update_order(self, order: Order) -> None:
        """Update order status"""
        pass


class RiskPort(Protocol):
    """Port interface for risk management"""
    
    async def validate_signal(self, signal: TradingSignal, portfolio: Portfolio) -> bool:
        """Validate trading signal against risk rules"""
        pass
    
    async def calculate_position_size(self, signal: TradingSignal, portfolio: Portfolio) -> Decimal:
        """Calculate appropriate position size"""
        pass


class EventPort(Protocol):
    """Port interface for event handling"""
    
    async def publish_event(self, event_type: str, event_data: Dict) -> None:
        """Publish trading event"""
        pass


@dataclass
class TradingSession:
    """Trading session state"""
    session_id: str
    strategy_id: str
    portfolio_id: str
    status: TradingSessionStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    error_message: Optional[str] = None
    config: Dict = field(default_factory=dict)


class LiveTradingEngine:
    """
    Core live trading engine that coordinates trading operations
    """
    
    def __init__(self, 
                 broker_port: BrokerPort,
                 portfolio_port: PortfolioPort,
                 risk_port: RiskPort,
                 event_port: EventPort):
        self.broker_port = broker_port
        self.portfolio_port = portfolio_port
        self.risk_port = risk_port
        self.event_port = event_port
        self.sessions: Dict[str, TradingSession] = {}
        self._running = False
    
    async def create_session(self, strategy_id: str, portfolio_id: str, config: Dict = None) -> str:
        """Create a new trading session"""
        session_id = str(uuid4())
        
        session = TradingSession(
            session_id=session_id,
            strategy_id=strategy_id,
            portfolio_id=portfolio_id,
            status=TradingSessionStatus.STOPPED,
            created_at=datetime.utcnow(),
            config=config or {}
        )
        
        self.sessions[session_id] = session
        
        await self.event_port.publish_event("session_created", {
            "session_id": session_id,
            "strategy_id": strategy_id,
            "portfolio_id": portfolio_id
        })
        
        logger.info(f"Created trading session {session_id} for strategy {strategy_id}")
        return session_id
    
    async def start_session(self, session_id: str) -> bool:
        """Start a trading session"""
        session = self.sessions.get(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False
        
        try:
            session.status = TradingSessionStatus.STARTING
            
            # Validate portfolio exists
            portfolio = await self.portfolio_port.get_portfolio(session.portfolio_id)
            if not portfolio:
                raise ValueError(f"Portfolio {session.portfolio_id} not found")
            
            # Check broker connection
            balance = await self.broker_port.get_account_balance()
            logger.info(f"Broker account balance: {balance}")
            
            session.status = TradingSessionStatus.RUNNING
            session.started_at = datetime.utcnow()
            
            await self.event_port.publish_event("session_started", {
                "session_id": session_id,
                "strategy_id": session.strategy_id
            })
            
            logger.info(f"Started trading session {session_id}")
            return True
            
        except Exception as e:
            session.status = TradingSessionStatus.ERROR
            session.error_message = str(e)
            logger.error(f"Failed to start session {session_id}: {str(e)}")
            return False
    
    async def stop_session(self, session_id: str) -> bool:
        """Stop a trading session"""
        session = self.sessions.get(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False
        
        try:
            session.status = TradingSessionStatus.STOPPING
            
            # Cancel all pending orders for this session
            portfolio = await self.portfolio_port.get_portfolio(session.portfolio_id)
            if portfolio:
                for order in portfolio.orders.values():
                    if order.status == OrderStatus.PENDING and order.broker_order_id:
                        await self.broker_port.cancel_order(order.broker_order_id)
            
            session.status = TradingSessionStatus.STOPPED
            session.stopped_at = datetime.utcnow()
            
            await self.event_port.publish_event("session_stopped", {
                "session_id": session_id,
                "strategy_id": session.strategy_id
            })
            
            logger.info(f"Stopped trading session {session_id}")
            return True
            
        except Exception as e:
            session.status = TradingSessionStatus.ERROR
            session.error_message = str(e)
            logger.error(f"Failed to stop session {session_id}: {str(e)}")
            return False
    
    async def process_signal(self, session_id: str, signal: TradingSignal) -> str:
        """Process a trading signal"""
        session = self.sessions.get(session_id)
        if not session or session.status != TradingSessionStatus.RUNNING:
            raise ValueError(f"Session {session_id} not running")
        
        # Get portfolio
        portfolio = await self.portfolio_port.get_portfolio(session.portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {session.portfolio_id} not found")
        
        # Validate signal
        is_valid = await self.risk_port.validate_signal(signal, portfolio)
        if not is_valid:
            logger.warning(f"Signal {signal.signal_id} failed risk validation")
            return None
        
        # Calculate position size
        position_size = await self.risk_port.calculate_position_size(signal, portfolio)
        
        # Create order
        order = Order(
            order_id=str(uuid4()),
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=signal.side,
            order_type=signal.order_type,
            quantity=position_size,
            price=signal.price,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        # Add to portfolio
        await self.portfolio_port.add_order(session.portfolio_id, order)
        
        # Submit to broker
        try:
            broker_order_id = await self.broker_port.place_order(order)
            order.broker_order_id = broker_order_id
            order.status = OrderStatus.SUBMITTED
            
            await self.portfolio_port.update_order(order)
            
            await self.event_port.publish_event("order_submitted", {
                "order_id": order.order_id,
                "session_id": session_id,
                "signal_id": signal.signal_id,
                "broker_order_id": broker_order_id
            })
            
            logger.info(f"Submitted order {order.order_id} to broker: {broker_order_id}")
            return order.order_id
            
        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.error_message = str(e)
            await self.portfolio_port.update_order(order)
            logger.error(f"Failed to submit order {order.order_id}: {str(e)}")
            raise
    
    async def get_session_status(self, session_id: str) -> Optional[TradingSession]:
        """Get trading session status"""
        return self.sessions.get(session_id)
    
    async def list_sessions(self) -> List[TradingSession]:
        """List all trading sessions"""
        return list(self.sessions.values())
    
    async def emergency_stop_all(self) -> None:
        """Emergency stop all trading sessions"""
        logger.warning("Emergency stop initiated for all sessions")
        
        for session_id in list(self.sessions.keys()):
            session = self.sessions[session_id]
            if session.status == TradingSessionStatus.RUNNING:
                await self.stop_session(session_id)
        
        await self.event_port.publish_event("emergency_stop", {
            "timestamp": datetime.utcnow().isoformat(),
            "sessions_stopped": len(self.sessions)
        })
        
        logger.warning("Emergency stop completed")