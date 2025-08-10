"""
Monitoring Module

Provides metrics collection, system monitoring, and health checks
for the trading system.
"""

from .api_metrics import router as metrics_router

__all__ = [
    'metrics_router'
]