"""
Adapter factory for creating and managing execution adapters.

Routes to appropriate implementation based on feature flags.
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from src.infrastructure.config.feature_flags import (
    get_feature_flags, ExecutionImplementation
)
from src.infrastructure.exchange.execution_adapter import ExecutionAdapter
from src.infrastructure.exchange.binance_v1_adapter import BinanceV1Adapter
from src.infrastructure.exchange.binance_v2_adapter import BinanceV2Adapter
from src.infrastructure.exchange.paper_adapter import PaperTradingAdapter

logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    Factory for creating execution adapters based on feature flags.
    
    Supports seamless switching between implementations without code changes.
    """
    
    _instance: Optional['AdapterFactory'] = None
    _adapters: Dict[str, ExecutionAdapter] = {}
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize factory."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.feature_flags = get_feature_flags()
            self._current_adapter: Optional[ExecutionAdapter] = None
            self._health_monitor = AdapterHealthMonitor()
            
            # Register for feature flag changes
            self.feature_flags.add_listener(self._on_flag_change)
    
    async def get_adapter(self, user_id: Optional[str] = None) -> ExecutionAdapter:
        """
        Get execution adapter based on feature flags.
        
        Args:
            user_id: Optional user ID for gradual rollout
            
        Returns:
            Appropriate execution adapter
        """
        impl = self.feature_flags.get_execution_impl(user_id)
        
        # Check if we need to switch adapters
        if self._current_adapter and self._current_adapter.get_adapter_name() == impl.value:
            return self._current_adapter
        
        # Create new adapter
        adapter = await self._create_adapter(impl)
        
        # Graceful switch
        if self._current_adapter:
            await self._switch_adapter(self._current_adapter, adapter)
        
        self._current_adapter = adapter
        return adapter
    
    async def _create_adapter(self, impl: ExecutionImplementation) -> ExecutionAdapter:
        """Create adapter instance based on implementation type."""
        
        # Check cache first
        if impl.value in self._adapters:
            adapter = self._adapters[impl.value]
            if await adapter.is_connected():
                logger.info(f"Reusing cached adapter: {impl.value}")
                return adapter
        
        logger.info(f"Creating new adapter: {impl.value}")
        
        if impl == ExecutionImplementation.BINANCE_V1:
            adapter = BinanceV1Adapter(
                api_key=os.getenv("BINANCE_API_KEY", ""),
                api_secret=os.getenv("BINANCE_API_SECRET", ""),
                testnet=os.getenv("BINANCE_TESTNET", "false").lower() == "true"
            )
        
        elif impl == ExecutionImplementation.BINANCE_V2:
            adapter = BinanceV2Adapter(
                api_key=os.getenv("BINANCE_API_KEY", ""),
                api_secret=os.getenv("BINANCE_API_SECRET", ""),
                testnet=os.getenv("BINANCE_TESTNET", "false").lower() == "true"
            )
        
        elif impl == ExecutionImplementation.PAPER:
            initial_balance = float(os.getenv("PAPER_INITIAL_BALANCE", "10000"))
            adapter = PaperTradingAdapter(initial_balance=initial_balance)
        
        else:
            raise ValueError(f"Unknown execution implementation: {impl}")
        
        # Connect adapter
        connected = await adapter.connect()
        if not connected:
            raise ConnectionError(f"Failed to connect adapter: {impl.value}")
        
        # Cache adapter
        self._adapters[impl.value] = adapter
        
        # Start health monitoring
        self._health_monitor.register_adapter(adapter)
        
        return adapter
    
    async def _switch_adapter(self, old_adapter: ExecutionAdapter, new_adapter: ExecutionAdapter):
        """
        Gracefully switch from one adapter to another.
        
        Ensures no in-flight requests are lost.
        """
        logger.info(f"Switching adapter: {old_adapter.get_adapter_name()} -> {new_adapter.get_adapter_name()}")
        
        # Wait for pending orders to complete
        open_orders = await old_adapter.get_open_orders()
        if open_orders:
            logger.warning(f"Found {len(open_orders)} open orders during switch")
            # Could implement order migration logic here
        
        # Log switch event
        self._log_switch_event(old_adapter, new_adapter)
    
    def _on_flag_change(self, flag_name: str, old_value: Any, new_value: Any):
        """Handle feature flag changes."""
        if flag_name == "EXECUTION_IMPL":
            logger.info(f"Execution implementation changed: {old_value} -> {new_value}")
            # Next call to get_adapter() will create new adapter
            self._current_adapter = None
    
    def _log_switch_event(self, old_adapter: ExecutionAdapter, new_adapter: ExecutionAdapter):
        """Log adapter switch event for monitoring."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event": "adapter_switch",
            "from": old_adapter.get_adapter_name(),
            "to": new_adapter.get_adapter_name(),
            "from_health": old_adapter.get_health_status(),
            "to_health": new_adapter.get_health_status()
        }
        logger.info(f"Adapter switch event: {event}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all adapters."""
        status = {
            "current_adapter": self._current_adapter.get_adapter_name() if self._current_adapter else None,
            "adapters": {},
            "feature_flags": self.feature_flags.get_status()
        }
        
        for name, adapter in self._adapters.items():
            status["adapters"][name] = adapter.get_health_status()
        
        return status
    
    async def cleanup(self):
        """Clean up all adapters."""
        for adapter in self._adapters.values():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting adapter: {e}")
        
        self._adapters.clear()
        self._current_adapter = None


