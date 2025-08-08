"""
State Recovery Service

Handles persistence and recovery of trading state across sessions,
crashes, and restarts.
"""
import json
import logging
import pickle
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from uuid import UUID

from src.application.trading.services.live_trading_service import TradingSession, TradingSessionStatus
from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.trading.entities.position import Position

logger = logging.getLogger(__name__)


@dataclass
class StateSnapshot:
    """
    Snapshot of trading state at a point in time.
    """
    timestamp: datetime
    session: Optional[TradingSession]
    active_orders: Dict[UUID, Dict[str, Any]]
    active_positions: Dict[str, Dict[str, Any]]
    monitored_symbols: Set[str]
    portfolio_id: Optional[UUID]
    risk_metrics: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "session": self._session_to_dict() if self.session else None,
            "active_orders": {str(k): v for k, v in self.active_orders.items()},
            "active_positions": self.active_positions,
            "monitored_symbols": list(self.monitored_symbols),
            "portfolio_id": str(self.portfolio_id) if self.portfolio_id else None,
            "risk_metrics": self.risk_metrics,
            "metadata": self.metadata
        }
    
    def _session_to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        if not self.session:
            return {}
        
        return {
            "id": str(self.session.id),
            "portfolio_id": str(self.session.portfolio_id),
            "status": self.session.status.value,
            "started_at": self.session.started_at.isoformat() if self.session.started_at else None,
            "stopped_at": self.session.stopped_at.isoformat() if self.session.stopped_at else None,
            "total_trades": self.session.total_trades,
            "winning_trades": self.session.winning_trades,
            "losing_trades": self.session.losing_trades,
            "total_pnl": str(self.session.total_pnl),
            "max_drawdown": str(self.session.max_drawdown),
            "error_message": self.session.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSnapshot":
        """Create snapshot from dictionary"""
        session = None
        if data.get("session"):
            session_data = data["session"]
            session = TradingSession(
                id=UUID(session_data["id"]),
                portfolio_id=UUID(session_data["portfolio_id"]),
                status=TradingSessionStatus[session_data["status"]],
                started_at=datetime.fromisoformat(session_data["started_at"]) if session_data.get("started_at") else None,
                stopped_at=datetime.fromisoformat(session_data["stopped_at"]) if session_data.get("stopped_at") else None,
                total_trades=session_data["total_trades"],
                winning_trades=session_data["winning_trades"],
                losing_trades=session_data["losing_trades"],
                total_pnl=Decimal(session_data["total_pnl"]),
                max_drawdown=Decimal(session_data["max_drawdown"]),
                error_message=session_data.get("error_message")
            )
        
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session=session,
            active_orders={UUID(k): v for k, v in data.get("active_orders", {}).items()},
            active_positions=data.get("active_positions", {}),
            monitored_symbols=set(data.get("monitored_symbols", [])),
            portfolio_id=UUID(data["portfolio_id"]) if data.get("portfolio_id") else None,
            risk_metrics=data.get("risk_metrics", {}),
            metadata=data.get("metadata", {})
        )


