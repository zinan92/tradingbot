"""
Database port interface.

Defines the contract for database operations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar
from datetime import datetime

T = TypeVar('T')


class DatabasePort(ABC):
    """
    Port interface for database operations.
    
    All database implementations must implement this interface.
    """
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to database.
        
        Returns:
            True if connected successfully
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from database.
        
        Returns:
            True if disconnected successfully
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to database.
        
        Returns:
            True if connected
        """
        pass
    
    @abstractmethod
    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a database query.
        
        Args:
            query: SQL query or command
            params: Query parameters
            
        Returns:
            Query result
        """
        pass
    
    @abstractmethod
    async def fetch_one(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch one row from database.
        
        Args:
            query: SELECT query
            params: Query parameters
            
        Returns:
            Single row as dictionary or None
        """
        pass
    
    @abstractmethod
    async def fetch_all(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all rows from database.
        
        Args:
            query: SELECT query
            params: Query parameters
            
        Returns:
            List of rows as dictionaries
        """
        pass
    
    @abstractmethod
    async def insert(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> Any:
        """
        Insert data into table.
        
        Args:
            table: Table name
            data: Data to insert
            
        Returns:
            Inserted ID or result
        """
        pass
    
    @abstractmethod
    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        conditions: Dict[str, Any]
    ) -> int:
        """
        Update data in table.
        
        Args:
            table: Table name
            data: Data to update
            conditions: WHERE conditions
            
        Returns:
            Number of rows updated
        """
        pass
    
    @abstractmethod
    async def delete(
        self,
        table: str,
        conditions: Dict[str, Any]
    ) -> int:
        """
        Delete data from table.
        
        Args:
            table: Table name
            conditions: WHERE conditions
            
        Returns:
            Number of rows deleted
        """
        pass
    
    @abstractmethod
    async def transaction_begin(self) -> None:
        """Begin a database transaction."""
        pass
    
    @abstractmethod
    async def transaction_commit(self) -> None:
        """Commit current transaction."""
        pass
    
    @abstractmethod
    async def transaction_rollback(self) -> None:
        """Rollback current transaction."""
        pass


class RepositoryPort(ABC):
    """
    Base repository port interface.
    
    All repositories must implement this interface.
    """
    
    @abstractmethod
    async def save(self, entity: T) -> T:
        """
        Save an entity.
        
        Args:
            entity: Entity to save
            
        Returns:
            Saved entity
        """
        pass
    
    @abstractmethod
    async def find_by_id(self, entity_id: str) -> Optional[T]:
        """
        Find entity by ID.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity or None
        """
        pass
    
    @abstractmethod
    async def find_all(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[T]:
        """
        Find all entities.
        
        Args:
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of entities
        """
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """
        Delete an entity.
        
        Args:
            entity_id: Entity ID to delete
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    async def exists(self, entity_id: str) -> bool:
        """
        Check if entity exists.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            True if entity exists
        """
        pass


class BacktestRepositoryPort(RepositoryPort):
    """Repository port for backtest results."""
    
    @abstractmethod
    async def find_by_strategy(self, strategy_name: str) -> List[Any]:
        """
        Find backtests by strategy name.
        
        Args:
            strategy_name: Strategy name
            
        Returns:
            List of backtest results
        """
        pass
    
    @abstractmethod
    async def find_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Any]:
        """
        Find backtests by date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of backtest results
        """
        pass