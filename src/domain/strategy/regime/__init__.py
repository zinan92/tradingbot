"""
Market regime management for grid trading strategy.

This module handles user-defined market regimes (bullish/bearish/range/none)
and automatically maps them to appropriate grid trading modes.
"""

from .regime_models import MarketRegime, GridMode, REGIME_TO_MODE_MAPPING, get_grid_mode_for_regime
from .regime_manager import RegimeManager

__all__ = [
    "MarketRegime",
    "GridMode", 
    "REGIME_TO_MODE_MAPPING",
    "get_grid_mode_for_regime",
    "RegimeManager"
]