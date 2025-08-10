from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
import uuid
import logging

from src.domain.shared.contracts.core_events import MarketDataReceived, IndicatorCalculated

logger = logging.getLogger(__name__)

class BinanceDataNormalizer:
    
    @staticmethod
    def normalize_kline(raw_data: Dict[str, Any], symbol: str, interval: str) -> Dict[str, Any]:
        """
        Normalize Binance kline data to internal format
        
        Raw Binance kline format:
        {
            'e': 'kline',
            'E': 1638360000000,  # Event time
            's': 'BTCUSDT',      # Symbol
            'k': {
                't': 1638360000000,  # Kline start time
                'T': 1638360059999,  # Kline close time
                'i': '1m',           # Interval
                'o': '57000.00',     # Open price
                'c': '57100.00',     # Close price
                'h': '57200.00',     # High price
                'l': '56900.00',     # Low price
                'v': '100.5',        # Base asset volume
                'n': 1500,           # Number of trades
                'x': False,          # Is this kline closed?
                'q': '5735000.00',   # Quote asset volume
                'V': '50.2',         # Taker buy base asset volume
                'Q': '2867500.00'    # Taker buy quote asset volume
            }
        }
        """
        try:
            kline = raw_data.get('k', {})
            
            return {
                'symbol': symbol.upper(),
                'interval': interval,
                'open_time': datetime.fromtimestamp(kline['t'] / 1000),
                'close_time': datetime.fromtimestamp(kline['T'] / 1000),
                'open_price': float(kline['o']),
                'high_price': float(kline['h']),
                'low_price': float(kline['l']),
                'close_price': float(kline['c']),
                'volume': float(kline['v']),
                'quote_volume': float(kline['q']),
                'number_of_trades': int(kline['n']),
                'taker_buy_base_volume': float(kline['V']),
                'taker_buy_quote_volume': float(kline['Q']),
                'is_closed': kline['x']
            }
        except Exception as e:
            logger.error(f"Error normalizing kline data: {e}")
            raise
    
    @staticmethod
    def normalize_historical_kline(raw_kline: List, symbol: str, interval: str) -> Dict[str, Any]:
        """
        Normalize historical kline data from REST API
        
        Format: [
            1499040000000,      # Open time
            "0.01634790",       # Open
            "0.80000000",       # High
            "0.01575800",       # Low
            "0.01577100",       # Close
            "148976.11427815",  # Volume
            1499644799999,      # Close time
            "2434.19055334",    # Quote asset volume
            308,                # Number of trades
            "1756.87402397",    # Taker buy base asset volume
            "28.46694368",      # Taker buy quote asset volume
            "0"                 # Ignore
        ]
        """
        try:
            return {
                'symbol': symbol.upper(),
                'interval': interval,
                'open_time': datetime.fromtimestamp(raw_kline[0] / 1000),
                'close_time': datetime.fromtimestamp(raw_kline[6] / 1000),
                'open_price': float(raw_kline[1]),
                'high_price': float(raw_kline[2]),
                'low_price': float(raw_kline[3]),
                'close_price': float(raw_kline[4]),
                'volume': float(raw_kline[5]),
                'quote_volume': float(raw_kline[7]),
                'number_of_trades': int(raw_kline[8]),
                'taker_buy_base_volume': float(raw_kline[9]),
                'taker_buy_quote_volume': float(raw_kline[10]),
                'is_closed': True
            }
        except Exception as e:
            logger.error(f"Error normalizing historical kline: {e}")
            raise
    
    @staticmethod
    def normalize_depth(raw_data: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """
        Normalize Binance order book depth data
        
        Format:
        {
            'e': 'depthUpdate',
            'E': 1638360000000,
            's': 'BTCUSDT',
            'U': 123456789,     # First update ID
            'u': 123456790,     # Final update ID
            'b': [['57000.00', '1.5'], ...],  # Bids
            'a': [['57100.00', '2.0'], ...]   # Asks
        }
        """
        try:
            bids = [[float(price), float(qty)] for price, qty in raw_data.get('b', [])]
            asks = [[float(price), float(qty)] for price, qty in raw_data.get('a', [])]
            
            best_bid = bids[0] if bids else [0, 0]
            best_ask = asks[0] if asks else [0, 0]
            spread = best_ask[0] - best_bid[0] if best_bid[0] and best_ask[0] else 0
            
            return {
                'symbol': symbol.upper(),
                'timestamp': datetime.fromtimestamp(raw_data.get('E', 0) / 1000),
                'update_id': raw_data.get('u', 0),
                'bids': bids,
                'asks': asks,
                'best_bid_price': best_bid[0],
                'best_bid_qty': best_bid[1],
                'best_ask_price': best_ask[0],
                'best_ask_qty': best_ask[1],
                'spread': spread
            }
        except Exception as e:
            logger.error(f"Error normalizing depth data: {e}")
            raise
    
    @staticmethod
    def normalize_trade(raw_data: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """
        Normalize Binance trade data
        
        Format:
        {
            'e': 'trade',
            'E': 1638360000000,
            's': 'BTCUSDT',
            't': 12345,         # Trade ID
            'p': '57000.00',    # Price
            'q': '0.1',         # Quantity
            'T': 1638360000000, # Trade time
            'm': True           # Is buyer the maker?
        }
        """
        try:
            price = float(raw_data['p'])
            quantity = float(raw_data['q'])
            
            return {
                'symbol': symbol.upper(),
                'trade_id': raw_data['t'],
                'price': price,
                'quantity': quantity,
                'quote_quantity': price * quantity,
                'timestamp': datetime.fromtimestamp(raw_data['T'] / 1000),
                'is_buyer_maker': 1 if raw_data.get('m', False) else 0
            }
        except Exception as e:
            logger.error(f"Error normalizing trade data: {e}")
            raise
    
    @staticmethod
    def normalize_ticker(raw_data: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """
        Normalize Binance 24hr ticker data
        
        Format:
        {
            'e': '24hrTicker',
            's': 'BTCUSDT',
            'p': '100.00',      # Price change
            'P': '0.18',        # Price change percent
            'w': '57050.00',    # Weighted average price
            'c': '57100.00',    # Last price
            'Q': '0.5',         # Last quantity
            'o': '57000.00',    # Open price
            'h': '57500.00',    # High price
            'l': '56500.00',    # Low price
            'v': '10000',       # Total traded base asset volume
            'q': '570000000',   # Total traded quote asset volume
            'O': 1638273600000, # Statistics open time
            'C': 1638360000000, # Statistics close time
            'F': 100,           # First trade ID
            'L': 10000,         # Last trade ID
            'n': 9901           # Total number of trades
        }
        """
        try:
            return {
                'symbol': symbol.upper(),
                'timestamp': datetime.now(),
                'price_24h_change': float(raw_data.get('P', 0)),
                'volume_24h': float(raw_data.get('v', 0)),
                'high_24h': float(raw_data.get('h', 0)),
                'low_24h': float(raw_data.get('l', 0)),
                'last_price': float(raw_data.get('c', 0)),
                'open_price_24h': float(raw_data.get('o', 0)),
                'weighted_avg_price': float(raw_data.get('w', 0)),
                'quote_volume_24h': float(raw_data.get('q', 0)),
                'trade_count_24h': int(raw_data.get('n', 0))
            }
        except Exception as e:
            logger.error(f"Error normalizing ticker data: {e}")
            raise
    
    @staticmethod
    def normalize_mark_price(raw_data: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """
        Normalize Binance mark price and funding rate data
        
        Format:
        {
            'e': 'markPriceUpdate',
            'E': 1638360000000,
            's': 'BTCUSDT',
            'p': '57050.00',    # Mark price
            'i': '57045.00',    # Index price
            'P': '57060.00',    # Estimated settle price
            'r': '0.0001',      # Funding rate
            'T': 1638360000000  # Next funding time
        }
        """
        try:
            return {
                'symbol': symbol.upper(),
                'timestamp': datetime.fromtimestamp(raw_data.get('E', 0) / 1000),
                'mark_price': float(raw_data.get('p', 0)),
                'index_price': float(raw_data.get('i', 0)),
                'funding_rate': float(raw_data.get('r', 0)),
                'next_funding_time': datetime.fromtimestamp(raw_data.get('T', 0) / 1000) if raw_data.get('T') else None,
                'estimated_settle_price': float(raw_data.get('P', 0)) if raw_data.get('P') else None
            }
        except Exception as e:
            logger.error(f"Error normalizing mark price data: {e}")
            raise
    
    @staticmethod
    def normalize_symbol_info(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Binance symbol information from exchange info
        """
        try:
            # Extract precision and filters
            price_precision = raw_data.get('pricePrecision', 8)
            quantity_precision = raw_data.get('quantityPrecision', 8)
            
            filters = {f['filterType']: f for f in raw_data.get('filters', [])}
            
            lot_size = filters.get('LOT_SIZE', {})
            min_notional = filters.get('MIN_NOTIONAL', {})
            
            return {
                'symbol': raw_data['symbol'],
                'base_asset': raw_data.get('baseAsset', ''),
                'quote_asset': raw_data.get('quoteAsset', ''),
                'price_precision': price_precision,
                'quantity_precision': quantity_precision,
                'min_quantity': float(lot_size.get('minQty', 0)),
                'max_quantity': float(lot_size.get('maxQty', 0)),
                'step_size': float(lot_size.get('stepSize', 0)),
                'min_notional': float(min_notional.get('notional', 0)),
                'contract_type': raw_data.get('contractType', 'PERPETUAL'),
                'status': raw_data.get('status', 'TRADING'),
                'listed_at': datetime.fromtimestamp(raw_data['onboardDate'] / 1000) if raw_data.get('onboardDate') else None
            }
        except Exception as e:
            logger.error(f"Error normalizing symbol info: {e}")
            raise
    
    @staticmethod
    def to_market_data_event(normalized_data: Dict[str, Any], data_type: str) -> MarketDataReceived:
        """
        Convert normalized data to MarketDataReceived domain event
        """
        try:
            # Extract key fields based on data type
            if data_type == 'kline':
                price = Decimal(str(normalized_data['close_price']))
                volume = normalized_data['volume']
                timestamp = normalized_data['close_time']
            elif data_type == 'trade':
                price = Decimal(str(normalized_data['price']))
                volume = normalized_data['quantity']
                timestamp = normalized_data['timestamp']
            elif data_type == 'ticker':
                price = Decimal(str(normalized_data['last_price']))
                volume = normalized_data['volume_24h']
                timestamp = normalized_data['timestamp']
            elif data_type == 'mark_price':
                price = Decimal(str(normalized_data['mark_price']))
                volume = 0  # Mark price doesn't have volume
                timestamp = normalized_data['timestamp']
            else:
                price = Decimal('0')
                volume = 0
                timestamp = datetime.now()
            
            return MarketDataReceived(
                event_id=str(uuid.uuid4()),
                occurred_at=datetime.now(),
                correlation_id=str(uuid.uuid4()),
                source_context='market_data',
                symbol=normalized_data['symbol'],
                price=price,
                volume=int(volume),
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"Error converting to MarketDataReceived event: {e}")
            raise
    
    @staticmethod
    def to_indicator_event(symbol: str, 
                          indicator_name: str,
                          value: float,
                          timestamp: datetime) -> IndicatorCalculated:
        """
        Create IndicatorCalculated domain event
        """
        return IndicatorCalculated(
            event_id=str(uuid.uuid4()),
            occurred_at=datetime.now(),
            correlation_id=str(uuid.uuid4()),
            source_context='indicators',
            symbol=symbol,
            indicator_name=indicator_name,
            value=Decimal(str(value)),
            timestamp=timestamp
        )