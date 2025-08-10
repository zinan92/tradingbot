"""
WebSocket port interface.

Defines the contract for WebSocket connections.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
import asyncio


class WebSocketPort(ABC):
    """
    Port interface for WebSocket connections.
    
    All WebSocket implementations must implement this interface.
    """
    
    @abstractmethod
    async def connect(self, url: str, **kwargs) -> bool:
        """
        Connect to WebSocket server.
        
        Args:
            url: WebSocket URL
            **kwargs: Additional connection parameters
            
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from WebSocket server.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to WebSocket.
        
        Returns:
            True if connected
        """
        pass
    
    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> bool:
        """
        Send a message through WebSocket.
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    async def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Receive a message from WebSocket.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Received message or None if timeout
        """
        pass
    
    @abstractmethod
    def subscribe(
        self,
        channel: str,
        callback: Callable[[Dict[str, Any]], None]
    ) -> bool:
        """
        Subscribe to a WebSocket channel.
        
        Args:
            channel: Channel name
            callback: Callback for messages
            
        Returns:
            True if subscribed successfully
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, channel: str) -> bool:
        """
        Unsubscribe from a WebSocket channel.
        
        Args:
            channel: Channel name
            
        Returns:
            True if unsubscribed successfully
        """
        pass
    
    @abstractmethod
    async def ping(self) -> bool:
        """
        Send ping to keep connection alive.
        
        Returns:
            True if ping successful
        """
        pass
    
    @abstractmethod
    def on_message(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Set callback for all incoming messages.
        
        Args:
            callback: Callback function
        """
        pass
    
    @abstractmethod
    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """
        Set callback for errors.
        
        Args:
            callback: Error callback function
        """
        pass
    
    @abstractmethod
    def on_close(self, callback: Callable[[], None]) -> None:
        """
        Set callback for connection close.
        
        Args:
            callback: Close callback function
        """
        pass
    
    @abstractmethod
    async def start_heartbeat(self, interval: float = 30.0) -> None:
        """
        Start heartbeat to keep connection alive.
        
        Args:
            interval: Heartbeat interval in seconds
        """
        pass
    
    @abstractmethod
    async def stop_heartbeat(self) -> None:
        """Stop heartbeat."""
        pass