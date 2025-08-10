"""
CLI configuration management.

Handles configuration, preferences, and state for the ops CLI.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CLIConfig:
    """CLI configuration."""
    mode: str = "testnet"  # testnet, paper, mainnet
    api_base_url: str = "http://localhost:8000"
    ws_base_url: str = "ws://localhost:8000"
    log_file: str = "logs/trading.log"
    default_symbol: str = "BTCUSDT"
    monitor_interval: int = 1
    tail_lines: int = 20
    confirm_mainnet: bool = True
    show_safety_ladder: bool = True
    color_output: bool = True
    
    # Safety settings
    max_position_size: float = 0.1  # Max 10% per position
    require_2fa_mainnet: bool = False
    emergency_contact: Optional[str] = None
    
    # Session state
    last_mode_switch: Optional[str] = None
    mainnet_enabled_at: Optional[str] = None
    total_operations: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert datetime fields
        if self.last_mode_switch:
            data["last_mode_switch"] = self.last_mode_switch
        if self.mainnet_enabled_at:
            data["mainnet_enabled_at"] = self.mainnet_enabled_at
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CLIConfig':
        """Create from dictionary."""
        return cls(**data)


class ConfigManager:
    """Manages CLI configuration persistence."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "cli_config.json"
        self.backup_file = self.config_dir / "cli_config.backup.json"
        self.config = self._load_config()
    
    def _load_config(self) -> CLIConfig:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    return CLIConfig.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                # Try backup
                if self.backup_file.exists():
                    try:
                        with open(self.backup_file, 'r') as f:
                            data = json.load(f)
                            return CLIConfig.from_dict(data)
                    except Exception as e2:
                        logger.error(f"Failed to load backup: {e2}")
        
        # Return default config
        return CLIConfig()
    
    def save_config(self):
        """Save configuration to file."""
        try:
            # Backup current config
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    backup_data = f.read()
                with open(self.backup_file, 'w') as f:
                    f.write(backup_data)
            
            # Save new config
            with open(self.config_file, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            
            logger.info("Configuration saved")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return getattr(self.config, key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value."""
        setattr(self.config, key, value)
        self.config.total_operations += 1
        self.save_config()
    
    def update_mode(self, mode: str):
        """Update trading mode with safety tracking."""
        old_mode = self.config.mode
        self.config.mode = mode
        self.config.last_mode_switch = datetime.now().isoformat()
        
        # Track mainnet activation
        if mode == "mainnet":
            self.config.mainnet_enabled_at = datetime.now().isoformat()
        
        # Log mode change
        logger.info(f"Mode changed: {old_mode} -> {mode}")
        
        self.save_config()
    
    def get_safety_status(self) -> Dict[str, Any]:
        """Get safety-related status."""
        return {
            "current_mode": self.config.mode,
            "mainnet_enabled": self.config.mainnet_enabled_at is not None,
            "mainnet_duration": self._get_mainnet_duration(),
            "operations_count": self.config.total_operations,
            "safety_features": {
                "confirm_mainnet": self.config.confirm_mainnet,
                "max_position_size": self.config.max_position_size,
                "require_2fa": self.config.require_2fa_mainnet,
                "show_ladder": self.config.show_safety_ladder
            }
        }
    
    def _get_mainnet_duration(self) -> Optional[str]:
        """Get how long mainnet has been enabled."""
        if not self.config.mainnet_enabled_at:
            return None
        
        try:
            enabled_at = datetime.fromisoformat(self.config.mainnet_enabled_at)
            duration = datetime.now() - enabled_at
            
            hours = duration.total_seconds() / 3600
            if hours < 1:
                return f"{int(duration.total_seconds() / 60)} minutes"
            elif hours < 24:
                return f"{int(hours)} hours"
            else:
                return f"{int(hours / 24)} days"
        except:
            return None
    
    def reset_to_safe_mode(self):
        """Reset to safe testnet mode."""
        self.config.mode = "testnet"
        self.config.mainnet_enabled_at = None
        self.save_config()
        logger.info("Reset to safe testnet mode")
    
    def validate_config(self) -> bool:
        """Validate configuration integrity."""
        try:
            # Check mode is valid
            if self.config.mode not in ["testnet", "paper", "mainnet"]:
                logger.error(f"Invalid mode: {self.config.mode}")
                return False
            
            # Check URLs are valid
            if not self.config.api_base_url.startswith(("http://", "https://")):
                logger.error(f"Invalid API URL: {self.config.api_base_url}")
                return False
            
            if not self.config.ws_base_url.startswith(("ws://", "wss://")):
                logger.error(f"Invalid WebSocket URL: {self.config.ws_base_url}")
                return False
            
            # Check safety limits
            if self.config.max_position_size > 1.0 or self.config.max_position_size <= 0:
                logger.error(f"Invalid max position size: {self.config.max_position_size}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False


class SafetyChecker:
    """Safety checks for CLI operations."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
    
    def check_mode_transition(self, from_mode: str, to_mode: str) -> tuple[bool, str]:
        """
        Check if mode transition is safe.
        
        Returns:
            Tuple of (is_safe, reason)
        """
        # Define safe transitions
        safe_transitions = {
            "testnet": ["paper", "testnet"],
            "paper": ["testnet", "mainnet", "paper"],
            "mainnet": ["paper", "testnet", "mainnet"]
        }
        
        if to_mode not in safe_transitions.get(from_mode, []):
            return False, f"Direct transition from {from_mode} to {to_mode} not recommended"
        
        # Check if jumping to mainnet too quickly
        if to_mode == "mainnet":
            if from_mode == "testnet":
                return False, "Must test in paper mode before mainnet"
            
            # Check if sufficient time in paper mode
            last_switch = self.config.config.last_mode_switch
            if last_switch:
                try:
                    switch_time = datetime.fromisoformat(last_switch)
                    time_in_mode = datetime.now() - switch_time
                    
                    if time_in_mode.total_seconds() < 3600:  # Less than 1 hour
                        return False, "Spend more time in paper mode before mainnet (minimum 1 hour recommended)"
                except:
                    pass
        
        return True, "Transition allowed"
    
    def check_operation_allowed(self, operation: str) -> tuple[bool, str]:
        """
        Check if an operation is allowed in current mode.
        
        Returns:
            Tuple of (is_allowed, reason)
        """
        mode = self.config.config.mode
        
        # Define restricted operations
        restrictions = {
            "testnet": [],  # No restrictions in testnet
            "paper": [],    # No restrictions in paper
            "mainnet": []   # All operations allowed but with confirmations
        }
        
        restricted = restrictions.get(mode, [])
        
        if operation in restricted:
            return False, f"Operation '{operation}' not allowed in {mode} mode"
        
        return True, "Operation allowed"
    
    def get_safety_warnings(self) -> list[str]:
        """Get current safety warnings."""
        warnings = []
        mode = self.config.config.mode
        
        if mode == "mainnet":
            warnings.append("⚠️  MAINNET ACTIVE - Real money at risk")
            
            # Check if recently switched
            if self.config.config.mainnet_enabled_at:
                try:
                    enabled_at = datetime.fromisoformat(self.config.config.mainnet_enabled_at)
                    duration = datetime.now() - enabled_at
                    
                    if duration.total_seconds() < 300:  # Less than 5 minutes
                        warnings.append("⚠️  Mainnet recently activated - trade carefully")
                except:
                    pass
            
            # Check position size limits
            if self.config.config.max_position_size > 0.2:
                warnings.append(f"⚠️  High position size limit: {self.config.config.max_position_size:.0%}")
        
        elif mode == "paper":
            warnings.append("ℹ️  Paper trading mode - orders are simulated")
        
        return warnings