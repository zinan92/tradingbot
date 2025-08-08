import asyncio
import logging
from typing import Dict, Optional, List, Any
from decimal import Decimal
from datetime import datetime
import json

from binance import AsyncClient, BinanceSocketManager
from binance.enums import (
    SIDE_BUY, SIDE_SELL,
    ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET,
    TIME_IN_FORCE_GTC, TIME_IN_FORCE_IOC, TIME_IN_FORCE_FOK,
    FUTURE_ORDER_TYPE_LIMIT, FUTURE_ORDER_TYPE_MARKET,
    FUTURE_ORDER_TYPE_STOP, FUTURE_ORDER_TYPE_STOP_MARKET,
    FUTURE_ORDER_TYPE_TAKE_PROFIT, FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET
)
from binance.exceptions import BinanceAPIException

from src.domain.trading.aggregates.order import Order, OrderStatus
from src.domain.trading.repositories.broker_interface import IBroker, BrokerOrderId
from src.domain.trading.value_objects.side import PositionSide
from src.domain.trading.value_objects.leverage import Leverage
from src.domain.trading.events.order_events import (
    OrderFilled, OrderRejected, OrderPartiallyFilled, OrderCancelledByBroker
)

logger = logging.getLogger(__name__)


class BinanceFuturesBroker(IBroker):
    """
    Binance Futures broker implementation.
    
    Handles order submission, cancellation, and real-time updates
    via WebSocket connections for Binance Futures trading.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        event_bus=None
    ):
        """
        Initialize Binance Futures broker.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet if True, mainnet if False
            event_bus: Optional event bus for publishing domain events
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.event_bus = event_bus
        
        self.client: Optional[AsyncClient] = None
        self.socket_manager: Optional[BinanceSocketManager] = None
        self.user_socket = None
        
        # Track orders and positions
        self.orders: Dict[str, Dict] = {}
        self.positions: Dict[str, Dict] = {}
        self.account_info: Dict = {}
        
        # WebSocket management
        self._ws_task = None
        self._reconnect_delay = 5
        self._max_reconnect_delay = 60
        
        logger.info(f"BinanceFuturesBroker initialized (testnet={testnet})")
    
    async def connect(self):
        """Establish connection to Binance."""
        try:
            # Create async client
            if self.testnet:
                self.client = await AsyncClient.create(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    testnet=True
                )
            else:
                self.client = await AsyncClient.create(
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )
            
            # Initialize socket manager
            self.socket_manager = BinanceSocketManager(self.client)
            
            # Start user data stream
            await self._start_user_stream()
            
            # Fetch initial account info
            await self._update_account_info()
            
            logger.info("Successfully connected to Binance Futures")
            
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Binance."""
        try:
            if self._ws_task:
                self._ws_task.cancel()
                try:
                    await self._ws_task
                except asyncio.CancelledError:
                    pass
            
            if self.user_socket:
                await self.user_socket.__aexit__(None, None, None)
            
            if self.client:
                await self.client.close_connection()
            
            logger.info("Disconnected from Binance Futures")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def submit_order(self, order: Order) -> BrokerOrderId:
        """
        Submit an order to Binance Futures.
        
        Args:
            order: The order to submit
            
        Returns:
            BrokerOrderId: Binance's order identifier
            
        Raises:
            BrokerConnectionError: If unable to connect
            BrokerValidationError: If order validation fails
        """
        if not self.client:
            await self.connect()
        
        try:
            # Map order to Binance parameters
            params = self._map_order_to_binance(order)
            
            # Submit order to Binance Futures
            result = await self.client.futures_create_order(**params)
            
            # Extract Binance order ID
            binance_order_id = str(result['orderId'])
            broker_order_id = BrokerOrderId(f"BINANCE-{binance_order_id}")
            
            # Store order info
            self.orders[broker_order_id] = {
                'order_id': str(order.id),
                'binance_id': binance_order_id,
                'symbol': order.symbol,
                'quantity': order.quantity,
                'side': params['side'],
                'type': params['type'],
                'status': result['status'],
                'created_at': datetime.utcnow()
            }
            
            logger.info(
                f"Order {order.id} submitted to Binance as {binance_order_id}. "
                f"Status: {result['status']}"
            )
            
            return broker_order_id
            
        except BinanceAPIException as e:
            logger.error(f"Binance API error submitting order: {e}")
            
            # Publish OrderRejected event
            if self.event_bus:
                event = OrderRejected(
                    order_id=order.id,
                    reason=str(e),
                    symbol=order.symbol,
                    quantity=order.quantity
                )
                await self._publish_event(event)
            
            raise BrokerValidationError(f"Order rejected by Binance: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error submitting order: {e}")
            raise BrokerConnectionError(f"Failed to submit order: {e}")
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order on Binance Futures.
        
        Args:
            order_id: The broker's order identifier
            
        Returns:
            bool: True if cancellation request was accepted
        """
        if not self.client:
            await self.connect()
        
        try:
            # Get order info
            if order_id not in self.orders:
                logger.warning(f"Order {order_id} not found")
                return False
            
            order_info = self.orders[order_id]
            symbol = order_info['symbol']
            binance_id = order_info['binance_id']
            
            # Cancel order on Binance
            result = await self.client.futures_cancel_order(
                symbol=symbol,
                orderId=binance_id
            )
            
            # Update local order status
            order_info['status'] = 'CANCELED'
            
            logger.info(f"Order {order_id} cancellation requested. Result: {result}")
            
            return True
            
        except BinanceAPIException as e:
            if e.code == -2011:  # Order not found or already canceled
                logger.info(f"Order {order_id} already canceled or not found")
                return True
            
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error canceling order: {e}")
            return False
    
    async def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current position for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position information or None
        """
        if not self.client:
            await self.connect()
        
        try:
            positions = await self.client.futures_position_information(symbol=symbol)
            
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    return {
                        'symbol': pos['symbol'],
                        'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                        'quantity': abs(float(pos['positionAmt'])),
                        'entry_price': float(pos['entryPrice']),
                        'mark_price': float(pos['markPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit']),
                        'leverage': int(pos['leverage']),
                        'margin_type': pos['marginType']
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a symbol.
        
        Args:
            symbol: Trading symbol
            leverage: Leverage value (1-125)
            
        Returns:
            True if successful
        """
        if not self.client:
            await self.connect()
        
        try:
            result = await self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            
            logger.info(f"Leverage set to {leverage}x for {symbol}")
            return True
            
        except BinanceAPIException as e:
            logger.error(f"Failed to set leverage: {e}")
            return False
    
    async def set_margin_type(self, symbol: str, margin_type: str) -> bool:
        """
        Set margin type for a symbol.
        
        Args:
            symbol: Trading symbol
            margin_type: "ISOLATED" or "CROSSED"
            
        Returns:
            True if successful
        """
        if not self.client:
            await self.connect()
        
        try:
            result = await self.client.futures_change_margin_type(
                symbol=symbol,
                marginType=margin_type
            )
            
            logger.info(f"Margin type set to {margin_type} for {symbol}")
            return True
            
        except BinanceAPIException as e:
            if e.code == -4046:  # No need to change margin type
                logger.info(f"Margin type already {margin_type} for {symbol}")
                return True
            
            logger.error(f"Failed to set margin type: {e}")
            return False
    
    def _map_order_to_binance(self, order: Order) -> Dict:
        """
        Map domain Order to Binance API parameters.
        
        Args:
            order: Domain order object
            
        Returns:
            Dictionary of Binance API parameters
        """
        params = {
            'symbol': order.symbol,
            'quantity': order.quantity
        }
        
        # Map order type
        order_type_upper = order.order_type.upper()
        if order_type_upper == 'MARKET':
            params['type'] = FUTURE_ORDER_TYPE_MARKET
        elif order_type_upper == 'LIMIT':
            params['type'] = FUTURE_ORDER_TYPE_LIMIT
            params['price'] = str(order.price)
            params['timeInForce'] = TIME_IN_FORCE_GTC
        elif order_type_upper == 'STOP':
            params['type'] = FUTURE_ORDER_TYPE_STOP_MARKET
            params['stopPrice'] = str(order.price)
        else:
            params['type'] = FUTURE_ORDER_TYPE_MARKET
        
        # Determine side based on context
        # This is simplified - in production, you'd track position context
        params['side'] = SIDE_BUY  # Default, should be determined by strategy
        
        return params
    
    async def _start_user_stream(self):
        """Start WebSocket stream for user data updates."""
        try:
            # Start user data stream
            self.user_socket = self.socket_manager.futures_user_socket()
            
            # Start processing messages
            self._ws_task = asyncio.create_task(self._process_user_stream())
            
            logger.info("User data stream started")
            
        except Exception as e:
            logger.error(f"Failed to start user stream: {e}")
            raise
    
    async def _process_user_stream(self):
        """Process messages from user data stream."""
        async with self.user_socket as stream:
            while True:
                try:
                    msg = await stream.recv()
                    await self._handle_user_message(msg)
                    
                except asyncio.CancelledError:
                    break
                    
                except Exception as e:
                    logger.error(f"Error processing user stream: {e}")
                    await asyncio.sleep(self._reconnect_delay)
    
    async def _handle_user_message(self, msg: Dict):
        """
        Handle user data stream messages.
        
        Args:
            msg: WebSocket message
        """
        try:
            event_type = msg.get('e')
            
            if event_type == 'ORDER_TRADE_UPDATE':
                await self._handle_order_update(msg)
                
            elif event_type == 'ACCOUNT_UPDATE':
                await self._handle_account_update(msg)
                
            elif event_type == 'MARGIN_CALL':
                await self._handle_margin_call(msg)
                
        except Exception as e:
            logger.error(f"Error handling user message: {e}")
    
    async def _handle_order_update(self, msg: Dict):
        """Handle order update from WebSocket."""
        try:
            order_data = msg['o']
            binance_order_id = str(order_data['i'])
            broker_order_id = f"BINANCE-{binance_order_id}"
            
            # Get our order info
            if broker_order_id not in self.orders:
                return
            
            order_info = self.orders[broker_order_id]
            order_id = order_info['order_id']
            status = order_data['X']  # Execution status
            
            # Handle different order statuses
            if status == 'FILLED':
                event = OrderFilled(
                    order_id=order_id,
                    symbol=order_data['s'],
                    quantity=int(float(order_data['q'])),
                    fill_price=Decimal(order_data['p']),
                    broker_order_id=broker_order_id
                )
                await self._publish_event(event)
                
            elif status == 'PARTIALLY_FILLED':
                event = OrderPartiallyFilled(
                    order_id=order_id,
                    symbol=order_data['s'],
                    filled_quantity=int(float(order_data['z'])),
                    remaining_quantity=int(float(order_data['q']) - float(order_data['z'])),
                    fill_price=Decimal(order_data['L']),
                    total_filled=int(float(order_data['z'])),
                    broker_order_id=broker_order_id
                )
                await self._publish_event(event)
                
            elif status == 'CANCELED':
                event = OrderCancelledByBroker(
                    order_id=order_id,
                    broker_order_id=broker_order_id,
                    cancelled_at=datetime.utcnow(),
                    reason="Cancelled by Binance"
                )
                await self._publish_event(event)
                
            elif status == 'REJECTED':
                event = OrderRejected(
                    order_id=order_id,
                    reason=order_data.get('r', 'Order rejected'),
                    symbol=order_data['s'],
                    quantity=int(float(order_data['q'])),
                    rejected_by="Binance"
                )
                await self._publish_event(event)
                
        except Exception as e:
            logger.error(f"Error handling order update: {e}")
    
    async def _handle_account_update(self, msg: Dict):
        """Handle account update from WebSocket."""
        try:
            # Update account balances
            for balance in msg.get('a', {}).get('B', []):
                asset = balance['a']
                free = float(balance['f'])
                locked = float(balance['l'])
                
                self.account_info[asset] = {
                    'free': free,
                    'locked': locked,
                    'total': free + locked
                }
            
            # Update positions
            for position in msg.get('a', {}).get('P', []):
                symbol = position['s']
                self.positions[symbol] = {
                    'symbol': symbol,
                    'side': position['ps'],
                    'quantity': abs(float(position['pa'])),
                    'entry_price': float(position['ep']),
                    'unrealized_pnl': float(position['up']),
                    'margin_type': position['mt']
                }
                
        except Exception as e:
            logger.error(f"Error handling account update: {e}")
    
    async def _handle_margin_call(self, msg: Dict):
        """Handle margin call notification."""
        logger.warning(f"MARGIN CALL received: {msg}")
        # TODO: Implement margin call handling
        # Could trigger position reduction or emergency close
    
    async def _update_account_info(self):
        """Fetch and update account information."""
        try:
            account = await self.client.futures_account()
            
            # Update balances
            for asset_info in account['assets']:
                asset = asset_info['asset']
                self.account_info[asset] = {
                    'free': float(asset_info['availableBalance']),
                    'locked': float(asset_info['initialMargin']),
                    'total': float(asset_info['marginBalance'])
                }
            
            # Update positions
            for pos in account['positions']:
                if float(pos['positionAmt']) != 0:
                    symbol = pos['symbol']
                    self.positions[symbol] = {
                        'symbol': symbol,
                        'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                        'quantity': abs(float(pos['positionAmt'])),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unrealizedProfit']),
                        'margin_type': pos['marginType']
                    }
            
            logger.info("Account info updated")
            
        except Exception as e:
            logger.error(f"Failed to update account info: {e}")
    
    async def _publish_event(self, event):
        """Publish domain event."""
        if self.event_bus:
            try:
                if hasattr(self.event_bus, 'publish_async'):
                    await self.event_bus.publish_async(event)
                else:
                    self.event_bus.publish(event)
                    
            except Exception as e:
                logger.error(f"Failed to publish event: {e}")
    
    async def get_account_balance(self) -> Dict[str, float]:
        """Get account balances."""
        if not self.account_info:
            await self._update_account_info()
        
        return {
            asset: info['free']
            for asset, info in self.account_info.items()
            if info['free'] > 0
        }
    
    async def get_all_positions(self) -> List[Dict]:
        """Get all open positions."""
        if not self.client:
            await self.connect()
        
        await self._update_account_info()
        return list(self.positions.values())


# Domain Exceptions
class BrokerError(Exception):
    """Base exception for broker errors."""
    pass


class BrokerConnectionError(BrokerError):
    """Raised when unable to connect to broker."""
    pass


class BrokerValidationError(BrokerError):
    """Raised when order validation fails."""
    pass