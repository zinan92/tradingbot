"""
Feature flag configuration system for controlled rollouts.

Supports environment-based flags, dynamic updates, and monitoring.
"""

import os
import json
from enum import Enum
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ExecutionImplementation(Enum):
    """Available execution implementations."""
    BINANCE_V1 = "binance_v1"
    BINANCE_V2 = "binance_v2"
    PAPER = "paper"


class Environment(Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    TESTNET = "testnet"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class FeatureFlag:
    """Represents a feature flag configuration."""
    name: str
    value: Any
    environment: Environment
    enabled: bool = True
    rollout_percentage: float = 100.0
    allowed_users: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def is_enabled_for_user(self, user_id: Optional[str] = None) -> bool:
        """Check if flag is enabled for specific user."""
        if not self.enabled:
            return False
        
        if self.allowed_users and user_id:
            return user_id in self.allowed_users
        
        if user_id and self.rollout_percentage < 100:
            # Simple hash-based rollout
            hash_value = hash(f"{self.name}:{user_id}") % 100
            return hash_value < self.rollout_percentage
        
        return self.rollout_percentage > 0


class FeatureFlagManager:
    """Manages feature flags across the application."""
    
    def __init__(self, environment: Optional[str] = None, config_path: Optional[str] = None):
        self.environment = Environment(environment or os.getenv("ENVIRONMENT", "development"))
        self.config_path = Path(config_path or os.getenv("FEATURE_FLAGS_CONFIG", "config/feature_flags.json"))
        self.flags: Dict[str, FeatureFlag] = {}
        self._listeners: List[callable] = []
        self._load_flags()
        self._setup_defaults()
    
    def _load_flags(self):
        """Load feature flags from configuration file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    
                for flag_name, flag_config in config.get("flags", {}).items():
                    env_config = flag_config.get(self.environment.value, {})
                    if env_config:
                        self.flags[flag_name] = FeatureFlag(
                            name=flag_name,
                            value=env_config.get("value"),
                            environment=self.environment,
                            enabled=env_config.get("enabled", True),
                            rollout_percentage=env_config.get("rollout_percentage", 100.0),
                            allowed_users=set(env_config.get("allowed_users", [])),
                            metadata=env_config.get("metadata", {})
                        )
                
                logger.info(f"Loaded {len(self.flags)} feature flags for {self.environment.value}")
                
            except Exception as e:
                logger.error(f"Failed to load feature flags: {e}")
    
    def _setup_defaults(self):
        """Setup default feature flags if not configured."""
        defaults = {
            "EXECUTION_IMPL": {
                Environment.DEVELOPMENT: ExecutionImplementation.PAPER,
                Environment.TESTNET: ExecutionImplementation.BINANCE_V2,
                Environment.STAGING: ExecutionImplementation.BINANCE_V2,
                Environment.PRODUCTION: ExecutionImplementation.BINANCE_V1,
            },
            "ENABLE_RETRY_IMPROVEMENTS": {
                Environment.DEVELOPMENT: True,
                Environment.TESTNET: True,
                Environment.STAGING: True,
                Environment.PRODUCTION: False,
            },
            "USE_PRECISION_MAP": {
                Environment.DEVELOPMENT: True,
                Environment.TESTNET: True,
                Environment.STAGING: True,
                Environment.PRODUCTION: False,
            },
            "MAX_RETRY_ATTEMPTS": {
                Environment.DEVELOPMENT: 3,
                Environment.TESTNET: 5,
                Environment.STAGING: 5,
                Environment.PRODUCTION: 3,
            }
        }
        
        for flag_name, env_values in defaults.items():
            if flag_name not in self.flags:
                value = env_values.get(self.environment, None)
                if value is not None:
                    self.flags[flag_name] = FeatureFlag(
                        name=flag_name,
                        value=value.value if isinstance(value, Enum) else value,
                        environment=self.environment,
                        enabled=True
                    )
    
    def get(self, flag_name: str, default: Any = None, user_id: Optional[str] = None) -> Any:
        """Get feature flag value."""
        flag = self.flags.get(flag_name)
        
        if not flag:
            logger.warning(f"Feature flag '{flag_name}' not found, using default: {default}")
            return default
        
        if not flag.is_enabled_for_user(user_id):
            return default
        
        return flag.value
    
    def set(self, flag_name: str, value: Any, notify: bool = True):
        """Update feature flag value."""
        if flag_name in self.flags:
            old_value = self.flags[flag_name].value
            self.flags[flag_name].value = value
            self.flags[flag_name].updated_at = datetime.now()
            
            logger.info(f"Updated feature flag '{flag_name}': {old_value} -> {value}")
            
            if notify:
                self._notify_listeners(flag_name, old_value, value)
        else:
            self.flags[flag_name] = FeatureFlag(
                name=flag_name,
                value=value,
                environment=self.environment
            )
            
            if notify:
                self._notify_listeners(flag_name, None, value)
    
    def enable(self, flag_name: str, rollout_percentage: float = 100.0):
        """Enable a feature flag with optional gradual rollout."""
        if flag_name in self.flags:
            self.flags[flag_name].enabled = True
            self.flags[flag_name].rollout_percentage = rollout_percentage
            self.flags[flag_name].updated_at = datetime.now()
            logger.info(f"Enabled feature flag '{flag_name}' with {rollout_percentage}% rollout")
    
    def disable(self, flag_name: str):
        """Disable a feature flag."""
        if flag_name in self.flags:
            self.flags[flag_name].enabled = False
            self.flags[flag_name].updated_at = datetime.now()
            logger.info(f"Disabled feature flag '{flag_name}'")
    
    def add_listener(self, callback: callable):
        """Add listener for flag changes."""
        self._listeners.append(callback)
    
    def _notify_listeners(self, flag_name: str, old_value: Any, new_value: Any):
        """Notify listeners of flag changes."""
        for listener in self._listeners:
            try:
                listener(flag_name, old_value, new_value)
            except Exception as e:
                logger.error(f"Error notifying listener: {e}")
    
    def get_execution_impl(self, user_id: Optional[str] = None) -> ExecutionImplementation:
        """Get current execution implementation."""
        value = self.get("EXECUTION_IMPL", ExecutionImplementation.PAPER.value, user_id)
        
        # Handle string values
        if isinstance(value, str):
            try:
                return ExecutionImplementation(value)
            except ValueError:
                logger.error(f"Invalid execution implementation: {value}")
                return ExecutionImplementation.PAPER
        
        return value
    
    def is_v2_enabled(self, user_id: Optional[str] = None) -> bool:
        """Check if v2 implementation is enabled."""
        impl = self.get_execution_impl(user_id)
        return impl == ExecutionImplementation.BINANCE_V2
    
    def promote_to_production(self, flag_name: str):
        """Promote a feature flag to production."""
        if self.environment != Environment.PRODUCTION:
            logger.warning(f"Cannot promote to production from {self.environment.value}")
            return
        
        if flag_name == "EXECUTION_IMPL":
            # Special handling for execution implementation
            current = self.get(flag_name)
            if current == ExecutionImplementation.BINANCE_V1.value:
                # Gradual rollout to v2
                self.set(flag_name, ExecutionImplementation.BINANCE_V2.value)
                self.enable(flag_name, rollout_percentage=10.0)  # Start with 10%
                logger.info("Started gradual rollout of binance_v2 to production (10%)")
    
    def rollback(self, flag_name: str):
        """Rollback a feature flag to previous value."""
        if flag_name == "EXECUTION_IMPL":
            current = self.get(flag_name)
            if current == ExecutionImplementation.BINANCE_V2.value:
                self.set(flag_name, ExecutionImplementation.BINANCE_V1.value)
                logger.warning(f"Rolled back {flag_name} to binance_v1")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of all feature flags."""
        return {
            "environment": self.environment.value,
            "flags": {
                name: {
                    "value": flag.value.value if isinstance(flag.value, Enum) else flag.value,
                    "enabled": flag.enabled,
                    "rollout_percentage": flag.rollout_percentage,
                    "updated_at": flag.updated_at.isoformat()
                }
                for name, flag in self.flags.items()
            }
        }
    
    def save_config(self):
        """Save current configuration to file."""
        config = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "flags": {}
        }
        
        for flag_name, flag in self.flags.items():
            if flag_name not in config["flags"]:
                config["flags"][flag_name] = {}
            
            config["flags"][flag_name][self.environment.value] = {
                "value": flag.value.value if isinstance(flag.value, Enum) else flag.value,
                "enabled": flag.enabled,
                "rollout_percentage": flag.rollout_percentage,
                "allowed_users": list(flag.allowed_users),
                "metadata": flag.metadata
            }
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Saved feature flag configuration to {self.config_path}")


# Global instance
_feature_flags: Optional[FeatureFlagManager] = None


def get_feature_flags() -> FeatureFlagManager:
    """Get global feature flag manager instance."""
    global _feature_flags
    if _feature_flags is None:
        _feature_flags = FeatureFlagManager()
    return _feature_flags


def get_execution_impl() -> ExecutionImplementation:
    """Convenience function to get execution implementation."""
    return get_feature_flags().get_execution_impl()