"""
Binance Execution Adapter

Implements ExecutionPort for Binance futures trading.
Handles all Binance-specific logic including precision, retries, and mapping.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
import math

from binance.client import AsyncClient
from binance.exceptions import BinanceAPIException
from binance.enums import (
    ORDER_TYPE_MARKET,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_STOP,
    ORDER_TYPE_STOP_MARKET,
    SIDE_BUY,
    SIDE_SELL,
    TIME_IN_FORCE_GTC,
    TIME_IN_FORCE_IOC,
    TIME_IN_FORCE_FOK,
    FUTURE_ORDER_TYPE_LIMIT,
    FUTURE_ORDER_TYPE_MARKET,
    FUTURE_ORDER_TYPE_STOP,
    FUTURE_ORDER_TYPE_STOP_MARKET,
    FUTURE_ORDER_TYPE_TAKE_PROFIT,
    FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET
)

from src.domain.shared.ports import ExecutionPort

logger = logging.getLogger(__name__)


class BinanceExecutionError(Exception):
    """Binance-specific execution error"""
    pass


class InsufficientBalanceError(BinanceExecutionError):
    """Insufficient balance error"""
    pass


class OrderNotFoundError(BinanceExecutionError):
    """Order not found error"""
    pass


class SymbolNotTradableError(BinanceExecutionError):
    """Symbol not tradable error"""
    pass


class BinanceExecutionAdapter(ExecutionPort):
    """
    Binance implementation of ExecutionPort
    
    Handles:
    - Order submission with proper precision
    - Order cancellation with retries
    - Position management
    - Error mapping to domain exceptions
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize Binance execution adapter
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet if True
            max_retries: Maximum number of retries for operations
            retry_delay: Delay between retries in seconds
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client: Optional[AsyncClient] = None
        self._symbol_info_cache: Dict[str, Dict[str, Any]] = {}
        self._connected = False
    
    async def connect(self):
        """Connect to Binance"""
        if not self._connected:
            self.client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            self._connected = True
            logger.info(f"Connected to Binance {'testnet' if self.testnet else 'mainnet'}")
    
    async def disconnect(self):
        """Disconnect from Binance"""
        if self.client and self._connected:
            await self.client.close_connection()
            self._connected = False
            logger.info("Disconnected from Binance")
    
    async def _ensure_connected(self):
        """Ensure connection is established"""
        if not self._connected:
            await self.connect()
    
    async def _get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get symbol trading info with caching
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Symbol information including precision
        """
        if symbol not in self._symbol_info_cache:
            await self._ensure_connected()
            
            try:
                exchange_info = await self.client.futures_exchange_info()
                for s in exchange_info['symbols']:
                    if s['symbol'] == symbol:
                        self._symbol_info_cache[symbol] = {
                            'price_precision': s['pricePrecision'],
                            'quantity_precision': s['quantityPrecision'],
                            'base_precision': s['baseAssetPrecision'],
                            'quote_precision': s['quotePrecision'],
                            'min_qty': Decimal(next(
                                f['minQty'] for f in s['filters']
                                if f['filterType'] == 'LOT_SIZE'
                            )),
                            'max_qty': Decimal(next(
                                f['maxQty'] for f in s['filters']
                                if f['filterType'] == 'LOT_SIZE'
                            )),
                            'step_size': Decimal(next(
                                f['stepSize'] for f in s['filters']
                                if f['filterType'] == 'LOT_SIZE'
                            )),
                            'min_notional': Decimal(next(
                                f['notional'] for f in s['filters']
                                if f['filterType'] == 'MIN_NOTIONAL'
                            )),
                            'status': s['status']
                        }
                        break
                else:
                    raise SymbolNotTradableError(f"Symbol {symbol} not found")
                    
            except BinanceAPIException as e:
                logger.error(f"Failed to get symbol info for {symbol}: {e}")
                raise BinanceExecutionError(f"Failed to get symbol info: {e}")
        
        return self._symbol_info_cache[symbol]
    
    def _round_price(self, price: Decimal, symbol_info: Dict[str, Any]) -> Decimal:
        """
        Round price to symbol's precision
        
        Args:
            price: Price to round
            symbol_info: Symbol information
            
        Returns:
            Rounded price
        """
        precision = symbol_info['price_precision']
        return Decimal(str(round(float(price), precision)))
    
    def _round_quantity(self, quantity: Decimal, symbol_info: Dict[str, Any]) -> Decimal:
        """
        Round quantity to symbol's precision and step size
        
        Args:
            quantity: Quantity to round
            symbol_info: Symbol information
            
        Returns:
            Rounded quantity
        """
        step_size = symbol_info['step_size']
        precision = symbol_info['quantity_precision']
        
        # Round down to step size
        rounded = Decimal(math.floor(float(quantity) / float(step_size))) * step_size
        
        # Apply precision
        return Decimal(str(round(float(rounded), precision)))
    
    def _map_order_type(self, order_type: str) -> str:
        """
        Map generic order type to Binance futures order type
        
        Args:
            order_type: Generic order type
            
        Returns:
            Binance order type constant
        """
        mapping = {
            'market': FUTURE_ORDER_TYPE_MARKET,
            'limit': FUTURE_ORDER_TYPE_LIMIT,
            'stop': FUTURE_ORDER_TYPE_STOP_MARKET,
            'stop_limit': FUTURE_ORDER_TYPE_STOP,
            'take_profit': FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
            'take_profit_limit': FUTURE_ORDER_TYPE_TAKE_PROFIT
        }
        return mapping.get(order_type.lower(), FUTURE_ORDER_TYPE_MARKET)
    
    def _map_side(self, side: str) -> str:
        """
        Map generic side to Binance side
        
        Args:
            side: Generic side (buy/sell)
            
        Returns:
            Binance side constant
        """
        return SIDE_BUY if side.lower() == 'buy' else SIDE_SELL
    
    def _map_time_in_force(self, tif: str) -> str:
        """
        Map time in force to Binance constant
        
        Args:
            tif: Time in force
            
        Returns:
            Binance TIF constant
        """
        mapping = {
            'gtc': TIME_IN_FORCE_GTC,
            'ioc': TIME_IN_FORCE_IOC,
            'fok': TIME_IN_FORCE_FOK
        }
        return mapping.get(tif.lower(), TIME_IN_FORCE_GTC)
    
    async def submit(self, order: Dict[str, Any]) -> str:
        """
        Submit an order to Binance
        
        Args:
            order: Order details
            
        Returns:
            Order ID from Binance
            
        Raises:
            BinanceExecutionError: If order submission fails
        """
        await self._ensure_connected()
        
        symbol = order['symbol']
        side = self._map_side(order['side'])
        order_type = self._map_order_type(order.get('type', 'market'))
        quantity = Decimal(str(order['quantity']))
        
        # Get symbol info and apply precision
        symbol_info = await self._get_symbol_info(symbol)
        
        # Check if symbol is tradable
        if symbol_info['status'] != 'TRADING':
            raise SymbolNotTradableError(f"Symbol {symbol} is not tradable")
        
        # Round quantity
        quantity = self._round_quantity(quantity, symbol_info)
        
        # Validate quantity
        if quantity < symbol_info['min_qty']:
            raise BinanceExecutionError(
                f"Quantity {quantity} below minimum {symbol_info['min_qty']}"
            )
        if quantity > symbol_info['max_qty']:
            raise BinanceExecutionError(
                f"Quantity {quantity} above maximum {symbol_info['max_qty']}"
            )
        
        # Build order parameters
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': float(quantity)
        }
        
        # Add price for limit orders
        if order_type in [FUTURE_ORDER_TYPE_LIMIT, FUTURE_ORDER_TYPE_STOP]:
            if 'price' not in order:
                raise BinanceExecutionError("Price required for limit order")
            price = self._round_price(Decimal(str(order['price'])), symbol_info)
            params['price'] = float(price)
            params['timeInForce'] = self._map_time_in_force(
                order.get('time_in_force', 'GTC')
            )
        
        # Add stop price for stop orders
        if order_type in [FUTURE_ORDER_TYPE_STOP, FUTURE_ORDER_TYPE_STOP_MARKET]:
            if 'stop_price' not in order:
                raise BinanceExecutionError("Stop price required for stop order")
            stop_price = self._round_price(
                Decimal(str(order['stop_price'])),
                symbol_info
            )
            params['stopPrice'] = float(stop_price)
        
        # Add reduce-only flag if specified
        if order.get('reduce_only', False):
            params['reduceOnly'] = True
        
        # Submit order with retries
        for attempt in range(self.max_retries):
            try:
                result = await self.client.futures_create_order(**params)
                logger.info(f"Order submitted: {result['orderId']} for {symbol}")
                return str(result['orderId'])
                
            except BinanceAPIException as e:
                if e.code == -2010:  # Insufficient balance
                    raise InsufficientBalanceError(str(e))
                elif e.code == -1021:  # Timestamp issue
                    logger.warning(f"Timestamp issue, retrying... (attempt {attempt + 1})")
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Order submission failed: {e}")
                    raise BinanceExecutionError(f"Order submission failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error submitting order: {e}")
                raise BinanceExecutionError(f"Unexpected error: {e}")
        
        raise BinanceExecutionError("Max retries exceeded for order submission")
    
    async def cancel(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """
        Cancel an order on Binance
        
        Args:
            order_id: Order ID to cancel
            symbol: Optional symbol (required for Binance)
            
        Returns:
            True if cancelled successfully
            
        Raises:
            OrderNotFoundError: If order not found
        """
        await self._ensure_connected()
        
        if not symbol:
            # Try to find symbol from open orders
            orders = await self.orders()
            for order in orders:
                if str(order['order_id']) == order_id:
                    symbol = order['symbol']
                    break
            else:
                raise OrderNotFoundError(f"Order {order_id} not found")
        
        # Cancel with retries
        for attempt in range(self.max_retries):
            try:
                result = await self.client.futures_cancel_order(
                    symbol=symbol,
                    orderId=int(order_id)
                )
                logger.info(f"Order cancelled: {order_id}")
                return True
                
            except BinanceAPIException as e:
                if e.code == -2011:  # Order not found
                    raise OrderNotFoundError(f"Order {order_id} not found")
                elif e.code == -1021:  # Timestamp issue
                    logger.warning(f"Timestamp issue, retrying... (attempt {attempt + 1})")
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Order cancellation failed: {e}")
                    raise BinanceExecutionError(f"Cancellation failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error cancelling order: {e}")
                raise BinanceExecutionError(f"Unexpected error: {e}")
        
        raise BinanceExecutionError("Max retries exceeded for order cancellation")
    
    async def positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions from Binance
        
        Returns:
            List of position dictionaries
        """
        await self._ensure_connected()
        
        try:
            positions = await self.client.futures_position_information()
            
            # Filter and map positions
            result = []
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    result.append({
                        'symbol': pos['symbol'],
                        'side': 'long' if float(pos['positionAmt']) > 0 else 'short',
                        'quantity': abs(Decimal(pos['positionAmt'])),
                        'entry_price': Decimal(pos['entryPrice']),
                        'current_price': Decimal(pos['markPrice']),
                        'unrealized_pnl': Decimal(pos['unRealizedProfit']),
                        'realized_pnl': Decimal('0'),  # Not provided by Binance here
                        'margin_used': Decimal(pos['initialMargin']),
                        'leverage': Decimal(pos['leverage'])
                    })
            
            return result
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get positions: {e}")
            raise BinanceExecutionError(f"Failed to get positions: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting positions: {e}")
            raise BinanceExecutionError(f"Unexpected error: {e}")
    
    async def orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get orders from Binance
        
        Args:
            status: Optional status filter
            
        Returns:
            List of order dictionaries
        """
        await self._ensure_connected()
        
        try:
            if status and status.lower() == 'pending':
                # Get open orders only
                orders = await self.client.futures_get_open_orders()
            else:
                # Get all recent orders
                orders = await self.client.futures_get_all_orders(limit=100)
            
            # Map orders
            result = []
            for order in orders:
                result.append({
                    'order_id': str(order['orderId']),
                    'symbol': order['symbol'],
                    'side': order['side'].lower(),
                    'type': order['type'].lower(),
                    'quantity': Decimal(order['origQty']),
                    'filled_quantity': Decimal(order['executedQty']),
                    'price': Decimal(order['price']) if order['price'] else None,
                    'average_fill_price': Decimal(order['avgPrice']) if order['avgPrice'] else None,
                    'status': order['status'].lower(),
                    'created_at': datetime.fromtimestamp(order['time'] / 1000),
                    'updated_at': datetime.fromtimestamp(order['updateTime'] / 1000)
                })
            
            # Filter by status if specified
            if status and status.lower() != 'pending':
                result = [o for o in result if o['status'] == status.lower()]
            
            return result
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get orders: {e}")
            raise BinanceExecutionError(f"Failed to get orders: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting orders: {e}")
            raise BinanceExecutionError(f"Unexpected error: {e}")
    
    async def get_order(self, order_id: str, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get specific order details
        
        Args:
            order_id: Order ID
            symbol: Optional symbol
            
        Returns:
            Order details or None if not found
        """
        orders = await self.orders()
        for order in orders:
            if order['order_id'] == order_id:
                return order
        return None
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get position for specific symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Position details or None if no position
        """
        positions = await self.positions()
        for pos in positions:
            if pos['symbol'] == symbol:
                return pos
        return None
    
    async def modify_order(
        self,
        order_id: str,
        modifications: Dict[str, Any]
    ) -> bool:
        """
        Modify an order (cancel and replace)
        
        Args:
            order_id: Order to modify
            modifications: New parameters
            
        Returns:
            True if modified successfully
        """
        # Binance doesn't support direct modification
        # Need to cancel and place new order
        order = await self.get_order(order_id)
        if not order:
            raise OrderNotFoundError(f"Order {order_id} not found")
        
        # Cancel existing order
        await self.cancel(order_id, order['symbol'])
        
        # Create new order with modifications
        new_order = {
            'symbol': order['symbol'],
            'side': order['side'],
            'type': order['type'],
            'quantity': modifications.get('quantity', order['quantity']),
            'price': modifications.get('price', order.get('price'))
        }
        
        # Submit new order
        new_id = await self.submit(new_order)
        logger.info(f"Order modified: {order_id} -> {new_id}")
        
        return True
    
    async def get_account_balance(self) -> Dict[str, Decimal]:
        """
        Get account balance information
        
        Returns:
            Balance details
        """
        await self._ensure_connected()
        
        try:
            account = await self.client.futures_account()
            
            return {
                'available': Decimal(account['availableBalance']),
                'locked': Decimal(account['totalInitialMargin']),
                'total': Decimal(account['totalWalletBalance']),
                'unrealized_pnl': Decimal(account['totalUnrealizedProfit']),
                'margin_ratio': Decimal(account['totalMarginBalance'])
            }
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get account balance: {e}")
            raise BinanceExecutionError(f"Failed to get balance: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting balance: {e}")
            raise BinanceExecutionError(f"Unexpected error: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()