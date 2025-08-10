"""
Live Trading Service

Application service layer for live trading operations.
Orchestrates between core domain logic and external adapters.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import uuid4

from backend.modules.live_trade.core_live_trading import (
    LiveTradingEngine,
    TradingSignal,
    TradingSession,
    TradingSessionStatus,
    OrderSide,
    OrderType
)

logger = logging.getLogger(__name__)


@dataclass
class CreateSessionRequest:
    """Request to create trading session"""
    strategy_name: str
    symbol: str
    initial_balance: Decimal
    risk_config: Dict = None
    strategy_params: Dict = None


@dataclass
class SignalRequest:
    """Request to process trading signal"""
    session_id: str
    side: str  # "BUY" or "SELL"
    quantity: Optional[Decimal] = None
    price: Optional[Decimal] = None
    order_type: str = "MARKET"
    metadata: Dict = None


class LiveTradingService:
    """
    Service layer for live trading operations.
    Provides high-level API for trading session management.
    """
    
    def __init__(self, trading_engine: LiveTradingEngine):
        self.trading_engine = trading_engine
        self._background_tasks = set()
    
    async def create_trading_session(self, request: CreateSessionRequest) -> str:
        """
        Create a new trading session for a strategy.
        
        Args:
            request: Session creation request
            
        Returns:
            Session ID
        """
        try:
            # Create portfolio ID
            portfolio_id = f"portfolio_{uuid4().hex[:8]}"
            
            # Session configuration
            config = {
                "strategy_name": request.strategy_name,
                "symbol": request.symbol,
                "initial_balance": float(request.initial_balance),
                "risk_config": request.risk_config or {},
                "strategy_params": request.strategy_params or {}
            }
            
            # Create session
            session_id = await self.trading_engine.create_session(
                strategy_id=f"strategy_{request.strategy_name}",
                portfolio_id=portfolio_id,
                config=config
            )
            
            logger.info(f"Created trading session {session_id} for {request.strategy_name}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create trading session: {str(e)}")
            raise
    
    async def start_session(self, session_id: str) -> bool:
        """
        Start a trading session.
        
        Args:
            session_id: Session to start
            
        Returns:
            True if started successfully
        """
        try:
            success = await self.trading_engine.start_session(session_id)
            
            if success:
                # Start background monitoring task
                task = asyncio.create_task(self._monitor_session(session_id))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {str(e)}")
            return False
    
    async def stop_session(self, session_id: str) -> bool:
        """
        Stop a trading session.
        
        Args:
            session_id: Session to stop
            
        Returns:
            True if stopped successfully
        """
        try:
            return await self.trading_engine.stop_session(session_id)
            
        except Exception as e:
            logger.error(f"Failed to stop session {session_id}: {str(e)}")
            return False
    
    async def submit_signal(self, request: SignalRequest) -> Optional[str]:
        """
        Submit a trading signal for processing.
        
        Args:
            request: Trading signal request
            
        Returns:
            Order ID if successful
        """
        try:
            # Convert request to trading signal
            signal = TradingSignal(
                signal_id=str(uuid4()),
                strategy_id=f"strategy_{request.session_id}",  # Simplified
                symbol="BTCUSDT",  # TODO: Get from session config
                side=OrderSide.BUY if request.side.upper() == "BUY" else OrderSide.SELL,
                quantity=request.quantity or Decimal('0.01'),  # Default quantity
                price=request.price,
                order_type=OrderType.MARKET if request.order_type.upper() == "MARKET" else OrderType.LIMIT,
                timestamp=datetime.utcnow(),
                metadata=request.metadata or {}
            )
            
            order_id = await self.trading_engine.process_signal(request.session_id, signal)
            logger.info(f"Processed signal {signal.signal_id}, order: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"Failed to process signal: {str(e)}")
            raise
    
    async def get_session_status(self, session_id: str) -> Optional[Dict]:
        """
        Get trading session status.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session status information
        """
        try:
            session = await self.trading_engine.get_session_status(session_id)
            
            if not session:
                return None
            
            return {
                "session_id": session.session_id,
                "strategy_id": session.strategy_id,
                "portfolio_id": session.portfolio_id,
                "status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "stopped_at": session.stopped_at.isoformat() if session.stopped_at else None,
                "error_message": session.error_message,
                "config": session.config
            }
            
        except Exception as e:
            logger.error(f"Failed to get session status: {str(e)}")
            return None
    
    async def list_sessions(self) -> List[Dict]:
        """
        List all trading sessions.
        
        Returns:
            List of session information
        """
        try:
            sessions = await self.trading_engine.list_sessions()
            
            return [
                {
                    "session_id": session.session_id,
                    "strategy_id": session.strategy_id,
                    "status": session.status.value,
                    "created_at": session.created_at.isoformat(),
                    "started_at": session.started_at.isoformat() if session.started_at else None,
                    "config": session.config
                }
                for session in sessions
            ]
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {str(e)}")
            return []
    
    async def emergency_stop(self) -> bool:
        """
        Emergency stop all trading sessions.
        
        Returns:
            True if emergency stop successful
        """
        try:
            await self.trading_engine.emergency_stop_all()
            logger.warning("Emergency stop completed")
            return True
            
        except Exception as e:
            logger.error(f"Emergency stop failed: {str(e)}")
            return False
    
    async def get_portfolio_status(self, session_id: str) -> Optional[Dict]:
        """
        Get portfolio status for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Portfolio information
        """
        try:
            session = await self.trading_engine.get_session_status(session_id)
            if not session:
                return None
            
            # TODO: Implement portfolio retrieval through ports
            # For now, return mock data
            return {
                "portfolio_id": session.portfolio_id,
                "total_balance": 10000.0,
                "available_balance": 9500.0,
                "unrealized_pnl": 125.50,
                "realized_pnl": -45.20,
                "open_positions": 2,
                "pending_orders": 1,
                "updated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get portfolio status: {str(e)}")
            return None
    
    async def _monitor_session(self, session_id: str):
        """
        Background task to monitor trading session.
        
        Args:
            session_id: Session to monitor
        """
        logger.info(f"Started monitoring session {session_id}")
        
        try:
            while True:
                session = await self.trading_engine.get_session_status(session_id)
                
                if not session or session.status in [
                    TradingSessionStatus.STOPPED,
                    TradingSessionStatus.ERROR
                ]:
                    break
                
                # Monitor session health
                # TODO: Add health checks, risk monitoring, etc.
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except asyncio.CancelledError:
            logger.info(f"Session monitoring cancelled for {session_id}")
        except Exception as e:
            logger.error(f"Session monitoring error for {session_id}: {str(e)}")
        
        logger.info(f"Stopped monitoring session {session_id}")
    
    async def cleanup(self):
        """Clean up background tasks"""
        logger.info("Cleaning up live trading service")
        
        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        logger.info("Live trading service cleanup completed")