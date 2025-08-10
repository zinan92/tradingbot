"""
Strategy registry port interface.

Defines the contract for strategy registration and management.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from src.domain.ports.backtest_port import StrategyPort


class StrategyRegistryPort(ABC):
    """
    Port interface for strategy registry.
    
    All strategy registry implementations must implement this interface.
    """
    
    @abstractmethod
    def register(
        self,
        name: str,
        strategy_class: Type[StrategyPort],
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Register a strategy.
        
        Args:
            name: Strategy name
            strategy_class: Strategy class
            description: Optional description
            parameters: Default parameters
            
        Returns:
            True if registered successfully
        """
        pass
    
    @abstractmethod
    def unregister(self, name: str) -> bool:
        """
        Unregister a strategy.
        
        Args:
            name: Strategy name
            
        Returns:
            True if unregistered successfully
        """
        pass
    
    @abstractmethod
    def get(self, name: str) -> Optional[Type[StrategyPort]]:
        """
        Get a strategy class by name.
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy class or None if not found
        """
        pass
    
    @abstractmethod
    def create_instance(
        self,
        name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategyPort]:
        """
        Create a strategy instance.
        
        Args:
            name: Strategy name
            parameters: Strategy parameters
            
        Returns:
            Strategy instance or None if not found
        """
        pass
    
    @abstractmethod
    def list_strategies(self) -> List[Dict[str, Any]]:
        """
        List all registered strategies.
        
        Returns:
            List of strategy information
        """
        pass
    
    @abstractmethod
    def get_strategy_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a strategy.
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy information or None if not found
        """
        pass
    
    @abstractmethod
    def validate_parameters(
        self,
        name: str,
        parameters: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate strategy parameters.
        
        Args:
            name: Strategy name
            parameters: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def get_default_parameters(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get default parameters for a strategy.
        
        Args:
            name: Strategy name
            
        Returns:
            Default parameters or None if not found
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all registered strategies."""
        pass