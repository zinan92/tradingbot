"""
Order Execution Bridge

Connects trading signals to Binance order execution with proper error handling,
retry logic, and order management.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from decimal import Decimal, ROUND_DOWN
from dataclasses import dataclass, asdict
import json

from src.infrastructure.binance_client import BinanceClient

logger = logging.getLogger(__name__)


@dataclass
class OrderRequest:
    """Order request with all necessary parameters"""
    symbol: str
    side: str  # BUY or SELL
    order_type: str  # MARKET, LIMIT, STOP_MARKET, TAKE_PROFIT_MARKET
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None
    time_in_force: str = 'GTC'  # Good Till Cancel
    reduce_only: bool = False


@dataclass
class OrderResult:
    """Order execution result"""
    success: bool
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    status: Optional[str] = None
    executed_qty: float = 0.0
    avg_price: float = 0.0
    fee: float = 0.0
    fee_asset: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None


class OrderExecutionBridge:
    """
    Manages order execution with Binance Futures API
    Handles order placement, tracking, cancellation, and error recovery
    """
    
    def __init__(
        self,
        binance_client: BinanceClient,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        use_testnet: bool = True
    ):
        """
        Initialize order execution bridge
        
        Args:
            binance_client: Binance API client
            max_retries: Maximum number of retries for failed orders
            retry_delay: Delay between retries in seconds
            use_testnet: Whether to use testnet
        """
        self.client = binance_client
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_testnet = use_testnet
        
        # Order tracking
        self.active_orders: Dict[str, OrderRequest] = {}
        self.order_history: List[OrderResult] = []
        
        # Symbol information cache
        self.symbol_info: Dict[str, Any] = {}
        
        # Statistics
        self.total_orders = 0
        self.successful_orders = 0
        self.failed_orders = 0
        
        logger.info(f"Order Execution Bridge initialized (testnet={use_testnet})")
    
    async def initialize(self):
        """Initialize bridge and load exchange information"""
        try:
            # Get exchange info for symbol filters
            exchange_info = await self.client.get_exchange_info()
            
            # Cache symbol information
            for symbol in exchange_info['symbols']:
                self.symbol_info[symbol['symbol']] = {
                    'status': symbol['status'],
                    'baseAsset': symbol['baseAsset'],
                    'quoteAsset': symbol['quoteAsset'],
                    'filters': {f['filterType']: f for f in symbol['filters']}
                }
            
            logger.info(f"Loaded info for {len(self.symbol_info)} symbols")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    def _get_symbol_precision(self, symbol: str) -> Dict[str, Any]:
        """Get symbol trading precision and limits"""
        if symbol not in self.symbol_info:
            return {
                'price_precision': 2,
                'quantity_precision': 3,
                'min_qty': 0.001,
                'max_qty': 10000,
                'min_notional': 10
            }
        
        info = self.symbol_info[symbol]
        filters = info['filters']
        
        # Extract precision and limits from filters
        lot_size = filters.get('LOT_SIZE', {})
        price_filter = filters.get('PRICE_FILTER', {})
        min_notional = filters.get('MIN_NOTIONAL', {})
        
        return {
            'price_precision': self._get_precision(float(price_filter.get('tickSize', 0.01))),
            'quantity_precision': self._get_precision(float(lot_size.get('stepSize', 0.001))),
            'min_qty': float(lot_size.get('minQty', 0.001)),
            'max_qty': float(lot_size.get('maxQty', 10000)),
            'min_notional': float(min_notional.get('minNotional', 10))
        }
    
    def _get_precision(self, step_size: float) -> int:
        """Calculate precision from step size"""
        if step_size >= 1:
            return 0
        return len(str(step_size).split('.')[-1].rstrip('0'))
    
    def _round_quantity(self, quantity: float, symbol: str) -> float:
        """Round quantity to symbol's precision"""
        precision = self._get_symbol_precision(symbol)
        qty_precision = precision['quantity_precision']
        
        # Use Decimal for precise rounding
        qty_decimal = Decimal(str(quantity))
        rounded = qty_decimal.quantize(
            Decimal(10) ** -qty_precision,
            rounding=ROUND_DOWN
        )
        
        return float(rounded)
    
    def _round_price(self, price: float, symbol: str) -> float:
        """Round price to symbol's precision"""
        precision = self._get_symbol_precision(symbol)
        price_precision = precision['price_precision']
        
        # Use Decimal for precise rounding
        price_decimal = Decimal(str(price))
        rounded = price_decimal.quantize(
            Decimal(10) ** -price_precision,
            rounding=ROUND_DOWN
        )
        
        return float(rounded)
    
    async def place_order(self, request: OrderRequest) -> OrderResult:
        """
        Place an order with retry logic
        
        Args:
            request: Order request parameters
            
        Returns:
            OrderResult with execution details
        """
        self.total_orders += 1
        
        # Validate and adjust order parameters
        request = self._validate_order(request)
        
        # Attempt to place order with retries
        for attempt in range(self.max_retries):
            try:
                result = await self._execute_order(request)
                
                if result.success:
                    self.successful_orders += 1
                    self.order_history.append(result)
                    
                    # Track active order
                    if result.order_id:
                        self.active_orders[result.order_id] = request
                    
                    logger.info(f"Order placed successfully: {result.order_id}")
                    return result
                
                # Check if error is retryable
                if not self._is_retryable_error(result.error):
                    self.failed_orders += 1
                    logger.error(f"Non-retryable error: {result.error}")
                    return result
                
                # Wait before retry
                logger.warning(f"Order failed (attempt {attempt + 1}): {result.error}")
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                
            except Exception as e:
                logger.error(f"Exception placing order: {e}")
                
                if attempt == self.max_retries - 1:
                    self.failed_orders += 1
                    return OrderResult(
                        success=False,
                        error=str(e),
                        timestamp=datetime.now()
                    )
                
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        self.failed_orders += 1
        return OrderResult(
            success=False,
            error="Max retries exceeded",
            timestamp=datetime.now()
        )
    
    def _validate_order(self, request: OrderRequest) -> OrderRequest:
        """Validate and adjust order parameters"""
        try:
            # Round quantity and price to symbol precision
            request.quantity = self._round_quantity(request.quantity, request.symbol)
            
            if request.price:
                request.price = self._round_price(request.price, request.symbol)
            
            if request.stop_price:
                request.stop_price = self._round_price(request.stop_price, request.symbol)
            
            # Check minimum quantity
            precision = self._get_symbol_precision(request.symbol)
            if request.quantity < precision['min_qty']:
                logger.warning(f"Quantity {request.quantity} below minimum {precision['min_qty']}")
                request.quantity = precision['min_qty']
            
            # Check maximum quantity
            if request.quantity > precision['max_qty']:
                logger.warning(f"Quantity {request.quantity} above maximum {precision['max_qty']}")
                request.quantity = precision['max_qty']
            
            return request
            
        except Exception as e:
            logger.error(f"Error validating order: {e}")
            return request
    
    async def _execute_order(self, request: OrderRequest) -> OrderResult:
        """Execute order on Binance"""
        try:
            # Build order parameters
            params = {
                'symbol': request.symbol,
                'side': request.side,
                'type': request.order_type,
                'quantity': request.quantity
            }
            
            # Add optional parameters
            if request.price and request.order_type == 'LIMIT':
                params['price'] = request.price
                params['timeInForce'] = request.time_in_force
            
            if request.stop_price:
                params['stopPrice'] = request.stop_price
            
            if request.client_order_id:
                params['newClientOrderId'] = request.client_order_id
            
            if request.reduce_only:
                params['reduceOnly'] = 'true'
            
            # Place order
            response = await self.client.place_order(**params)
            
            # Parse response
            if response.get('orderId'):
                return OrderResult(
                    success=True,
                    order_id=str(response['orderId']),
                    client_order_id=response.get('clientOrderId'),
                    status=response.get('status'),
                    executed_qty=float(response.get('executedQty', 0)),
                    avg_price=float(response.get('avgPrice', 0)) if response.get('avgPrice') else 0,
                    timestamp=datetime.now()
                )
            else:
                return OrderResult(
                    success=False,
                    error=response.get('msg', 'Unknown error'),
                    timestamp=datetime.now()
                )
            
        except Exception as e:
            return OrderResult(
                success=False,
                error=str(e),
                timestamp=datetime.now()
            )
    
    def _is_retryable_error(self, error: str) -> bool:
        """Check if error is retryable"""
        if not error:
            return False
        
        # Non-retryable errors
        non_retryable = [
            'INSUFFICIENT_BALANCE',
            'INVALID_SYMBOL',
            'MIN_NOTIONAL',
            'LOT_SIZE',
            'PRICE_FILTER',
            'PERCENT_PRICE',
            'MARKET_CLOSED'
        ]
        
        for err in non_retryable:
            if err in error.upper():
                return False
        
        # Retryable errors
        retryable = [
            'TIMEOUT',
            'CONNECTION',
            'NETWORK',
            'SERVER_BUSY',
            'TOO_MANY_REQUESTS'
        ]
        
        for err in retryable:
            if err in error.upper():
                return True
        
        # Default to non-retryable
        return False
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order"""
        try:
            response = await self.client.cancel_order(
                symbol=symbol,
                orderId=order_id
            )
            
            if response.get('status') == 'CANCELED':
                # Remove from active orders
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                
                logger.info(f"Order {order_id} cancelled successfully")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: str) -> int:
        """Cancel all orders for a symbol"""
        try:
            response = await self.client.cancel_all_orders(symbol=symbol)
            
            cancelled_count = len(response) if isinstance(response, list) else 0
            
            # Clear active orders for this symbol
            self.active_orders = {
                oid: order for oid, order in self.active_orders.items()
                if order.symbol != symbol
            }
            
            logger.info(f"Cancelled {cancelled_count} orders for {symbol}")
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Error cancelling all orders for {symbol}: {e}")
            return 0
    
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order status"""
        try:
            response = await self.client.query_order(
                symbol=symbol,
                orderId=order_id
            )
            
            return {
                'order_id': response.get('orderId'),
                'status': response.get('status'),
                'executed_qty': float(response.get('executedQty', 0)),
                'avg_price': float(response.get('avgPrice', 0)) if response.get('avgPrice') else 0,
                'time': response.get('time')
            }
            
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return {}
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all open orders"""
        try:
            if symbol:
                response = await self.client.get_open_orders(symbol=symbol)
            else:
                response = await self.client.get_open_orders()
            
            return [{
                'order_id': order.get('orderId'),
                'symbol': order.get('symbol'),
                'side': order.get('side'),
                'type': order.get('type'),
                'price': float(order.get('price', 0)),
                'quantity': float(order.get('origQty', 0)),
                'executed_qty': float(order.get('executedQty', 0)),
                'status': order.get('status'),
                'time': order.get('time')
            } for order in response]
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""
        success_rate = (self.successful_orders / self.total_orders * 100) if self.total_orders > 0 else 0
        
        return {
            'total_orders': self.total_orders,
            'successful_orders': self.successful_orders,
            'failed_orders': self.failed_orders,
            'success_rate': f"{success_rate:.1f}%",
            'active_orders': len(self.active_orders),
            'order_history_size': len(self.order_history)
        }
    
    async def place_bracket_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss_price: float,
        take_profit_price: float
    ) -> Dict[str, OrderResult]:
        """
        Place a bracket order (entry + stop loss + take profit)
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            quantity: Order quantity
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            
        Returns:
            Dictionary with results for each order
        """
        results = {}
        
        try:
            # Place market entry order
            entry_request = OrderRequest(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=quantity
            )
            
            entry_result = await self.place_order(entry_request)
            results['entry'] = entry_result
            
            if not entry_result.success:
                logger.error(f"Entry order failed: {entry_result.error}")
                return results
            
            # Place stop loss order
            sl_side = 'SELL' if side == 'BUY' else 'BUY'
            sl_request = OrderRequest(
                symbol=symbol,
                side=sl_side,
                order_type='STOP_MARKET',
                quantity=quantity,
                stop_price=stop_loss_price,
                reduce_only=True
            )
            
            sl_result = await self.place_order(sl_request)
            results['stop_loss'] = sl_result
            
            # Place take profit order
            tp_request = OrderRequest(
                symbol=symbol,
                side=sl_side,
                order_type='TAKE_PROFIT_MARKET',
                quantity=quantity,
                stop_price=take_profit_price,
                reduce_only=True
            )
            
            tp_result = await self.place_order(tp_request)
            results['take_profit'] = tp_result
            
            logger.info(f"Bracket order placed: Entry={entry_result.order_id}, "
                       f"SL={sl_result.order_id}, TP={tp_result.order_id}")
            
        except Exception as e:
            logger.error(f"Error placing bracket order: {e}")
        
        return results