"""
Strategy Registry Port

Abstract interface for strategy registry operations.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from enum import Enum


class StrategyStatus(Enum):
    """Strategy execution status"""
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class StrategyRegistryPort(ABC):
    """Abstract interface for strategy registry operations"""
    
    @abstractmethod
    async def list(self) -> List[Dict[str, Any]]:
        """
        List all registered strategies
        
        Returns:
            List of strategy configurations with metadata
        """
        pass
    
    @abstractmethod
    async def get(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific strategy by ID
        
        Args:
            strategy_id: Unique strategy identifier
            
        Returns:
            Strategy configuration if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def publish(self, config: Dict[str, Any]) -> str:
        """
        Publish a new strategy configuration
        
        Args:
            config: Strategy configuration dictionary
            
        Returns:
            Unique identifier for the published strategy
        """
        pass
    
    @abstractmethod
    async def set_status(
        self,
        strategy_id: str,
        status: StrategyStatus
    ) -> bool:
        """
        Set the execution status of a strategy
        
        Args:
            strategy_id: Unique strategy identifier
            status: New strategy status
            
        Returns:
            True if status was updated successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def update_config(
        self,
        strategy_id: str,
        config: Dict[str, Any]
    ) -> bool:
        """
        Update strategy configuration
        
        Args:
            strategy_id: Unique strategy identifier
            config: Updated configuration
            
        Returns:
            True if configuration was updated successfully
        """
        pass
    
    @abstractmethod
    async def delete(self, strategy_id: str) -> bool:
        """
        Delete a strategy from the registry
        
        Args:
            strategy_id: Unique strategy identifier
            
        Returns:
            True if strategy was deleted successfully
        """
        pass