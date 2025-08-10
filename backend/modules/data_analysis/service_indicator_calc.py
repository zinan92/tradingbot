import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import pandas as pd

from .core_indicators import IndicatorCalculator
# These imports will be replaced with port interfaces
# from ..persistence.postgres.market_data_repository import MarketDataRepository
# from ..market_data.data_normalizer import BinanceDataNormalizer
# from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

logger = logging.getLogger(__name__)

class IndicatorService:
    def __init__(self,
                 db_session: Session = None,
                 event_bus = None):
        self.db_session = db_session
        self.event_bus = event_bus
        # Repository and normalizer will be injected via DI container
        self.repository = None  # MarketDataRepository(db_session)
        self.calculator = IndicatorCalculator()
        self.normalizer = None  # BinanceDataNormalizer()
        
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
    
    async def batch_calculate_historical(self,
                                        symbols: List[str],
                                        intervals: List[str],
                                        start_date: datetime,
                                        end_date: Optional[datetime] = None,
                                        batch_size: int = 1000,
                                        parallel_workers: int = 4) -> Dict[str, Any]:
        """
        Batch calculate indicators for historical data
        
        Args:
            symbols: List of trading symbols
            intervals: List of time intervals
            start_date: Start date for calculations
            end_date: End date (default: now)
            batch_size: Number of candles to process at once
            parallel_workers: Number of parallel calculation workers
            
        Returns:
            Calculation statistics
        """
        if end_date is None:
            end_date = datetime.now()
        
        total_tasks = len(symbols) * len(intervals)
        logger.info(f"Starting batch calculation for {total_tasks} symbol/interval combinations")
        
        # Create calculation tasks
        calc_tasks = []
        for symbol in symbols:
            for interval in intervals:
                calc_tasks.append({
                    'symbol': symbol,
                    'interval': interval,
                    'start_date': start_date,
                    'end_date': end_date
                })
        
        # Process with worker pool
        semaphore = asyncio.Semaphore(parallel_workers)
        results = []
        
        async def calculate_with_semaphore(task):
            async with semaphore:
                return await self._batch_calculate_single(
                    task['symbol'],
                    task['interval'],
                    task['start_date'],
                    task['end_date'],
                    batch_size
                )
        
        # Execute calculations
        from tqdm.asyncio import tqdm
        
        with tqdm(total=total_tasks, desc="Calculating indicators") as pbar:
            tasks = [calculate_with_semaphore(task) for task in calc_tasks]
            
            for future in asyncio.as_completed(tasks):
                result = await future
                results.append(result)
                pbar.update(1)
                
                if result['success']:
                    pbar.set_description(
                        f"Calculated {result['symbol']} {result['interval']} "
                        f"({result['indicators_calculated']} indicators)"
                    )
        
        # Compile statistics
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        stats = {
            'total_tasks': total_tasks,
            'successful': len(successful),
            'failed': len(failed),
            'total_indicators': sum(r['indicators_calculated'] for r in successful),
            'total_time': sum(r.get('calculation_time', 0) for r in results),
            'failed_tasks': [
                f"{r['symbol']}_{r['interval']}: {r.get('error', 'Unknown error')}"
                for r in failed
            ]
        }
        
        logger.info(f"Batch calculation complete: {stats['successful']}/{stats['total_tasks']} successful")
        logger.info(f"Total indicators calculated: {stats['total_indicators']:,}")
        
        if stats['failed'] > 0:
            logger.warning(f"Failed calculations: {stats['failed_tasks']}")
        
        return stats
    
    async def _batch_calculate_single(self,
                                     symbol: str,
                                     interval: str,
                                     start_date: datetime,
                                     end_date: datetime,
                                     batch_size: int) -> Dict[str, Any]:
        """
        Calculate indicators for a single symbol/interval in batches
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_date: Start date
            end_date: End date
            batch_size: Batch size for processing
            
        Returns:
            Calculation result
        """
        import time
        start_time = time.time()
        
        try:
            # Get all klines for the period
            all_klines = []
            current_start = start_date
            
            while current_start < end_date:
                batch_end = min(current_start + timedelta(days=30), end_date)
                
                klines = self.repository.get_klines(
                    symbol=symbol,
                    interval=interval,
                    start_time=current_start,
                    end_time=batch_end,
                    limit=batch_size * 10  # Get more at once
                )
                
                if klines:
                    all_klines.extend(klines)
                
                current_start = batch_end
            
            if len(all_klines) < 50:
                logger.warning(f"Insufficient data for {symbol} {interval}: {len(all_klines)} klines")
                return {
                    'success': False,
                    'symbol': symbol,
                    'interval': interval,
                    'error': 'Insufficient data',
                    'indicators_calculated': 0
                }
            
            # Sort by time
            all_klines.sort(key=lambda k: k.open_time)
            
            # Process in sliding windows for efficient calculation
            indicators_saved = 0
            window_size = min(1000, len(all_klines))  # Use last 1000 candles for calculation
            step_size = 100  # Calculate every 100 candles
            
            for i in range(window_size, len(all_klines) + 1, step_size):
                window_klines = all_klines[max(0, i - window_size):i]
                
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
                    for k in window_klines
                ]
                
                df = self.calculator.prepare_dataframe(kline_data)
                
                # Calculate indicators
                indicators = self.calculator.calculate_all_indicators(df)
                
                # Save the latest values for this batch
                latest_time = df.index[-1]
                latest_values = self.calculator.get_latest_indicators(df)
                
                for indicator_name in self.enabled_indicators:
                    if indicator_name in latest_values:
                        value = latest_values[indicator_name]
                        
                        # Check if this indicator already exists
                        existing = self.repository.get_indicator_values(
                            symbol=symbol,
                            indicator_name=indicator_name,
                            timeframe=interval,
                            start_time=latest_time,
                            limit=1
                        )
                        
                        if not existing or existing[0].timestamp != latest_time:
                            # Save indicator
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
                            indicators_saved += 1
            
            # Commit all indicators
            self.db_session.commit()
            
            calculation_time = time.time() - start_time
            
            logger.debug(f"Calculated {indicators_saved} indicators for {symbol} {interval} in {calculation_time:.2f}s")
            
            return {
                'success': True,
                'symbol': symbol,
                'interval': interval,
                'indicators_calculated': indicators_saved,
                'klines_processed': len(all_klines),
                'calculation_time': calculation_time
            }
            
        except Exception as e:
            logger.error(f"Error in batch calculation for {symbol} {interval}: {e}")
            return {
                'success': False,
                'symbol': symbol,
                'interval': interval,
                'error': str(e),
                'indicators_calculated': 0,
                'calculation_time': time.time() - start_time
            }
    
    async def recalculate_all_indicators(self,
                                        symbol: str,
                                        interval: str,
                                        lookback_days: int = 30) -> Dict[str, int]:
        """
        Recalculate all indicators for a symbol/interval
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            lookback_days: Number of days to recalculate
            
        Returns:
            Dictionary with counts of recalculated indicators
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            
            # Delete existing indicators in this range
            from ..persistence.postgres.market_data_tables import IndicatorValue
            
            deleted = self.db_session.query(IndicatorValue).filter(
                IndicatorValue.symbol == symbol,
                IndicatorValue.timeframe == interval,
                IndicatorValue.timestamp >= start_date,
                IndicatorValue.timestamp <= end_date
            ).delete()
            
            self.db_session.commit()
            
            logger.info(f"Deleted {deleted} existing indicators for {symbol} {interval}")
            
            # Recalculate
            result = await self._batch_calculate_single(
                symbol, interval, start_date, end_date, 1000
            )
            
            return {
                'deleted': deleted,
                'recalculated': result['indicators_calculated'] if result['success'] else 0,
                'success': result['success']
            }
            
        except Exception as e:
            logger.error(f"Error recalculating indicators: {e}")
            self.db_session.rollback()
            return {'deleted': 0, 'recalculated': 0, 'success': False}
    
    async def stop(self):
        """Stop all periodic calculations"""
        for task in self.calculation_tasks.values():
            task.cancel()
        
        # Wait for all tasks to complete
        if self.calculation_tasks:
            await asyncio.gather(*self.calculation_tasks.values(), return_exceptions=True)
        
        self.calculation_tasks.clear()
        logger.info(f"Indicator service stopped. Stats: {self.stats}")