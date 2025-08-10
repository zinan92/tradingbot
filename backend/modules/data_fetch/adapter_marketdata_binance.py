import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from binance import AsyncClient, BinanceSocketManager
from binance.enums import FuturesType
import aiohttp

logger = logging.getLogger(__name__)

class BinanceFuturesClient:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client: Optional[AsyncClient] = None
        self.socket_manager: Optional[BinanceSocketManager] = None
        self.active_streams: Dict[str, Any] = {}
        self.callbacks: Dict[str, List[Callable]] = {
            'kline': [],
            'depth': [],
            'trade': [],
            'ticker': [],
            'mark_price': []
        }
        self.reconnect_delay = 5
        self.max_reconnect_attempts = 10
        self.futures_type = FuturesType.USD_M  # USDT-M Futures
        
    async def start(self):
        try:
            self.client = await AsyncClient.create(
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            self.socket_manager = BinanceSocketManager(self.client)
            logger.info("Binance Futures client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    async def stop(self):
        try:
            # Stop all active streams
            for stream_id in list(self.active_streams.keys()):
                await self.unsubscribe_stream(stream_id)
            
            # Close the client
            if self.client:
                await self.client.close_connection()
                
            logger.info("Binance Futures client stopped")
        except Exception as e:
            logger.error(f"Error stopping Binance client: {e}")
    
    def register_callback(self, data_type: str, callback: Callable):
        if data_type in self.callbacks:
            self.callbacks[data_type].append(callback)
            logger.debug(f"Registered callback for {data_type}")
        else:
            logger.warning(f"Unknown data type: {data_type}")
    
    async def subscribe_kline_stream(self, symbol: str, interval: str):
        stream_id = f"kline_{symbol}_{interval}"
        if stream_id in self.active_streams:
            logger.warning(f"Already subscribed to {stream_id}")
            return
        
        try:
            socket = self.socket_manager.futures_kline_socket(
                symbol=symbol.lower(),
                interval=interval,
                futures_type=self.futures_type
            )
            
            self.active_streams[stream_id] = {
                'socket': socket,
                'symbol': symbol,
                'interval': interval,
                'type': 'kline'
            }
            
            asyncio.create_task(self._handle_stream(stream_id, socket))
            logger.info(f"Subscribed to kline stream: {symbol} {interval}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to kline stream: {e}")
            raise
    
    async def subscribe_depth_stream(self, symbol: str, depth: int = 20, update_speed: int = 100):
        stream_id = f"depth_{symbol}_{depth}"
        if stream_id in self.active_streams:
            logger.warning(f"Already subscribed to {stream_id}")
            return
        
        try:
            socket = self.socket_manager.futures_depth_socket(
                symbol=symbol.lower(),
                depth=depth,
                update_time=update_speed,
                futures_type=self.futures_type
            )
            
            self.active_streams[stream_id] = {
                'socket': socket,
                'symbol': symbol,
                'depth': depth,
                'type': 'depth'
            }
            
            asyncio.create_task(self._handle_stream(stream_id, socket))
            logger.info(f"Subscribed to depth stream: {symbol} depth={depth}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to depth stream: {e}")
            raise
    
    async def subscribe_trade_stream(self, symbol: str):
        stream_id = f"trade_{symbol}"
        if stream_id in self.active_streams:
            logger.warning(f"Already subscribed to {stream_id}")
            return
        
        try:
            socket = self.socket_manager.futures_trade_socket(
                symbol=symbol.lower(),
                futures_type=self.futures_type
            )
            
            self.active_streams[stream_id] = {
                'socket': socket,
                'symbol': symbol,
                'type': 'trade'
            }
            
            asyncio.create_task(self._handle_stream(stream_id, socket))
            logger.info(f"Subscribed to trade stream: {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to trade stream: {e}")
            raise
    
    async def subscribe_ticker_stream(self, symbol: str):
        stream_id = f"ticker_{symbol}"
        if stream_id in self.active_streams:
            logger.warning(f"Already subscribed to {stream_id}")
            return
        
        try:
            socket = self.socket_manager.futures_ticker_socket(
                symbol=symbol.lower(),
                futures_type=self.futures_type
            )
            
            self.active_streams[stream_id] = {
                'socket': socket,
                'symbol': symbol,
                'type': 'ticker'
            }
            
            asyncio.create_task(self._handle_stream(stream_id, socket))
            logger.info(f"Subscribed to ticker stream: {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to ticker stream: {e}")
            raise
    
    async def subscribe_mark_price_stream(self, symbol: str, update_speed: int = 1000):
        stream_id = f"mark_price_{symbol}"
        if stream_id in self.active_streams:
            logger.warning(f"Already subscribed to {stream_id}")
            return
        
        try:
            # Mark price stream for futures
            socket = self.socket_manager.futures_mark_price_socket(
                symbol=symbol.lower(),
                update_time=update_speed,
                futures_type=self.futures_type
            )
            
            self.active_streams[stream_id] = {
                'socket': socket,
                'symbol': symbol,
                'type': 'mark_price'
            }
            
            asyncio.create_task(self._handle_stream(stream_id, socket))
            logger.info(f"Subscribed to mark price stream: {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to mark price stream: {e}")
            raise
    
    async def unsubscribe_stream(self, stream_id: str):
        if stream_id not in self.active_streams:
            logger.warning(f"Stream {stream_id} not found")
            return
        
        try:
            stream_info = self.active_streams[stream_id]
            # Cancel the socket
            if 'task' in stream_info:
                stream_info['task'].cancel()
            
            del self.active_streams[stream_id]
            logger.info(f"Unsubscribed from stream: {stream_id}")
            
        except Exception as e:
            logger.error(f"Error unsubscribing from stream {stream_id}: {e}")
    
    async def _handle_stream(self, stream_id: str, socket):
        reconnect_attempts = 0
        
        while stream_id in self.active_streams and reconnect_attempts < self.max_reconnect_attempts:
            try:
                async with socket as stream:
                    reconnect_attempts = 0  # Reset on successful connection
                    logger.info(f"Stream {stream_id} connected")
                    
                    async for msg in stream:
                        if stream_id not in self.active_streams:
                            break
                        
                        try:
                            await self._process_message(stream_id, msg)
                        except Exception as e:
                            logger.error(f"Error processing message from {stream_id}: {e}")
                            
            except Exception as e:
                logger.error(f"Stream {stream_id} disconnected: {e}")
                reconnect_attempts += 1
                
                if stream_id in self.active_streams and reconnect_attempts < self.max_reconnect_attempts:
                    await asyncio.sleep(self.reconnect_delay * reconnect_attempts)
                    logger.info(f"Attempting to reconnect stream {stream_id} (attempt {reconnect_attempts})")
                else:
                    logger.error(f"Max reconnection attempts reached for {stream_id}")
                    break
        
        # Clean up
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
    
    async def _process_message(self, stream_id: str, msg: Dict):
        stream_info = self.active_streams.get(stream_id)
        if not stream_info:
            return
        
        data_type = stream_info['type']
        
        # Call registered callbacks
        for callback in self.callbacks.get(data_type, []):
            try:
                await callback(msg, stream_info)
            except Exception as e:
                logger.error(f"Error in callback for {data_type}: {e}")
    
    # REST API Methods
    async def get_exchange_info(self) -> Dict:
        try:
            return await self.client.futures_exchange_info()
        except Exception as e:
            logger.error(f"Failed to get exchange info: {e}")
            raise
    
    async def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        try:
            info = await self.get_exchange_info()
            for s in info['symbols']:
                if s['symbol'] == symbol.upper():
                    return s
            return None
        except Exception as e:
            logger.error(f"Failed to get symbol info for {symbol}: {e}")
            raise
    
    async def get_historical_klines(self, 
                                  symbol: str, 
                                  interval: str,
                                  start_time: Optional[int] = None,
                                  end_time: Optional[int] = None,
                                  limit: int = 500) -> List[List]:
        try:
            klines = await self.client.futures_klines(
                symbol=symbol.upper(),
                interval=interval,
                startTime=start_time,
                endTime=end_time,
                limit=limit
            )
            return klines
        except Exception as e:
            logger.error(f"Failed to get historical klines: {e}")
            raise
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        try:
            return await self.client.futures_order_book(
                symbol=symbol.upper(),
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            raise
    
    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict]:
        try:
            return await self.client.futures_recent_trades(
                symbol=symbol.upper(),
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            raise
    
    async def get_ticker_24hr(self, symbol: Optional[str] = None) -> Dict:
        try:
            if symbol:
                return await self.client.futures_ticker(symbol=symbol.upper())
            else:
                return await self.client.futures_ticker()
        except Exception as e:
            logger.error(f"Failed to get 24hr ticker: {e}")
            raise
    
    async def get_mark_price(self, symbol: Optional[str] = None) -> Dict:
        try:
            if symbol:
                return await self.client.futures_mark_price(symbol=symbol.upper())
            else:
                return await self.client.futures_mark_price()
        except Exception as e:
            logger.error(f"Failed to get mark price: {e}")
            raise
    
    async def get_funding_rate(self, symbol: str, limit: int = 100) -> List[Dict]:
        try:
            return await self.client.futures_funding_rate(
                symbol=symbol.upper(),
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to get funding rate: {e}")
            raise
    
    async def get_open_interest(self, symbol: str) -> Dict:
        try:
            return await self.client.futures_open_interest(symbol=symbol.upper())
        except Exception as e:
            logger.error(f"Failed to get open interest: {e}")
            raise