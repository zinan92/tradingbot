"""
Execution Port

Abstract interface for order execution and position management.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime


class ExecutionPort(ABC):
    """Abstract interface for order execution and position management"""
    
    @abstractmethod
    async def submit(self, order: Dict[str, Any]) -> str:
        """
        Submit an order for execution
        
        Args:
            order: Order details including:
                - symbol: Trading pair symbol
                - side: 'buy' or 'sell'
                - type: Order type (market, limit, stop, etc.)
                - quantity: Order quantity
                - price: Limit price (for limit orders)
                - stop_price: Stop price (for stop orders)
                
        Returns:
            Order ID for tracking
        """
        pass
    
    @abstractmethod
    async def cancel(self, order_id: str) -> bool:
        """
        Cancel a pending order
        
        Args:
            order_id: Unique order identifier
            
        Returns:
            True if order was cancelled successfully
        """
        pass
    
    @abstractmethod
    async def positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions
        
        Returns:
            List of position dictionaries containing:
                - symbol: Trading pair symbol
                - side: Position side (long/short)
                - quantity: Position size
                - entry_price: Average entry price
                - current_price: Current market price
                - unrealized_pnl: Unrealized profit/loss
                - realized_pnl: Realized profit/loss
        """
        pass
    
    @abstractmethod
    async def orders(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders with optional status filter
        
        Args:
            status: Optional status filter (pending, filled, cancelled)
            
        Returns:
            List of order dictionaries
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific order
        
        Args:
            order_id: Unique order identifier
            
        Returns:
            Order details if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get position for a specific symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Position details if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        modifications: Dict[str, Any]
    ) -> bool:
        """
        Modify a pending order
        
        Args:
            order_id: Order to modify
            modifications: Fields to update (price, quantity, etc.)
            
        Returns:
            True if order was modified successfully
        """
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> Dict[str, Decimal]:
        """
        Get account balance information
        
        Returns:
            Dictionary with balance details (available, locked, total)
        """
        pass