class StateRecoveryService:
    """
    Service for persisting and recovering trading state.
    
    Features:
    - Periodic state snapshots
    - Crash recovery
    - State validation
    - Cleanup of old snapshots
    """
    
    def __init__(
        self,
        state_dir: str = "./trading_state",
        snapshot_interval_seconds: int = 60,
        max_snapshots: int = 100,
        retention_days: int = 7
    ):
        """
        Initialize state recovery service.
        
        Args:
            state_dir: Directory for storing state files
            snapshot_interval_seconds: Interval between snapshots
            max_snapshots: Maximum number of snapshots to keep
            retention_days: Days to retain old snapshots
        """
        self.state_dir = Path(state_dir)
        self.snapshot_interval = snapshot_interval_seconds
        self.max_snapshots = max_snapshots
        self.retention_days = retention_days
        
        # Create state directory if it doesn't exist
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Paths for different state files
        self.current_state_file = self.state_dir / "current_state.json"
        self.backup_state_file = self.state_dir / "backup_state.json"
        self.snapshots_dir = self.state_dir / "snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
        
        logger.info(f"StateRecoveryService initialized with state_dir: {self.state_dir}")
    
    async def save_state(
        self,
        session: Optional[TradingSession],
        active_orders: Dict[UUID, Order],
        active_positions: Dict[str, Position],
        monitored_symbols: Set[str],
        risk_metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save current trading state.
        
        Args:
            session: Current trading session
            active_orders: Active orders
            active_positions: Active positions
            monitored_symbols: Monitored symbols
            risk_metrics: Current risk metrics
        """
        try:
            # Create state snapshot
            snapshot = StateSnapshot(
                timestamp=datetime.utcnow(),
                session=session,
                active_orders=self._serialize_orders(active_orders),
                active_positions=self._serialize_positions(active_positions),
                monitored_symbols=monitored_symbols,
                portfolio_id=session.portfolio_id if session else None,
                risk_metrics=risk_metrics or {},
                metadata={
                    "version": "1.0",
                    "save_reason": "periodic"
                }
            )
            
            # Save to current state file
            self._save_to_file(self.current_state_file, snapshot.to_dict())
            
            # Create backup
            if self.current_state_file.exists():
                self._save_to_file(self.backup_state_file, snapshot.to_dict())
            
            # Save snapshot if interval has passed
            if self._should_create_snapshot():
                await self._create_snapshot(snapshot)
            
            logger.debug("State saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    async def recover_state(self) -> Optional[StateSnapshot]:
        """
        Recover trading state from storage.
        
        Returns:
            Recovered state snapshot or None
        """
        try:
            # Try to load current state
            if self.current_state_file.exists():
                state_data = self._load_from_file(self.current_state_file)
                if state_data:
                    snapshot = StateSnapshot.from_dict(state_data)
                    
                    # Validate state
                    if self._validate_snapshot(snapshot):
                        logger.info(f"State recovered from {self.current_state_file}")
                        return snapshot
            
            # Try backup if current failed
            if self.backup_state_file.exists():
                state_data = self._load_from_file(self.backup_state_file)
                if state_data:
                    snapshot = StateSnapshot.from_dict(state_data)
                    
                    if self._validate_snapshot(snapshot):
                        logger.info(f"State recovered from backup")
                        return snapshot
            
            # Try latest snapshot
            latest_snapshot = await self._get_latest_snapshot()
            if latest_snapshot:
                logger.info("State recovered from snapshot")
                return latest_snapshot
            
            logger.warning("No valid state found for recovery")
            return None
            
        except Exception as e:
            logger.error(f"Failed to recover state: {e}")
            return None
    
    async def save_critical_state(
        self,
        session: TradingSession,
        reason: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save critical state immediately (e.g., before shutdown).
        
        Args:
            session: Trading session
            reason: Reason for critical save
            additional_data: Additional data to save
        """
        try:
            timestamp = datetime.utcnow()
            filename = f"critical_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.state_dir / filename
            
            data = {
                "timestamp": timestamp.isoformat(),
                "reason": reason,
                "session": {
                    "id": str(session.id),
                    "status": session.status.value,
                    "portfolio_id": str(session.portfolio_id),
                    "total_pnl": str(session.total_pnl),
                    "total_trades": session.total_trades
                },
                "additional_data": additional_data or {}
            }
            
            self._save_to_file(filepath, data)
            logger.info(f"Critical state saved: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save critical state: {e}")
    
    async def cleanup_old_states(self) -> None:
        """Clean up old state files and snapshots"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            # Clean up snapshots
            for snapshot_file in self.snapshots_dir.glob("snapshot_*.json"):
                try:
                    # Parse timestamp from filename
                    timestamp_str = snapshot_file.stem.replace("snapshot_", "")
                    file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    if file_date < cutoff_date:
                        snapshot_file.unlink()
                        logger.debug(f"Deleted old snapshot: {snapshot_file.name}")
                        
                except Exception as e:
                    logger.warning(f"Error processing snapshot file {snapshot_file}: {e}")
            
            # Limit number of snapshots
            snapshots = sorted(self.snapshots_dir.glob("snapshot_*.json"))
            if len(snapshots) > self.max_snapshots:
                for snapshot_file in snapshots[:-self.max_snapshots]:
                    snapshot_file.unlink()
                    logger.debug(f"Deleted excess snapshot: {snapshot_file.name}")
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old states: {e}")
    
    def _serialize_orders(self, orders: Dict[UUID, Order]) -> Dict[UUID, Dict[str, Any]]:
        """Serialize orders for storage"""
        serialized = {}
        
        for order_id, order in orders.items():
            serialized[order_id] = {
                "id": str(order.id),
                "symbol": order.symbol.value,
                "quantity": order.quantity.value,
                "order_type": order.order_type.value,
                "side": order.side.value,
                "status": order.status.value,
                "price": float(order.price.value) if order.price else None,
                "filled_quantity": order.filled_quantity,
                "average_price": float(order.average_price) if order.average_price else None,
                "broker_order_id": order.broker_order_id,
                "portfolio_id": str(order.portfolio_id),
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat()
            }
        
        return serialized
    
    def _serialize_positions(self, positions: Dict[str, Position]) -> Dict[str, Dict[str, Any]]:
        """Serialize positions for storage"""
        serialized = {}
        
        for symbol, position in positions.items():
            serialized[symbol] = {
                "id": str(position.id),
                "symbol": position.symbol,
                "side": position.side.value,
                "quantity": position.quantity.value,
                "entry_price": float(position.entry_price.value),
                "mark_price": float(position.mark_price.value) if position.mark_price else None,
                "leverage": position.leverage.value if position.leverage else 1,
                "unrealized_pnl": float(position.unrealized_pnl),
                "realized_pnl": float(position.realized_pnl),
                "margin": float(position.initial_margin),
                "liquidation_price": float(position.liquidation_price.value) if position.liquidation_price else None,
                "portfolio_id": str(position.portfolio_id),
                "is_open": position.is_open
            }
        
        return serialized
    
    def _save_to_file(self, filepath: Path, data: Dict[str, Any]) -> None:
        """Save data to JSON file"""
        try:
            # Convert Decimal to string for JSON serialization
            json_data = json.dumps(data, default=str, indent=2)
            
            # Write atomically (write to temp then rename)
            temp_file = filepath.with_suffix('.tmp')
            temp_file.write_text(json_data)
            temp_file.replace(filepath)
            
        except Exception as e:
            logger.error(f"Failed to save to {filepath}: {e}")
            raise
    
    def _load_from_file(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Load data from JSON file"""
        try:
            if not filepath.exists():
                return None
            
            json_data = filepath.read_text()
            return json.loads(json_data)
            
        except Exception as e:
            logger.error(f"Failed to load from {filepath}: {e}")
            return None
    
    def _should_create_snapshot(self) -> bool:
        """Check if a new snapshot should be created"""
        try:
            # Get latest snapshot
            snapshots = sorted(self.snapshots_dir.glob("snapshot_*.json"))
            if not snapshots:
                return True
            
            latest = snapshots[-1]
            timestamp_str = latest.stem.replace("snapshot_", "")
            latest_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            
            # Check if interval has passed
            return (datetime.utcnow() - latest_time).total_seconds() >= self.snapshot_interval
            
        except Exception:
            return True
    
    async def _create_snapshot(self, snapshot: StateSnapshot) -> None:
        """Create a new snapshot"""
        try:
            timestamp = datetime.utcnow()
            filename = f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.snapshots_dir / filename
            
            self._save_to_file(filepath, snapshot.to_dict())
            logger.debug(f"Snapshot created: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
    
    async def _get_latest_snapshot(self) -> Optional[StateSnapshot]:
        """Get the latest valid snapshot"""
        try:
            snapshots = sorted(self.snapshots_dir.glob("snapshot_*.json"))
            
            # Try snapshots from newest to oldest
            for snapshot_file in reversed(snapshots):
                data = self._load_from_file(snapshot_file)
                if data:
                    snapshot = StateSnapshot.from_dict(data)
                    if self._validate_snapshot(snapshot):
                        return snapshot
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get latest snapshot: {e}")
            return None
    
    def _validate_snapshot(self, snapshot: StateSnapshot) -> bool:
        """
        Validate a snapshot for consistency.
        
        Args:
            snapshot: Snapshot to validate
            
        Returns:
            True if valid
        """
        try:
            # Check timestamp is reasonable (not too old)
            age = datetime.utcnow() - snapshot.timestamp
            if age.days > self.retention_days:
                logger.warning(f"Snapshot too old: {age.days} days")
                return False
            
            # Check session consistency
            if snapshot.session:
                if snapshot.session.status == TradingSessionStatus.RUNNING:
                    # Check if session was running too long ago
                    if age.total_seconds() > 3600:  # 1 hour
                        logger.warning("Running session is too old")
                        return False
            
            # Validate portfolio ID
            if snapshot.session and not snapshot.portfolio_id:
                logger.warning("Session exists but no portfolio ID")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Snapshot validation error: {e}")
            return False
    
    async def export_state_history(
        self,
        output_file: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> None:
        """
        Export state history to file.
        
        Args:
            output_file: Output file path
            start_date: Start date filter
            end_date: End date filter
        """
        try:
            history = []
            
            # Collect all snapshots
            for snapshot_file in sorted(self.snapshots_dir.glob("snapshot_*.json")):
                data = self._load_from_file(snapshot_file)
                if data:
                    snapshot = StateSnapshot.from_dict(data)
                    
                    # Apply date filters
                    if start_date and snapshot.timestamp < start_date:
                        continue
                    if end_date and snapshot.timestamp > end_date:
                        continue
                    
                    history.append(snapshot.to_dict())
            
            # Save to output file
            output_path = Path(output_file)
            self._save_to_file(output_path, {"history": history})
            
            logger.info(f"Exported {len(history)} snapshots to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to export state history: {e}")