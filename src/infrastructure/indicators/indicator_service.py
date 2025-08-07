import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import pandas as pd

from .indicator_calculator import IndicatorCalculator
from ..persistence.postgres.market_data_repository import MarketDataRepository
from ..market_data.data_normalizer import BinanceDataNormalizer
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)

class IndicatorService:
    def __init__(self,
                 db_session: Session,
                 event_bus: InMemoryEventBus):
        self.db_session = db_session
        self.event_bus = event_bus
        self.repository = MarketDataRepository(db_session)
        self.calculator = IndicatorCalculator()
        self.normalizer = BinanceDataNormalizer()
        
        # Configuration
        self.calculation_intervals = ['1m', '5m', '15m', '1h', '4h', '1d']
        self.enabled_indicators = [
            'rsi', 'macd', 'bb_upper', 'bb_lower', 'sma_20', 'sma_50',
            'ema_12', 'ema_26', 'atr', 'adx', 'obv', 'vwap'
        ]
        
        # Tracking
        self.last_calculation: Dict[str, Dict[str, datetime]] = {}
        self.calculation_tasks: Dict[str, asyncio.Task] = {}
        
        # Stats
        self.stats = {
            'calculations_performed': 0,
            'events_published': 0,
            'errors': 0
        }
    
    async def start_periodic_calculation(self, 
                                        symbol: str,
                                        interval: str = '1m',
                                        calculate_every: int = 60):
        """
        Start periodic indicator calculation for a symbol
        
        Args:
            symbol: Trading pair symbol
            interval: Timeframe for calculation
            calculate_every: Seconds between calculations
        """
        task_id = f"{symbol}_{interval}"
        
        if task_id in self.calculation_tasks:
            logger.warning(f"Already calculating indicators for {task_id}")
            return
        
        async def periodic_task():
            while True:
                try:
                    await self.calculate_and_publish(symbol, interval)
                    await asyncio.sleep(calculate_every)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in periodic calculation for {task_id}: {e}")
                    self.stats['errors'] += 1
                    await asyncio.sleep(calculate_every)
        
        task = asyncio.create_task(periodic_task())
        self.calculation_tasks[task_id] = task
        logger.info(f"Started periodic indicator calculation for {task_id}")
    
    async def stop_periodic_calculation(self, symbol: str, interval: str = '1m'):
        """Stop periodic indicator calculation for a symbol"""
        task_id = f"{symbol}_{interval}"
        
        if task_id in self.calculation_tasks:
            self.calculation_tasks[task_id].cancel()
            del self.calculation_tasks[task_id]
            logger.info(f"Stopped periodic indicator calculation for {task_id}")
    
    async def calculate_and_publish(self, 
                                   symbol: str,
                                   interval: str,
                                   lookback_periods: int = 200) -> Dict[str, float]:
        """
        Calculate indicators and publish events
        
        Args:
            symbol: Trading pair symbol
            interval: Timeframe for calculation
            lookback_periods: Number of periods to look back
        
        Returns:
            Dictionary of latest indicator values
        """
        try:
            # Get historical klines from database
            klines = self.repository.get_klines(
                symbol=symbol,
                interval=interval,
                limit=lookback_periods
            )
            
            if len(klines) < 50:
                logger.warning(f"Insufficient data for {symbol} {interval}: {len(klines)} klines")
                return {}
            
            # Convert to DataFrame
            kline_data = [
                {
                    'open_price': k.open_price,
                    'high_price': k.high_price,
                    'low_price': k.low_price,
                    'close_price': k.close_price,
                    'volume': k.volume,
                    'open_time': k.open_time
                }
                for k in reversed(klines)  # Reverse to get chronological order
            ]
            
            df = self.calculator.prepare_dataframe(kline_data)
            
            # Calculate all indicators
            indicators = self.calculator.calculate_all_indicators(df)
            
            # Get latest values
            latest_values = self.calculator.get_latest_indicators(df)
            latest_time = df.index[-1]
            
            # Store and publish selected indicators
            for indicator_name in self.enabled_indicators:
                if indicator_name in latest_values:
                    value = latest_values[indicator_name]
                    
                    # Store in database
                    indicator_data = {
                        'symbol': symbol,
                        'indicator_name': indicator_name,
                        'timeframe': interval,
                        'timestamp': latest_time,
                        'value': value,
                        'parameters': self._get_indicator_parameters(indicator_name)
                    }
                    
                    # Add additional values for complex indicators
                    if indicator_name == 'macd':
                        indicator_data['additional_values'] = {
                            'signal': latest_values.get('macd_signal'),
                            'histogram': latest_values.get('macd_histogram')
                        }
                    
                    self.repository.save_indicator_value(indicator_data)
                    
                    # Publish event
                    event = self.normalizer.to_indicator_event(
                        symbol=symbol,
                        indicator_name=indicator_name,
                        value=value,
                        timestamp=latest_time
                    )
                    self.event_bus.publish(event)
                    self.stats['events_published'] += 1
            
            # Update tracking
            if symbol not in self.last_calculation:
                self.last_calculation[symbol] = {}
            self.last_calculation[symbol][interval] = datetime.now()
            
            self.stats['calculations_performed'] += 1
            
            logger.debug(f"Calculated {len(latest_values)} indicators for {symbol} {interval}")
            return latest_values
            
        except Exception as e:
            logger.error(f"Error calculating indicators for {symbol} {interval}: {e}")
            self.stats['errors'] += 1
            raise
    
    async def calculate_on_new_data(self, market_data_event: Any):
        """
        Calculate indicators when new market data is received
        
        Args:
            market_data_event: MarketDataReceived event
        """
        try:
            symbol = market_data_event.symbol
            
            # Check if we should calculate (e.g., every minute)
            if symbol in self.last_calculation:
                for interval in ['1m', '5m', '15m']:
                    last_calc = self.last_calculation[symbol].get(interval)
                    if not last_calc or (datetime.now() - last_calc).seconds > 60:
                        await self.calculate_and_publish(symbol, interval)
            else:
                # First calculation for this symbol
                for interval in ['1m', '5m', '15m']:
                    await self.calculate_and_publish(symbol, interval)
                    
        except Exception as e:
            logger.error(f"Error in calculate_on_new_data: {e}")
            self.stats['errors'] += 1
    
    def get_latest_indicators(self, 
                            symbol: str,
                            timeframe: str = '1m') -> Dict[str, Any]:
        """
        Get latest indicator values from database
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe for indicators
        
        Returns:
            Dictionary of latest indicator values
        """
        try:
            latest_indicators = {}
            
            for indicator_name in self.enabled_indicators:
                indicator = self.repository.get_latest_indicator(
                    symbol=symbol,
                    indicator_name=indicator_name,
                    timeframe=timeframe
                )
                
                if indicator:
                    latest_indicators[indicator_name] = {
                        'value': indicator.value,
                        'timestamp': indicator.timestamp,
                        'parameters': indicator.parameters_dict,
                        'additional': indicator.additional_values_dict
                    }
            
            return latest_indicators
            
        except Exception as e:
            logger.error(f"Error getting latest indicators: {e}")
            return {}
    
    def get_indicator_history(self,
                            symbol: str,
                            indicator_name: str,
                            timeframe: str = '1m',
                            periods: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical indicator values
        
        Args:
            symbol: Trading pair symbol
            indicator_name: Name of the indicator
            timeframe: Timeframe for indicators
            periods: Number of periods to retrieve
        
        Returns:
            List of indicator values
        """
        try:
            indicators = self.repository.get_indicator_values(
                symbol=symbol,
                indicator_name=indicator_name,
                timeframe=timeframe,
                limit=periods
            )
            
            return [
                {
                    'timestamp': ind.timestamp,
                    'value': ind.value,
                    'parameters': ind.parameters_dict,
                    'additional': ind.additional_values_dict
                }
                for ind in reversed(indicators)  # Return in chronological order
            ]
            
        except Exception as e:
            logger.error(f"Error getting indicator history: {e}")
            return []
    
    def _get_indicator_parameters(self, indicator_name: str) -> Dict[str, Any]:
        """Get default parameters for an indicator"""
        parameters = {
            'rsi': {'period': 14},
            'macd': {'fast': 12, 'slow': 26, 'signal': 9},
            'bb_upper': {'period': 20, 'std': 2},
            'bb_lower': {'period': 20, 'std': 2},
            'sma_20': {'period': 20},
            'sma_50': {'period': 50},
            'ema_12': {'period': 12},
            'ema_26': {'period': 26},
            'atr': {'period': 14},
            'adx': {'period': 14},
            'stoch_k': {'k_period': 14, 'd_period': 3},
            'cci': {'period': 20},
            'williams_r': {'period': 14}
        }
        
        return parameters.get(indicator_name, {})
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'active_calculations': list(self.calculation_tasks.keys()),
            'last_calculations': {
                symbol: {
                    interval: last.isoformat() if last else None
                    for interval, last in intervals.items()
                }
                for symbol, intervals in self.last_calculation.items()
            }
        }
    
    async def stop(self):
        """Stop all periodic calculations"""
        for task in self.calculation_tasks.values():
            task.cancel()
        
        # Wait for all tasks to complete
        if self.calculation_tasks:
            await asyncio.gather(*self.calculation_tasks.values(), return_exceptions=True)
        
        self.calculation_tasks.clear()
        logger.info(f"Indicator service stopped. Stats: {self.stats}")