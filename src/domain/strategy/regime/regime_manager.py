"""
Regime manager for handling market regime configuration.

This module provides functionality to read, update, and persist
market regime settings in the configuration file.
"""

import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from .regime_models import MarketRegime, GridMode, get_grid_mode_for_regime


logger = logging.getLogger(__name__)


class RegimeManager:
    """Manages market regime configuration and persistence."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the regime manager.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = Path(config_path)
        self._ensure_config_exists()
        
    def _ensure_config_exists(self) -> None:
        """Ensure the config file exists with default structure."""
        if not self.config_path.exists():
            default_config = {
                "trading": {
                    "market_regime": "none",
                    "regime_updated": datetime.now().isoformat()
                }
            }
            self._write_config(default_config)
            logger.info(f"Created default config at {self.config_path}")
    
    def _read_config(self) -> Dict[str, Any]:
        """Read the entire configuration file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error reading config: {e}")
            return {}
    
    def _write_config(self, config: Dict[str, Any]) -> None:
        """Write the configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            logger.error(f"Error writing config: {e}")
            raise
    
    def get_current_regime(self) -> MarketRegime:
        """
        Get the current market regime from configuration.
        
        Returns:
            Current market regime
        """
        config = self._read_config()
        
        # Ensure trading section exists
        if "trading" not in config:
            config["trading"] = {}
        
        # Get regime or default to NONE
        regime_str = config.get("trading", {}).get("market_regime", "none")
        
        try:
            regime = MarketRegime.from_string(regime_str)
            logger.debug(f"Current regime: {regime}")
            return regime
        except ValueError as e:
            logger.warning(f"Invalid regime in config: {regime_str}, defaulting to NONE")
            return MarketRegime.NONE
    
    def get_current_grid_mode(self) -> GridMode:
        """
        Get the grid mode based on current market regime.
        
        Returns:
            Grid mode corresponding to current regime
        """
        regime = self.get_current_regime()
        mode = get_grid_mode_for_regime(regime)
        logger.debug(f"Grid mode for {regime}: {mode}")
        return mode
    
    def update_regime(self, regime: MarketRegime) -> bool:
        """
        Update the market regime in configuration.
        
        Args:
            regime: New market regime to set
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            config = self._read_config()
            
            # Ensure trading section exists
            if "trading" not in config:
                config["trading"] = {}
            
            # Update regime and timestamp
            config["trading"]["market_regime"] = regime.value
            config["trading"]["regime_updated"] = datetime.now().isoformat()
            
            # Write back to file
            self._write_config(config)
            
            logger.info(f"Updated market regime to: {regime}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update regime: {e}")
            return False
    
    def get_regime_info(self) -> Dict[str, Any]:
        """
        Get detailed information about current regime settings.
        
        Returns:
            Dictionary with regime, grid mode, and last update time
        """
        config = self._read_config()
        trading_config = config.get("trading", {})
        
        regime = self.get_current_regime()
        grid_mode = self.get_current_grid_mode()
        
        return {
            "market_regime": regime.value,
            "grid_mode": grid_mode.value,
            "last_updated": trading_config.get("regime_updated", "unknown"),
            "config_path": str(self.config_path)
        }
    
    def get_last_update_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the last regime update.
        
        Returns:
            Datetime of last update or None if not available
        """
        config = self._read_config()
        timestamp_str = config.get("trading", {}).get("regime_updated")
        
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid timestamp in config: {timestamp_str}")
                return None
        return None