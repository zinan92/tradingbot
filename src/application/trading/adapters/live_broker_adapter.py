"""
Live Broker Adapter

Provides a unified interface for different broker implementations,
abstracting broker-specific details from the trading service.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID

from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.trading.entities.position import Position
from src.infrastructure.brokers.binance_futures_broker import BinanceFuturesBroker
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)


class BrokerType(Enum):
    """Supported broker types"""
    BINANCE_FUTURES = "BINANCE_FUTURES"
    BINANCE_SPOT = "BINANCE_SPOT"
    MOCK = "MOCK"


@dataclass
class MarketData:
    """Market data snapshot"""
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume_24h: Decimal
    timestamp: datetime


@dataclass
class AccountInfo:
    """Account information"""
    total_balance: Decimal
    available_balance: Decimal
    margin_balance: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    margin_ratio: Optional[Decimal] = None


class IBrokerAdapter(ABC):
    """
    Abstract broker adapter interface.
    
    Defines the contract that all broker adapters must implement.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to broker"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker"""
        pass
    
    @abstractmethod
    async def submit_order(self, order: Order) -> str:
        """
        Submit order to broker.
        
        Args:
            order: Order to submit
            
        Returns:
            Broker order ID
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """
        Cancel order.
        
        Args:
            broker_order_id: Broker's order ID
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        broker_order_id: str,
        new_quantity: Optional[int] = None,
        new_price: Optional[Decimal] = None
    ) -> bool:
        """
        Modify existing order.
        
        Args:
            broker_order_id: Broker's order ID
            new_quantity: New quantity (optional)
            new_price: New price (optional)
            
        Returns:
            True if modified successfully
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """
        Get order status.
        
        Args:
            broker_order_id: Broker's order ID
            
        Returns:
            Order status
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of open positions
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position or None
        """
        pass
    
    @abstractmethod
    async def close_position(self, symbol: str) -> bool:
        """
        Close position for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            True if closed successfully
        """
        pass
    
    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """
        Get current market data.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Market data snapshot
        """
        pass
    
    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """
        Get account information.
        
        Returns:
            Account information
        """
        pass
    
    @abstractmethod
    async def subscribe_market_data(
        self,
        symbols: List[str],
        callback: Callable[[MarketData], None]
    ) -> None:
        """
        Subscribe to market data updates.
        
        Args:
            symbols: List of symbols to subscribe
            callback: Callback for market updates
        """
        pass
    
    @abstractmethod
    async def subscribe_order_updates(
        self,
        callback: Callable[[Dict], None]
    ) -> None:
        """
        Subscribe to order updates.
        
        Args:
            callback: Callback for order updates
        """
        pass


class BinanceFuturesAdapter(IBrokerAdapter):
    """
    Adapter for Binance Futures broker.
    
    Wraps the BinanceFuturesBroker to provide a unified interface.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        event_bus: Optional[InMemoryEventBus] = None
    ):
        """
        Initialize Binance Futures adapter.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet if True
            event_bus: Event bus for publishing events
        """
        self.broker = BinanceFuturesBroker(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            event_bus=event_bus
        )
        self._market_data_callbacks = []
        self._order_update_callbacks = []
        
        logger.info(f"BinanceFuturesAdapter initialized ({'testnet' if testnet else 'mainnet'})")
    
    async def connect(self) -> None:
        """Connect to Binance"""
        await self.broker.connect()
        logger.info("Connected to Binance Futures")
    
    async def disconnect(self) -> None:
        """Disconnect from Binance"""
        await self.broker.disconnect()
        logger.info("Disconnected from Binance Futures")
    
    async def submit_order(self, order: Order) -> str:
        """Submit order to Binance"""
        try:
            broker_order_id = await self.broker.submit_order(order)
            logger.info(f"Order submitted to Binance: {order.id} -> {broker_order_id}")
            return broker_order_id
            
        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            raise
    
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel order on Binance"""
        try:
            result = await self.broker.cancel_order(broker_order_id)
            logger.info(f"Order cancelled on Binance: {broker_order_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to cancel order {broker_order_id}: {e}")
            return False
    
    async def modify_order(
        self,
        broker_order_id: str,
        new_quantity: Optional[int] = None,
        new_price: Optional[Decimal] = None
    ) -> bool:
        """
        Modify order on Binance.
        
        Note: Binance doesn't support direct order modification,
        so this cancels and replaces the order.
        """
        try:
            # Get original order details
            order_info = await self.broker.get_order(broker_order_id)
            if not order_info:
                return False
            
            # Cancel original order
            if not await self.cancel_order(broker_order_id):
                return False
            
            # Create new order with modifications
            # This would need the original Order object
            # In production, store order mapping
            
            logger.warning("Order modification not fully implemented")
            return False
            
        except Exception as e:
            logger.error(f"Failed to modify order {broker_order_id}: {e}")
            return False
    
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """Get order status from Binance"""
        try:
            order_info = await self.broker.get_order(broker_order_id)
            
            if not order_info:
                return OrderStatus.REJECTED
            
            # Map Binance status to OrderStatus
            status_map = {
                "NEW": OrderStatus.PENDING,
                "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
                "FILLED": OrderStatus.FILLED,
                "CANCELED": OrderStatus.CANCELLED,
                "REJECTED": OrderStatus.REJECTED,
                "EXPIRED": OrderStatus.CANCELLED
            }
            
            return status_map.get(order_info["status"], OrderStatus.REJECTED)
            
        except Exception as e:
            logger.error(f"Failed to get order status for {broker_order_id}: {e}")
            return OrderStatus.REJECTED
    
    async def get_positions(self) -> List[Position]:
        """Get all open positions from Binance"""
        try:
            positions_data = await self.broker.get_positions()
            
            # Convert to Position objects
            positions = []
            for pos_data in positions_data:
                if float(pos_data["positionAmt"]) != 0:
                    # Create Position object from Binance data
                    # This would need proper mapping
                    pass
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol from Binance"""
        try:
            position_data = await self.broker.get_position(symbol)
            
            if not position_data or float(position_data["positionAmt"]) == 0:
                return None
            
            # Convert to Position object
            # This would need proper mapping
            return None
            
        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None
    
    async def close_position(self, symbol: str) -> bool:
        """Close position on Binance"""
        try:
            position = await self.get_position(symbol)
            if not position:
                logger.warning(f"No position to close for {symbol}")
                return True
            
            # Create market order to close position
            close_order = Order.create(
                symbol=symbol,
                quantity=abs(position.quantity.value),
                order_type="MARKET",
                side="SELL" if position.side.value == "LONG" else "BUY",
                portfolio_id=position.portfolio_id,
                reduce_only=True
            )
            
            broker_order_id = await self.submit_order(close_order)
            
            logger.info(f"Position close order submitted for {symbol}: {broker_order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {e}")
            return False
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get market data from Binance"""
        try:
            ticker = await self.broker.get_ticker(symbol)
            
            return MarketData(
                symbol=symbol,
                bid=Decimal(ticker["bidPrice"]),
                ask=Decimal(ticker["askPrice"]),
                last=Decimal(ticker["lastPrice"]),
                volume_24h=Decimal(ticker["volume"]),
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            raise
    
    async def get_account_info(self) -> AccountInfo:
        """Get account info from Binance"""
        try:
            account = await self.broker.get_account()
            
            return AccountInfo(
                total_balance=Decimal(account["totalWalletBalance"]),
                available_balance=Decimal(account["availableBalance"]),
                margin_balance=Decimal(account["totalMarginBalance"]),
                unrealized_pnl=Decimal(account["totalUnrealizedProfit"]),
                realized_pnl=Decimal(account.get("totalRealizedProfit", "0")),
                margin_ratio=Decimal(account.get("totalMaintMargin", "0")) / 
                           Decimal(account["totalMarginBalance"]) 
                           if float(account["totalMarginBalance"]) > 0 else None
            )
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            raise
    
    async def subscribe_market_data(
        self,
        symbols: List[str],
        callback: Callable[[MarketData], None]
    ) -> None:
        """Subscribe to market data updates"""
        self._market_data_callbacks.append(callback)
        
        # Set up WebSocket subscription
        for symbol in symbols:
            await self.broker.subscribe_ticker(symbol, self._handle_market_update)
        
        logger.info(f"Subscribed to market data for {len(symbols)} symbols")
    
    async def subscribe_order_updates(
        self,
        callback: Callable[[Dict], None]
    ) -> None:
        """Subscribe to order updates"""
        self._order_update_callbacks.append(callback)
        
        # Set up WebSocket subscription
        await self.broker.subscribe_user_data(self._handle_order_update)
        
        logger.info("Subscribed to order updates")
    
    def _handle_market_update(self, data: Dict) -> None:
        """Handle market data update from WebSocket"""
        try:
            market_data = MarketData(
                symbol=data["s"],
                bid=Decimal(data["b"]),
                ask=Decimal(data["a"]),
                last=Decimal(data["c"]),
                volume_24h=Decimal(data["v"]),
                timestamp=datetime.utcnow()
            )
            
            for callback in self._market_data_callbacks:
                callback(market_data)
                
        except Exception as e:
            logger.error(f"Error handling market update: {e}")
    
    def _handle_order_update(self, data: Dict) -> None:
        """Handle order update from WebSocket"""
        try:
            for callback in self._order_update_callbacks:
                callback(data)
                
        except Exception as e:
            logger.error(f"Error handling order update: {e}")


class LiveBrokerAdapter:
    """
    Factory and manager for broker adapters.
    
    Provides broker selection and unified interface.
    """
    
    def __init__(self, broker_type: BrokerType, config: Dict[str, Any]):
        """
        Initialize broker adapter.
        
        Args:
            broker_type: Type of broker to use
            config: Broker configuration
        """
        self.broker_type = broker_type
        self.config = config
        self.adapter: Optional[IBrokerAdapter] = None
        
        logger.info(f"LiveBrokerAdapter initialized for {broker_type.value}")
    
    def create_adapter(self, event_bus: Optional[InMemoryEventBus] = None) -> IBrokerAdapter:
        """
        Create broker adapter instance.
        
        Args:
            event_bus: Event bus for publishing events
            
        Returns:
            Broker adapter instance
        """
        if self.broker_type == BrokerType.BINANCE_FUTURES:
            self.adapter = BinanceFuturesAdapter(
                api_key=self.config["api_key"],
                api_secret=self.config["api_secret"],
                testnet=self.config.get("testnet", True),
                event_bus=event_bus
            )
        elif self.broker_type == BrokerType.MOCK:
            # Would implement MockBrokerAdapter for testing
            raise NotImplementedError("Mock broker not implemented")
        else:
            raise ValueError(f"Unsupported broker type: {self.broker_type}")
        
        return self.adapter
    
    async def connect(self) -> None:
        """Connect to broker"""
        if not self.adapter:
            raise RuntimeError("Adapter not created")
        
        await self.adapter.connect()
    
    async def disconnect(self) -> None:
        """Disconnect from broker"""
        if self.adapter:
            await self.adapter.disconnect()
    
    def get_adapter(self) -> IBrokerAdapter:
        """Get broker adapter instance"""
        if not self.adapter:
            raise RuntimeError("Adapter not created")
        
        return self.adapter