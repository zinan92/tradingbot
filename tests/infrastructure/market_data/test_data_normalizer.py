import pytest
from datetime import datetime
from decimal import Decimal
from src.infrastructure.market_data.data_normalizer import BinanceDataNormalizer
from src.domain.shared.contracts.core_events import MarketDataReceived, IndicatorCalculated

class TestBinanceDataNormalizer:
    
    def setup_method(self):
        self.normalizer = BinanceDataNormalizer()
    
    def test_normalize_kline(self):
        # Arrange
        raw_data = {
            'e': 'kline',
            'E': 1638360000000,
            's': 'BTCUSDT',
            'k': {
                't': 1638360000000,
                'T': 1638360059999,
                'i': '1m',
                'o': '57000.00',
                'c': '57100.00',
                'h': '57200.00',
                'l': '56900.00',
                'v': '100.5',
                'n': 1500,
                'x': True,
                'q': '5735000.00',
                'V': '50.2',
                'Q': '2867500.00'
            }
        }
        
        # Act
        result = self.normalizer.normalize_kline(raw_data, 'BTCUSDT', '1m')
        
        # Assert
        assert result['symbol'] == 'BTCUSDT'
        assert result['interval'] == '1m'
        assert result['open_price'] == 57000.00
        assert result['close_price'] == 57100.00
        assert result['high_price'] == 57200.00
        assert result['low_price'] == 56900.00
        assert result['volume'] == 100.5
        assert result['is_closed'] == True
        assert isinstance(result['open_time'], datetime)
    
    def test_normalize_historical_kline(self):
        # Arrange
        raw_kline = [
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
        
        # Act
        result = self.normalizer.normalize_historical_kline(raw_kline, 'BTCUSDT', '1h')
        
        # Assert
        assert result['symbol'] == 'BTCUSDT'
        assert result['interval'] == '1h'
        assert result['open_price'] == 0.01634790
        assert result['close_price'] == 0.01577100
        assert result['high_price'] == 0.80000000
        assert result['low_price'] == 0.01575800
        assert result['volume'] == 148976.11427815
        assert result['is_closed'] == True
    
    def test_normalize_depth(self):
        # Arrange
        raw_data = {
            'e': 'depthUpdate',
            'E': 1638360000000,
            's': 'BTCUSDT',
            'U': 123456789,
            'u': 123456790,
            'b': [['57000.00', '1.5'], ['56999.00', '2.0']],
            'a': [['57100.00', '2.0'], ['57101.00', '1.5']]
        }
        
        # Act
        result = self.normalizer.normalize_depth(raw_data, 'BTCUSDT')
        
        # Assert
        assert result['symbol'] == 'BTCUSDT'
        assert result['update_id'] == 123456790
        assert result['best_bid_price'] == 57000.00
        assert result['best_bid_qty'] == 1.5
        assert result['best_ask_price'] == 57100.00
        assert result['best_ask_qty'] == 2.0
        assert result['spread'] == 100.00
        assert len(result['bids']) == 2
        assert len(result['asks']) == 2
    
    def test_normalize_trade(self):
        # Arrange
        raw_data = {
            'e': 'trade',
            'E': 1638360000000,
            's': 'BTCUSDT',
            't': 12345,
            'p': '57000.00',
            'q': '0.1',
            'T': 1638360000000,
            'm': True
        }
        
        # Act
        result = self.normalizer.normalize_trade(raw_data, 'BTCUSDT')
        
        # Assert
        assert result['symbol'] == 'BTCUSDT'
        assert result['trade_id'] == 12345
        assert result['price'] == 57000.00
        assert result['quantity'] == 0.1
        assert result['quote_quantity'] == 5700.00
        assert result['is_buyer_maker'] == 1
    
    def test_normalize_ticker(self):
        # Arrange
        raw_data = {
            'e': '24hrTicker',
            's': 'BTCUSDT',
            'p': '100.00',
            'P': '0.18',
            'w': '57050.00',
            'c': '57100.00',
            'Q': '0.5',
            'o': '57000.00',
            'h': '57500.00',
            'l': '56500.00',
            'v': '10000',
            'q': '570000000',
            'n': 9901
        }
        
        # Act
        result = self.normalizer.normalize_ticker(raw_data, 'BTCUSDT')
        
        # Assert
        assert result['symbol'] == 'BTCUSDT'
        assert result['price_24h_change'] == 0.18
        assert result['volume_24h'] == 10000
        assert result['high_24h'] == 57500.00
        assert result['low_24h'] == 56500.00
        assert result['last_price'] == 57100.00
    
    def test_normalize_mark_price(self):
        # Arrange
        raw_data = {
            'e': 'markPriceUpdate',
            'E': 1638360000000,
            's': 'BTCUSDT',
            'p': '57050.00',
            'i': '57045.00',
            'P': '57060.00',
            'r': '0.0001',
            'T': 1638360000000
        }
        
        # Act
        result = self.normalizer.normalize_mark_price(raw_data, 'BTCUSDT')
        
        # Assert
        assert result['symbol'] == 'BTCUSDT'
        assert result['mark_price'] == 57050.00
        assert result['index_price'] == 57045.00
        assert result['funding_rate'] == 0.0001
        assert result['estimated_settle_price'] == 57060.00
    
    def test_to_market_data_event(self):
        # Arrange
        normalized_data = {
            'symbol': 'BTCUSDT',
            'close_price': 57100.00,
            'volume': 100.5,
            'close_time': datetime.now()
        }
        
        # Act
        event = self.normalizer.to_market_data_event(normalized_data, 'kline')
        
        # Assert
        assert isinstance(event, MarketDataReceived)
        assert event.symbol == 'BTCUSDT'
        assert event.price == Decimal('57100.00')
        assert event.volume == 100
        assert event.source_context == 'market_data'
    
    def test_to_indicator_event(self):
        # Arrange
        symbol = 'BTCUSDT'
        indicator_name = 'RSI'
        value = 65.5
        timestamp = datetime.now()
        
        # Act
        event = self.normalizer.to_indicator_event(symbol, indicator_name, value, timestamp)
        
        # Assert
        assert isinstance(event, IndicatorCalculated)
        assert event.symbol == 'BTCUSDT'
        assert event.indicator_name == 'RSI'
        assert event.value == Decimal('65.5')
        assert event.timestamp == timestamp
        assert event.source_context == 'indicators'