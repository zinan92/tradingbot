"""
Example usage of the Market Data Infrastructure

This module demonstrates how to integrate and use the market data components.
"""

import asyncio
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.market_data.market_data_service import MarketDataService
from src.infrastructure.indicators.indicator_service import IndicatorService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.postgres.market_data_tables import Base
from src.domain.shared.contracts.core_events import MarketDataReceived, IndicatorCalculated

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MarketDataPipeline:
    """
    Complete market data pipeline integrating all components
    """
    
    def __init__(self, database_url: str, api_key: str = None, api_secret: str = None):
        # Database setup
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db_session = Session()
        
        # Event bus setup
        self.event_bus = InMemoryEventBus()
        
        # Services setup
        self.market_data_service = MarketDataService(
            db_session=self.db_session,
            event_bus=self.event_bus,
            api_key=api_key,
            api_secret=api_secret
        )
        
        self.indicator_service = IndicatorService(
            db_session=self.db_session,
            event_bus=self.event_bus
        )
        
        # Subscribe to events
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """Setup event handlers for the pipeline"""
        
        # Handle market data events
        def handle_market_data(event: MarketDataReceived):
            logger.info(f"Market data received: {event.symbol} @ {event.price}")
        
        # Handle indicator events
        def handle_indicator(event: IndicatorCalculated):
            logger.info(f"Indicator calculated: {event.symbol} {event.indicator_name} = {event.value}")
        
        self.event_bus.subscribe('MarketDataReceived', handle_market_data)
        self.event_bus.subscribe('IndicatorCalculated', handle_indicator)
    
    async def start(self):
        """Start the market data pipeline"""
        logger.info("Starting market data pipeline...")
        
        # Start services
        await self.market_data_service.start()
        
        logger.info("Market data pipeline started successfully")
    
    async def stop(self):
        """Stop the market data pipeline"""
        logger.info("Stopping market data pipeline...")
        
        # Stop services
        await self.market_data_service.stop()
        await self.indicator_service.stop()
        
        # Close database
        self.db_session.close()
        self.engine.dispose()
        
        logger.info("Market data pipeline stopped")
    
    async def subscribe_to_symbol(self, symbol: str, intervals: list = None):
        """
        Subscribe to market data and indicators for a symbol
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            intervals: Timeframes for indicators (e.g., ['1m', '5m', '15m'])
        """
        if intervals is None:
            intervals = ['1m', '5m', '15m']
        
        # Subscribe to market data streams
        await self.market_data_service.subscribe_symbol(
            symbol=symbol,
            data_types=['kline', 'depth', 'trade', 'ticker'],
            interval='1m'
        )
        
        # Start periodic indicator calculation
        for interval in intervals:
            await self.indicator_service.start_periodic_calculation(
                symbol=symbol,
                interval=interval,
                calculate_every=60  # Calculate every minute
            )
        
        logger.info(f"Subscribed to {symbol} with intervals {intervals}")
    
    async def load_historical_data(self, symbol: str, days_back: int = 7):
        """
        Load historical data for backtesting
        
        Args:
            symbol: Trading pair
            days_back: Number of days of historical data to load
        """
        logger.info(f"Loading {days_back} days of historical data for {symbol}")
        
        count = await self.market_data_service.load_historical_data(
            symbol=symbol,
            interval='1m',
            days_back=days_back
        )
        
        # Calculate indicators on historical data
        await self.indicator_service.calculate_and_publish(symbol, '1m')
        await self.indicator_service.calculate_and_publish(symbol, '5m')
        await self.indicator_service.calculate_and_publish(symbol, '15m')
        
        logger.info(f"Loaded {count} historical klines and calculated indicators")
    
    def get_latest_market_data(self, symbol: str):
        """Get latest market data for a symbol"""
        latest_kline = self.market_data_service.repository.get_latest_kline(symbol, '1m')
        latest_metrics = self.market_data_service.repository.get_latest_metrics(symbol)
        latest_orderbook = self.market_data_service.repository.get_latest_orderbook(symbol)
        
        return {
            'kline': {
                'close': latest_kline.close_price if latest_kline else None,
                'volume': latest_kline.volume if latest_kline else None,
                'time': latest_kline.close_time if latest_kline else None
            },
            'metrics': {
                'volume_24h': latest_metrics.volume_24h if latest_metrics else None,
                'funding_rate': latest_metrics.funding_rate if latest_metrics else None
            },
            'orderbook': {
                'best_bid': latest_orderbook.best_bid_price if latest_orderbook else None,
                'best_ask': latest_orderbook.best_ask_price if latest_orderbook else None,
                'spread': latest_orderbook.spread if latest_orderbook else None
            }
        }
    
    def get_latest_indicators(self, symbol: str, timeframe: str = '1m'):
        """Get latest indicator values for a symbol"""
        return self.indicator_service.get_latest_indicators(symbol, timeframe)
    
    def get_stats(self):
        """Get pipeline statistics"""
        return {
            'market_data': self.market_data_service.get_stats(),
            'indicators': self.indicator_service.get_stats()
        }


async def main():
    """
    Example usage of the market data pipeline
    """
    # Configuration
    DATABASE_URL = "postgresql://user:password@localhost/tradingbot"
    API_KEY = None  # Optional: Add your Binance API key
    API_SECRET = None  # Optional: Add your Binance API secret
    
    # Create pipeline
    pipeline = MarketDataPipeline(
        database_url=DATABASE_URL,
        api_key=API_KEY,
        api_secret=API_SECRET
    )
    
    try:
        # Start pipeline
        await pipeline.start()
        
        # Load historical data for backtesting
        await pipeline.load_historical_data('BTCUSDT', days_back=7)
        
        # Subscribe to real-time data
        await pipeline.subscribe_to_symbol('BTCUSDT', intervals=['1m', '5m', '15m'])
        await pipeline.subscribe_to_symbol('ETHUSDT', intervals=['1m', '5m'])
        
        # Run for a while
        for i in range(60):  # Run for 60 seconds
            await asyncio.sleep(1)
            
            # Get and print latest data every 10 seconds
            if i % 10 == 0:
                btc_data = pipeline.get_latest_market_data('BTCUSDT')
                btc_indicators = pipeline.get_latest_indicators('BTCUSDT', '1m')
                
                logger.info(f"BTC Price: ${btc_data['kline']['close']}")
                logger.info(f"BTC Indicators: RSI={btc_indicators.get('rsi', {}).get('value')}")
        
        # Print statistics
        stats = pipeline.get_stats()
        logger.info(f"Pipeline stats: {stats}")
        
    finally:
        # Clean shutdown
        await pipeline.stop()


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())