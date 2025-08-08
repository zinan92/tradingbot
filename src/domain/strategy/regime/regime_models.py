"""
Market regime models and mappings for grid trading.

This module defines the market regime types and their automatic
mapping to grid trading modes.
"""

from enum import Enum
from typing import Dict


class MarketRegime(Enum):
    """Market regime as defined by the user."""
    
    BULLISH = "bullish"   # Expecting upward price movement
    BEARISH = "bearish"   # Expecting downward price movement
    RANGE = "range"       # Expecting sideways movement
    NONE = "none"         # No clear direction or trading disabled
    
    @classmethod
    def from_string(cls, value: str) -> "MarketRegime":
        """Create regime from string value (case-insensitive)."""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(
                f"Invalid regime: {value}. "
                f"Valid options: {', '.join([r.value for r in cls])}"
            )
    
    def __str__(self) -> str:
        return self.value


class GridMode(Enum):
    """Grid trading mode derived from market regime."""
    
    LONG_ONLY = "long_only"          # Only buy orders (for bullish markets)
    SHORT_ONLY = "short_only"        # Only sell orders (for bearish markets)
    BIDIRECTIONAL = "bidirectional"  # Both buy and sell (for ranging markets)
    DISABLED = "disabled"            # No grid trading
    
    def __str__(self) -> str:
        return self.value


# Automatic mapping from market regime to grid mode
REGIME_TO_MODE_MAPPING: Dict[MarketRegime, GridMode] = {
    MarketRegime.BULLISH: GridMode.LONG_ONLY,
    MarketRegime.BEARISH: GridMode.SHORT_ONLY,
    MarketRegime.RANGE: GridMode.BIDIRECTIONAL,
    MarketRegime.NONE: GridMode.DISABLED
}


def get_grid_mode_for_regime(regime: MarketRegime) -> GridMode:
    """Get the appropriate grid mode for a given market regime."""
    return REGIME_TO_MODE_MAPPING[regime]