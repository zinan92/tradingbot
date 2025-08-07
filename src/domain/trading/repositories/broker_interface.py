from abc import ABC, abstractmethod
from typing import NewType
from src.domain.trading.aggregates.order import Order

# Type alias for broker order ID
BrokerOrderId = NewType('BrokerOrderId', str)


class IBroker(ABC):
    """
    Interface for broker services
    
    Defines the contract for broker implementations to submit
    and manage orders with external trading systems.
    """
    
    @abstractmethod
    async def submit_order(self, order: Order) -> BrokerOrderId:
        """
        Submit an order to the broker.
        
        Args:
            order: The order to submit
            
        Returns:
            BrokerOrderId: The broker's order identifier
            
        Raises:
            BrokerConnectionError: If unable to connect to broker
            BrokerValidationError: If order validation fails
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order with broker.
        Returns True if cancellation request accepted.
        Note: This doesn't mean order is cancelled, just that request was received.
        
        Args:
            order_id: The broker's order identifier
            
        Returns:
            bool: True if cancellation request was accepted, False otherwise
            
        Raises:
            BrokerConnectionError: If unable to connect to broker
        """
        pass