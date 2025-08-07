import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .binance_client import BinanceFuturesClient
from .data_normalizer import BinanceDataNormalizer
from ..persistence.postgres.market_data_repository import MarketDataRepository
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)

class MarketDataService:
    def __init__(self,
                 db_session: Session,
                 event_bus: InMemoryEventBus,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None):
        self.db_session = db_session
        self.event_bus = event_bus
        self.repository = MarketDataRepository(db_session)
        self.client = BinanceFuturesClient(api_key, api_secret)
        self.normalizer = BinanceDataNormalizer()
        
        # Track subscribed symbols and data types
        self.subscribed_symbols: Set[str] = set()
        self.active_subscriptions: Dict[str, List[str]] = {}
        
        # Configuration
        self.default_interval = '1m'
        self.default_depth = 20
        self.store_to_db = True
        self.publish_events = True
        
        # Stats
        self.stats = {
            'klines_received': 0,
            'trades_received': 0,
            'depth_updates': 0,
            'events_published': 0,
            'db_writes': 0,
            'errors': 0
        }
    
    async def start(self):
        """Start the market data service"""
        try:
            await self.client.start()
            
            # Register callbacks for different data types
            self.client.register_callback('kline', self._handle_kline_data)
            self.client.register_callback('depth', self._handle_depth_data)
            self.client.register_callback('trade', self._handle_trade_data)
            self.client.register_callback('ticker', self._handle_ticker_data)
            self.client.register_callback('mark_price', self._handle_mark_price_data)
            
            logger.info("Market data service started successfully")
            
            # Load symbol information
            await self._load_symbol_info()
            
        except Exception as e:
            logger.error(f"Failed to start market data service: {e}")
            raise
    
    async def stop(self):
        """Stop the market data service"""
        try:
            await self.client.stop()
            logger.info(f"Market data service stopped. Stats: {self.stats}")
        except Exception as e:
            logger.error(f"Error stopping market data service: {e}")
    
    async def subscribe_symbol(self, 
                              symbol: str,
                              data_types: List[str] = None,
                              interval: str = None):
        """
        Subscribe to market data for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            data_types: List of data types to subscribe ['kline', 'depth', 'trade', 'ticker', 'mark_price']
            interval: Kline interval (e.g., '1m', '5m', '1h')
        """
        if data_types is None:
            data_types = ['kline', 'depth', 'trade']
        
        if interval is None:
            interval = self.default_interval
        
        symbol = symbol.upper()
        
        try:
            # Subscribe to each data type
            for data_type in data_types:
                if data_type == 'kline':
                    await self.client.subscribe_kline_stream(symbol, interval)
                elif data_type == 'depth':
                    await self.client.subscribe_depth_stream(symbol, self.default_depth)
                elif data_type == 'trade':
                    await self.client.subscribe_trade_stream(symbol)
                elif data_type == 'ticker':
                    await self.client.subscribe_ticker_stream(symbol)
                elif data_type == 'mark_price':
                    await self.client.subscribe_mark_price_stream(symbol)
                else:
                    logger.warning(f"Unknown data type: {data_type}")
                    continue
            
            # Track subscriptions
            self.subscribed_symbols.add(symbol)
            if symbol not in self.active_subscriptions:
                self.active_subscriptions[symbol] = []
            self.active_subscriptions[symbol].extend(data_types)
            
            logger.info(f"Subscribed to {data_types} for {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol}: {e}")
            raise
    
    async def unsubscribe_symbol(self, symbol: str):
        """Unsubscribe from all data streams for a symbol"""
        symbol = symbol.upper()
        
        if symbol not in self.subscribed_symbols:
            logger.warning(f"Symbol {symbol} not subscribed")
            return
        
        try:
            # Find and unsubscribe all streams for this symbol
            for stream_id in list(self.client.active_streams.keys()):
                if symbol in stream_id:
                    await self.client.unsubscribe_stream(stream_id)
            
            # Update tracking
            self.subscribed_symbols.discard(symbol)
            self.active_subscriptions.pop(symbol, None)
            
            logger.info(f"Unsubscribed from {symbol}")
            
        except Exception as e:
            logger.error(f"Error unsubscribing from {symbol}: {e}")
    
    async def load_historical_data(self,
                                  symbol: str,
                                  interval: str = '1m',
                                  days_back: int = 7):
        """Load historical kline data from Binance"""
        try:
            symbol = symbol.upper()
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
            
            logger.info(f"Loading {days_back} days of {interval} data for {symbol}")
            
            all_klines = []
            current_start = start_time
            
            while current_start < end_time:
                klines = await self.client.get_historical_klines(
                    symbol=symbol,
                    interval=interval,
                    start_time=current_start,
                    end_time=end_time,
                    limit=1000
                )
                
                if not klines:
                    break
                
                all_klines.extend(klines)
                
                # Move to next batch
                current_start = klines[-1][0] + 1
                
                # Rate limiting
                await asyncio.sleep(0.1)
            
            # Store in database
            for kline in all_klines:
                normalized = self.normalizer.normalize_historical_kline(kline, symbol, interval)
                if self.store_to_db:
                    self.repository.save_kline(normalized)
            
            logger.info(f"Loaded {len(all_klines)} historical klines for {symbol}")
            return len(all_klines)
            
        except Exception as e:
            logger.error(f"Failed to load historical data: {e}")
            raise
    
    async def _handle_kline_data(self, msg: Dict, stream_info: Dict):
        """Handle incoming kline data"""
        try:
            symbol = stream_info['symbol']
            interval = stream_info['interval']
            
            # Normalize data
            normalized = self.normalizer.normalize_kline(msg, symbol, interval)
            
            # Only process closed klines for storage and events
            if normalized['is_closed']:
                # Store in database
                if self.store_to_db:
                    self.repository.save_kline(normalized)
                    self.stats['db_writes'] += 1
                
                # Publish event
                if self.publish_events:
                    event = self.normalizer.to_market_data_event(normalized, 'kline')
                    self.event_bus.publish(event)
                    self.stats['events_published'] += 1
            
            self.stats['klines_received'] += 1
            
        except Exception as e:
            logger.error(f"Error handling kline data: {e}")
            self.stats['errors'] += 1
    
    async def _handle_depth_data(self, msg: Dict, stream_info: Dict):
        """Handle incoming order book depth data"""
        try:
            symbol = stream_info['symbol']
            
            # Normalize data
            normalized = self.normalizer.normalize_depth(msg, symbol)
            
            # Store snapshot (limit frequency to avoid overwhelming DB)
            if self.store_to_db and self.stats['depth_updates'] % 10 == 0:
                self.repository.save_orderbook_snapshot(normalized)
                self.stats['db_writes'] += 1
            
            # Publish event for best bid/ask changes
            if self.publish_events and normalized['best_bid_price'] > 0:
                # Create a simplified market data event with mid price
                mid_price = (normalized['best_bid_price'] + normalized['best_ask_price']) / 2
                simplified = {
                    'symbol': symbol,
                    'price': mid_price,
                    'volume': 0,
                    'timestamp': normalized['timestamp']
                }
                event = self.normalizer.to_market_data_event(simplified, 'depth')
                self.event_bus.publish(event)
                self.stats['events_published'] += 1
            
            self.stats['depth_updates'] += 1
            
        except Exception as e:
            logger.error(f"Error handling depth data: {e}")
            self.stats['errors'] += 1
    
    async def _handle_trade_data(self, msg: Dict, stream_info: Dict):
        """Handle incoming trade data"""
        try:
            symbol = stream_info['symbol']
            
            # Normalize data
            normalized = self.normalizer.normalize_trade(msg, symbol)
            
            # Store in database
            if self.store_to_db:
                self.repository.save_trade(normalized)
                self.stats['db_writes'] += 1
            
            # Publish event
            if self.publish_events:
                event = self.normalizer.to_market_data_event(normalized, 'trade')
                self.event_bus.publish(event)
                self.stats['events_published'] += 1
            
            self.stats['trades_received'] += 1
            
        except Exception as e:
            logger.error(f"Error handling trade data: {e}")
            self.stats['errors'] += 1
    
    async def _handle_ticker_data(self, msg: Dict, stream_info: Dict):
        """Handle incoming 24hr ticker data"""
        try:
            symbol = stream_info['symbol']
            
            # Normalize data
            normalized = self.normalizer.normalize_ticker(msg, symbol)
            
            # Store as market metrics
            if self.store_to_db:
                metrics_data = {
                    'symbol': symbol,
                    'timestamp': normalized['timestamp'],
                    'price_24h_change': normalized['price_24h_change'],
                    'volume_24h': normalized['volume_24h'],
                    'high_24h': normalized['high_24h'],
                    'low_24h': normalized['low_24h']
                }
                self.repository.save_market_metrics(metrics_data)
                self.stats['db_writes'] += 1
            
            # Publish event
            if self.publish_events:
                event = self.normalizer.to_market_data_event(normalized, 'ticker')
                self.event_bus.publish(event)
                self.stats['events_published'] += 1
            
        except Exception as e:
            logger.error(f"Error handling ticker data: {e}")
            self.stats['errors'] += 1
    
    async def _handle_mark_price_data(self, msg: Dict, stream_info: Dict):
        """Handle incoming mark price and funding rate data"""
        try:
            symbol = stream_info['symbol']
            
            # Normalize data
            normalized = self.normalizer.normalize_mark_price(msg, symbol)
            
            # Store as market metrics
            if self.store_to_db:
                metrics_data = {
                    'symbol': symbol,
                    'timestamp': normalized['timestamp'],
                    'mark_price': normalized['mark_price'],
                    'index_price': normalized['index_price'],
                    'funding_rate': normalized['funding_rate']
                }
                self.repository.save_market_metrics(metrics_data)
                self.stats['db_writes'] += 1
            
            # Publish event
            if self.publish_events:
                event = self.normalizer.to_market_data_event(normalized, 'mark_price')
                self.event_bus.publish(event)
                self.stats['events_published'] += 1
            
        except Exception as e:
            logger.error(f"Error handling mark price data: {e}")
            self.stats['errors'] += 1
    
    async def _load_symbol_info(self):
        """Load and store symbol information from exchange"""
        try:
            exchange_info = await self.client.get_exchange_info()
            
            for symbol_data in exchange_info.get('symbols', []):
                if symbol_data['status'] == 'TRADING':
                    normalized = self.normalizer.normalize_symbol_info(symbol_data)
                    self.repository.save_symbol_info(normalized)
            
            logger.info(f"Loaded {len(exchange_info.get('symbols', []))} symbol info")
            
        except Exception as e:
            logger.error(f"Failed to load symbol info: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'subscribed_symbols': list(self.subscribed_symbols),
            'active_streams': len(self.client.active_streams)
        }