"""
Health Check Router

Provides health status endpoints for all system modules.
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import asyncio
import logging

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration"""
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class ModuleHealth(BaseModel):
    """Module health status model"""
    status: HealthStatus = Field(..., description="Current health status")
    last_success_ts: Optional[datetime] = Field(None, description="Last successful operation timestamp")
    lag_seconds: float = Field(0, description="Lag in seconds from expected state")
    error_rate: float = Field(0, ge=0, le=1, description="Error rate (0-1)")
    queue_depth: int = Field(0, ge=0, description="Number of items in queue")
    message: Optional[str] = Field(None, description="Additional status message")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthCheckRegistry:
    """Registry for module health check functions"""
    
    def __init__(self):
        self._checks: Dict[str, Any] = {}
        self._cached_results: Dict[str, tuple[ModuleHealth, datetime]] = {}
        self._cache_ttl = timedelta(seconds=5)
    
    def register(self, module: str, check_func):
        """Register a health check function for a module"""
        self._checks[module] = check_func
    
    async def check_health(self, module: str) -> ModuleHealth:
        """Execute health check for a module with caching"""
        # Check cache
        if module in self._cached_results:
            result, timestamp = self._cached_results[module]
            if datetime.utcnow() - timestamp < self._cache_ttl:
                return result
        
        # Execute check
        if module not in self._checks:
            raise KeyError(f"No health check registered for module: {module}")
        
        try:
            result = await self._checks[module]()
            self._cached_results[module] = (result, datetime.utcnow())
            return result
        except Exception as e:
            logger.error(f"Health check failed for {module}: {str(e)}")
            return ModuleHealth(
                status=HealthStatus.DOWN,
                last_success_ts=None,
                lag_seconds=999999,
                error_rate=1.0,
                queue_depth=0,
                message=f"Health check failed: {str(e)}"
            )
    
    def list_modules(self) -> list[str]:
        """List all registered modules"""
        return list(self._checks.keys())


# Global registry instance
health_registry = HealthCheckRegistry()


# Module-specific health check implementations

async def check_market_data_health() -> ModuleHealth:
    """Check market data module health"""
    try:
        # In production, this would check actual market data connection
        # For now, we'll simulate a health check
        last_update = datetime.utcnow() - timedelta(seconds=2)
        lag = (datetime.utcnow() - last_update).total_seconds()
        
        if lag < 5:
            status = HealthStatus.OK
        elif lag < 30:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.DOWN
        
        return ModuleHealth(
            status=status,
            last_success_ts=last_update,
            lag_seconds=lag,
            error_rate=0.01,  # Simulated 1% error rate
            queue_depth=0
        )
    except Exception as e:
        logger.error(f"Market data health check error: {e}")
        return ModuleHealth(
            status=HealthStatus.DOWN,
            error_rate=1.0,
            lag_seconds=999999
        )


async def check_execution_health() -> ModuleHealth:
    """Check execution module health"""
    try:
        # Simulated health check for execution module
        return ModuleHealth(
            status=HealthStatus.OK,
            last_success_ts=datetime.utcnow(),
            lag_seconds=0,
            error_rate=0.005,  # 0.5% error rate
            queue_depth=3  # 3 pending orders
        )
    except Exception as e:
        logger.error(f"Execution health check error: {e}")
        return ModuleHealth(
            status=HealthStatus.DOWN,
            error_rate=1.0,
            lag_seconds=999999
        )


async def check_backtest_health() -> ModuleHealth:
    """Check backtest module health"""
    try:
        # Simulated health check for backtest module
        return ModuleHealth(
            status=HealthStatus.OK,
            last_success_ts=datetime.utcnow() - timedelta(minutes=1),
            lag_seconds=60,
            error_rate=0.0,
            queue_depth=1  # 1 backtest in queue
        )
    except Exception as e:
        logger.error(f"Backtest health check error: {e}")
        return ModuleHealth(
            status=HealthStatus.DOWN,
            error_rate=1.0,
            lag_seconds=999999
        )