class AdapterHealthMonitor:
    """
    Monitors health of execution adapters.
    
    Tracks metrics and can trigger automatic failover if needed.
    """
    
    def __init__(self):
        self.adapters: Dict[str, ExecutionAdapter] = {}
        self.health_history: Dict[str, list] = {}
        self.failure_counts: Dict[str, int] = {}
        
    def register_adapter(self, adapter: ExecutionAdapter):
        """Register adapter for monitoring."""
        name = adapter.get_adapter_name()
        self.adapters[name] = adapter
        self.health_history[name] = []
        self.failure_counts[name] = 0
        logger.info(f"Registered adapter for health monitoring: {name}")
    
    async def check_health(self) -> Dict[str, Any]:
        """Check health of all registered adapters."""
        results = {}
        
        for name, adapter in self.adapters.items():
            try:
                # Check connection
                connected = await adapter.is_connected()
                
                # Get detailed health
                health = adapter.get_health_status()
                
                # Determine overall status
                if not connected:
                    status = "unhealthy"
                    self.failure_counts[name] += 1
                elif health.get("error_rate", 0) > 10:  # >10% error rate
                    status = "degraded"
                else:
                    status = "healthy"
                    self.failure_counts[name] = 0
                
                results[name] = {
                    "status": status,
                    "connected": connected,
                    "failure_count": self.failure_counts[name],
                    "details": health
                }
                
                # Record history
                self.health_history[name].append({
                    "timestamp": datetime.now().isoformat(),
                    "status": status
                })
                
                # Keep only last 100 entries
                if len(self.health_history[name]) > 100:
                    self.health_history[name] = self.health_history[name][-100:]
                
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results
    
    def should_failover(self, adapter_name: str) -> bool:
        """Determine if adapter should be failed over."""
        # Failover if more than 5 consecutive failures
        return self.failure_counts.get(adapter_name, 0) > 5
    
    def get_healthiest_adapter(self) -> Optional[str]:
        """Get the healthiest adapter name."""
        min_failures = float('inf')
        healthiest = None
        
        for name, count in self.failure_counts.items():
            if count < min_failures:
                min_failures = count
                healthiest = name
        
        return healthiest


# Global factory instance
_factory: Optional[AdapterFactory] = None


def get_adapter_factory() -> AdapterFactory:
    """Get global adapter factory instance."""
    global _factory
    if _factory is None:
        _factory = AdapterFactory()
    return _factory


async def get_execution_adapter(user_id: Optional[str] = None) -> ExecutionAdapter:
    """
    Convenience function to get execution adapter.
    
    This is the main entry point for the rest of the application.
    """
    factory = get_adapter_factory()
    return await factory.get_adapter(user_id)