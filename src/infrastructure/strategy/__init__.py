"""
Strategy Infrastructure Module

Provides strategy registry and configuration management.
"""

from .strategy_registry import StrategyRegistry, get_registry

__all__ = [
    'StrategyRegistry',
    'get_registry'
]