async def check_strategy_health() -> ModuleHealth:
    """Check strategy module health"""
    try:
        # Simulated health check for strategy module
        return ModuleHealth(
            status=HealthStatus.OK,
            last_success_ts=datetime.utcnow(),
            lag_seconds=0.5,
            error_rate=0.0,
            queue_depth=0
        )
    except Exception as e:
        logger.error(f"Strategy health check error: {e}")
        return ModuleHealth(
            status=HealthStatus.DOWN,
            error_rate=1.0,
            lag_seconds=999999
        )


async def check_risk_health() -> ModuleHealth:
    """Check risk module health"""
    try:
        # Simulated health check for risk module
        return ModuleHealth(
            status=HealthStatus.OK,
            last_success_ts=datetime.utcnow(),
            lag_seconds=0,
            error_rate=0.0,
            queue_depth=0
        )
    except Exception as e:
        logger.error(f"Risk health check error: {e}")
        return ModuleHealth(
            status=HealthStatus.DOWN,
            error_rate=1.0,
            lag_seconds=999999
        )


async def check_telemetry_health() -> ModuleHealth:
    """Check telemetry module health"""
    try:
        # Simulated health check for telemetry module
        return ModuleHealth(
            status=HealthStatus.OK,
            last_success_ts=datetime.utcnow(),
            lag_seconds=0.1,
            error_rate=0.0,
            queue_depth=15  # 15 metrics in buffer
        )
    except Exception as e:
        logger.error(f"Telemetry health check error: {e}")
        return ModuleHealth(
            status=HealthStatus.DOWN,
            error_rate=1.0,
            lag_seconds=999999
        )


# Register all health checks
health_registry.register("market_data", check_market_data_health)
health_registry.register("execution", check_execution_health)
health_registry.register("backtest", check_backtest_health)
health_registry.register("strategy", check_strategy_health)
health_registry.register("risk", check_risk_health)
health_registry.register("telemetry", check_telemetry_health)


# Create router
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/{module}", response_model=ModuleHealth)
async def get_module_health(module: str) -> ModuleHealth:
    """
    Get health status for a specific module
    
    Args:
        module: Module name (market_data, execution, backtest, strategy, risk, telemetry)
    
    Returns:
        Module health status
    """
    try:
        return await health_registry.check_health(module)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Module '{module}' not found. Available modules: {health_registry.list_modules()}"
        )


@router.get("/", response_model=Dict[str, ModuleHealth])
async def get_all_health() -> Dict[str, ModuleHealth]:
    """
    Get health status for all modules
    
    Returns:
        Dictionary of module health statuses
    """
    results = {}
    modules = health_registry.list_modules()
    
    # Check all modules concurrently
    tasks = {
        module: health_registry.check_health(module)
        for module in modules
    }
    
    for module, task in tasks.items():
        try:
            results[module] = await task
        except Exception as e:
            logger.error(f"Failed to check health for {module}: {e}")
            results[module] = ModuleHealth(
                status=HealthStatus.DOWN,
                error_rate=1.0,
                lag_seconds=999999,
                message=str(e)
            )
    
    return results


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Kubernetes-style readiness probe
    
    Returns 200 if system is ready to serve traffic, 503 otherwise
    """
    all_health = await get_all_health()
    
    # System is ready if no modules are DOWN
    down_modules = [
        module for module, health in all_health.items()
        if health.status == HealthStatus.DOWN
    ]
    
    if down_modules:
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "down_modules": down_modules
            }
        )
    
    return {
        "ready": True,
        "modules": len(all_health),
        "degraded_modules": [
            module for module, health in all_health.items()
            if health.status == HealthStatus.DEGRADED
        ]
    }


@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """
    Kubernetes-style liveness probe
    
    Always returns 200 if the service is running
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }