"""
Binance V1 adapter - existing implementation.

This is the current production adapter with basic functionality.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime
import hmac
import hashlib
import time

import aiohttp
from src.infrastructure.exchange.execution_adapter import (
    ExecutionAdapter, ExecutionResult, MarketData, AccountInfo,
    SymbolInfo, OrderStatus, Order, Position
)

logger = logging.getLogger(__name__)


class BinanceV1Adapter(ExecutionAdapter):
    """Binance V1 implementation - current production version."""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        if testnet:
            self.base_url = "https://testnet.binance.vision/api"
            self.ws_url = "wss://testnet.binance.vision/ws"
        else:
            self.base_url = "https://api.binance.com/api"
            self.ws_url = "wss://stream.binance.com:9443/ws"
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.connected = False
        self.symbol_info_cache: Dict[str, SymbolInfo] = {}
        
        # Basic retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def connect(self) -> bool:
        """Establish connection to Binance."""
        try:
            self.session = aiohttp.ClientSession()
            
            # Test connection with ping
            async with self.session.get(f"{self.base_url}/v3/ping") as response:
                if response.status == 200:
                    self.connected = True
                    logger.info(f"Connected to Binance V1 ({'testnet' if self.testnet else 'mainnet'})")
                    
                    # Load exchange info
                    await self._load_exchange_info()
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to connect to Binance V1: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Close connection to Binance."""
        if self.session:
            await self.session.close()
            self.session = None
        
        self.connected = False
        logger.info("Disconnected from Binance V1")
        return True
    
    async def is_connected(self) -> bool:
        """Check connection status."""
        return self.connected and self.session is not None
    
    async def place_order(self, order: Order) -> ExecutionResult:
        """Place order on Binance."""
        if not self.connected:
            return ExecutionResult(
                success=False,
                order_id="",
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                average_price=Decimal("0"),
                commission=Decimal("0"),
                commission_asset="",
                timestamp=datetime.now(),
                raw_response={},
                error_message="Not connected"
            )
        
        # Prepare order parameters
        params = {
            "symbol": order.symbol.value,
            "side": order.side.value,
            "type": order.type.value,
            "quantity": str(self.format_quantity(order.quantity.value, order.symbol.value)),
            "timestamp": int(time.time() * 1000)
        }
        
        if order.price:
            params["price"] = str(self.format_price(order.price.value, order.symbol.value))
            params["timeInForce"] = "GTC"
        
        # Sign request
        params["signature"] = self._sign_request(params)
        
        # Execute with basic retry
        for attempt in range(self.max_retries):
            try:
                async with self.session.post(
                    f"{self.base_url}/v3/order",
                    headers={"X-MBX-APIKEY": self.api_key},
                    params=params
                ) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        return ExecutionResult(
                            success=True,
                            order_id=str(data["orderId"]),
                            status=OrderStatus(data["status"]),
                            filled_quantity=Decimal(data.get("executedQty", "0")),
                            average_price=Decimal(data.get("price", "0")),
                            commission=Decimal("0"),  # Would need separate call
                            commission_asset="BNB",
                            timestamp=datetime.fromtimestamp(data["transactTime"] / 1000),
                            raw_response=data,
                            retry_count=attempt
                        )
                    else:
                        error_msg = data.get("msg", "Unknown error")
                        logger.error(f"Order failed: {error_msg}")
                        
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        
                        return ExecutionResult(
                            success=False,
                            order_id="",
                            status=OrderStatus.REJECTED,
                            filled_quantity=Decimal("0"),
                            average_price=Decimal("0"),
                            commission=Decimal("0"),
                            commission_asset="",
                            timestamp=datetime.now(),
                            raw_response=data,
                            error_message=error_msg,
                            retry_count=attempt
                        )
            
            except Exception as e:
                logger.error(f"Order placement error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return ExecutionResult(
                        success=False,
                        order_id="",
                        status=OrderStatus.REJECTED,
                        filled_quantity=Decimal("0"),
                        average_price=Decimal("0"),
                        commission=Decimal("0"),
                        commission_asset="",
                        timestamp=datetime.now(),
                        raw_response={},
                        error_message=str(e),
                        retry_count=attempt
                    )
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel order on Binance."""
        if not self.connected:
            return False
        
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "timestamp": int(time.time() * 1000)
        }
        params["signature"] = self._sign_request(params)
        
        try:
            async with self.session.delete(
                f"{self.base_url}/v3/order",
                headers={"X-MBX-APIKEY": self.api_key},
                params=params
            ) as response:
                return response.status == 200
        
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    async def get_order_status(self, order_id: str, symbol: str) -> ExecutionResult:
        """Get order status from Binance."""
        if not self.connected:
            return ExecutionResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                average_price=Decimal("0"),
                commission=Decimal("0"),
                commission_asset="",
                timestamp=datetime.now(),
                raw_response={},
                error_message="Not connected"
            )
        
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "timestamp": int(time.time() * 1000)
        }
        params["signature"] = self._sign_request(params)
        
        try:
            async with self.session.get(
                f"{self.base_url}/v3/order",
                headers={"X-MBX-APIKEY": self.api_key},
                params=params
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    return ExecutionResult(
                        success=True,
                        order_id=order_id,
                        status=OrderStatus(data["status"]),
                        filled_quantity=Decimal(data.get("executedQty", "0")),
                        average_price=Decimal(data.get("price", "0")),
                        commission=Decimal("0"),
                        commission_asset="BNB",
                        timestamp=datetime.fromtimestamp(data["updateTime"] / 1000),
                        raw_response=data
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        order_id=order_id,
                        status=OrderStatus.REJECTED,
                        filled_quantity=Decimal("0"),
                        average_price=Decimal("0"),
                        commission=Decimal("0"),
                        commission_asset="",
                        timestamp=datetime.now(),
                        raw_response=data,
                        error_message=data.get("msg", "Unknown error")
                    )
        
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return ExecutionResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                filled_quantity=Decimal("0"),
                average_price=Decimal("0"),
                commission=Decimal("0"),
                commission_asset="",
                timestamp=datetime.now(),
                raw_response={},
                error_message=str(e)
            )
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get open orders from Binance."""
        if not self.connected:
            return []
        
        params = {"timestamp": int(time.time() * 1000)}
        if symbol:
            params["symbol"] = symbol
        
        params["signature"] = self._sign_request(params)
        
        try:
            async with self.session.get(
                f"{self.base_url}/v3/openOrders",
                headers={"X-MBX-APIKEY": self.api_key},
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Convert to Order objects
                    return []  # Simplified for now
                
                return []
        
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []
    
    async def get_account_info(self) -> AccountInfo:
        """Get account information from Binance."""
        if not self.connected:
            return AccountInfo(
                balances={},
                positions=[],
                margin_level=None,
                free_margin=None,
                equity=Decimal("0"),
                timestamp=datetime.now()
            )
        
        params = {"timestamp": int(time.time() * 1000)}
        params["signature"] = self._sign_request(params)
        
        try:
            async with self.session.get(
                f"{self.base_url}/v3/account",
                headers={"X-MBX-APIKEY": self.api_key},
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    balances = {}
                    for balance in data["balances"]:
                        free = Decimal(balance["free"])
                        locked = Decimal(balance["locked"])
                        if free > 0 or locked > 0:
                            balances[balance["asset"]] = free + locked
                    
                    return AccountInfo(
                        balances=balances,
                        positions=[],  # Spot doesn't have positions
                        margin_level=None,
                        free_margin=None,
                        equity=sum(balances.values()),  # Simplified
                        timestamp=datetime.now()
                    )
                
                return AccountInfo(
                    balances={},
                    positions=[],
                    margin_level=None,
                    free_margin=None,
                    equity=Decimal("0"),
                    timestamp=datetime.now()
                )
        
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return AccountInfo(
                balances={},
                positions=[],
                margin_level=None,
                free_margin=None,
                equity=Decimal("0"),
                timestamp=datetime.now()
            )
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get market data from Binance."""
        if not self.connected:
            return MarketData(
                symbol=symbol,
                bid=Decimal("0"),
                ask=Decimal("0"),
                last=Decimal("0"),
                volume_24h=Decimal("0"),
                timestamp=datetime.now()
            )
        
        try:
            async with self.session.get(
                f"{self.base_url}/v3/ticker/bookTicker",
                params={"symbol": symbol}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    return MarketData(
                        symbol=symbol,
                        bid=Decimal(data["bidPrice"]),
                        ask=Decimal(data["askPrice"]),
                        last=(Decimal(data["bidPrice"]) + Decimal(data["askPrice"])) / 2,
                        volume_24h=Decimal("0"),  # Would need separate call
                        timestamp=datetime.now()
                    )
                
                return MarketData(
                    symbol=symbol,
                    bid=Decimal("0"),
                    ask=Decimal("0"),
                    last=Decimal("0"),
                    volume_24h=Decimal("0"),
                    timestamp=datetime.now()
                )
        
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            return MarketData(
                symbol=symbol,
                bid=Decimal("0"),
                ask=Decimal("0"),
                last=Decimal("0"),
                volume_24h=Decimal("0"),
                timestamp=datetime.now()
            )
    
    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get symbol trading rules."""
        if symbol in self.symbol_info_cache:
            return self.symbol_info_cache[symbol]
        
        # Default if not found
        return SymbolInfo(
            symbol=symbol,
            base_asset="",
            quote_asset="USDT",
            status="TRADING",
            min_quantity=Decimal("0.00001"),
            max_quantity=Decimal("10000"),
            step_size=Decimal("0.00001"),
            min_notional=Decimal("10"),
            price_precision=2,
            quantity_precision=5,
            base_precision=8,
            quote_precision=8,
            filters={}
        )
    
    async def get_precision_map(self) -> Dict[str, Tuple[int, int]]:
        """Get precision map for all symbols."""
        precision_map = {}
        
        for symbol, info in self.symbol_info_cache.items():
            precision_map[symbol] = (info.price_precision, info.quantity_precision)
        
        return precision_map
    
    def get_adapter_name(self) -> str:
        """Get adapter name."""
        return "binance_v1"
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status."""
        return {
            "adapter": "binance_v1",
            "connected": self.connected,
            "testnet": self.testnet,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _load_exchange_info(self):
        """Load exchange information."""
        try:
            async with self.session.get(f"{self.base_url}/v3/exchangeInfo") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    for symbol_data in data["symbols"]:
                        symbol = symbol_data["symbol"]
                        
                        # Extract filters
                        filters = {f["filterType"]: f for f in symbol_data["filters"]}
                        
                        # LOT_SIZE filter for quantity
                        lot_size = filters.get("LOT_SIZE", {})
                        
                        # PRICE_FILTER for price
                        price_filter = filters.get("PRICE_FILTER", {})
                        
                        self.symbol_info_cache[symbol] = SymbolInfo(
                            symbol=symbol,
                            base_asset=symbol_data["baseAsset"],
                            quote_asset=symbol_data["quoteAsset"],
                            status=symbol_data["status"],
                            min_quantity=Decimal(lot_size.get("minQty", "0.00001")),
                            max_quantity=Decimal(lot_size.get("maxQty", "10000")),
                            step_size=Decimal(lot_size.get("stepSize", "0.00001")),
                            min_notional=Decimal(filters.get("MIN_NOTIONAL", {}).get("minNotional", "10")),
                            price_precision=symbol_data.get("quotePrecision", 8),
                            quantity_precision=symbol_data.get("baseAssetPrecision", 8),
                            base_precision=symbol_data.get("baseAssetPrecision", 8),
                            quote_precision=symbol_data.get("quotePrecision", 8),
                            filters=filters
                        )
                    
                    logger.info(f"Loaded {len(self.symbol_info_cache)} symbols")
        
        except Exception as e:
            logger.error(f"Failed to load exchange info: {e}")
    
    def _sign_request(self, params: Dict[str, Any]) -> str:
        """Sign request parameters."""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature