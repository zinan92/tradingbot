"""
Instrumented Components

Wrappers that add metrics to core system components.
"""
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from src.domain.shared.ports.market_data_port import MarketDataPort
from src.domain.shared.ports.indicator_port import IndicatorPort
from src.domain.shared.ports.backtest_port import BacktestPort
from src.domain.shared.ports.execution_port import ExecutionPort
from src.infrastructure.monitoring.metrics import system_metrics, Timer

logger = logging.getLogger(__name__)


class InstrumentedMarketDataPort(MarketDataPort):
    """Market data port with metrics instrumentation"""
    
    def __init__(self, wrapped_port: MarketDataPort):
        """
        Initialize instrumented port
        
        Args:
            wrapped_port: The actual market data port to wrap
        """
        self.wrapped_port = wrapped_port
        self._request_queue: List[float] = []
        self._max_queue_size = 1000
    
    async def get_candles(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> list:
        """Get candles with metrics"""
        labels = {
            'source': 'binance',
            'symbol': symbol,
            'interval': interval
        }
        
        # Track request
        system_metrics['data_ingestion_requests'].inc(labels=labels)
        
        # Update queue depth
        self._request_queue.append(time.time())
        # Clean old entries
        cutoff = time.time() - 60
        self._request_queue = [t for t in self._request_queue if t > cutoff]
        system_metrics['queue_depth'].set(
            len(self._request_queue),
            labels={'queue_name': 'market_data_requests'}
        )
        
        # Measure latency
        with Timer(system_metrics['data_ingestion_latency'], labels):
            try:
                result = await self.wrapped_port.get_candles(
                    symbol, interval, start_time, end_time, limit
                )
                return result
            except Exception as e:
                error_labels = {**labels, 'error_type': type(e).__name__}
                system_metrics['data_ingestion_errors'].inc(labels=error_labels)
                raise
    
    async def get_ticker(self, symbol: str) -> dict:
        """Get ticker with metrics"""
        labels = {
            'source': 'binance',
            'symbol': symbol,
            'interval': 'ticker'
        }
        
        system_metrics['data_ingestion_requests'].inc(labels=labels)
        
        with Timer(system_metrics['data_ingestion_latency'], labels):
            try:
                return await self.wrapped_port.get_ticker(symbol)
            except Exception as e:
                error_labels = {**labels, 'error_type': type(e).__name__}
                system_metrics['data_ingestion_errors'].inc(labels=error_labels)
                raise
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> dict:
        """Get order book with metrics"""
        labels = {
            'source': 'binance',
            'symbol': symbol,
            'interval': 'orderbook'
        }
        
        system_metrics['data_ingestion_requests'].inc(labels=labels)
        
        with Timer(system_metrics['data_ingestion_latency'], labels):
            try:
                return await self.wrapped_port.get_order_book(symbol, limit)
            except Exception as e:
                error_labels = {**labels, 'error_type': type(e).__name__}
                system_metrics['data_ingestion_errors'].inc(labels=error_labels)
                raise
    
    async def subscribe_trades(self, symbol: str, callback: callable):
        """Subscribe to trades with metrics"""
        return await self.wrapped_port.subscribe_trades(symbol, callback)
    
    async def subscribe_orderbook(self, symbol: str, callback: callable):
        """Subscribe to orderbook with metrics"""
        return await self.wrapped_port.subscribe_orderbook(symbol, callback)


class InstrumentedIndicatorPort(IndicatorPort):
    """Indicator port with metrics instrumentation"""
    
    def __init__(self, wrapped_port: IndicatorPort):
        """
        Initialize instrumented port
        
        Args:
            wrapped_port: The actual indicator port to wrap
        """
        self.wrapped_port = wrapped_port
    
    async def calculate(
        self,
        indicator_type: str,
        data: List[Dict[str, float]],
        params: Dict[str, Any]
    ) -> List[float]:
        """Calculate indicator with metrics"""
        labels = {
            'indicator': indicator_type,
            'symbol': params.get('symbol', 'unknown'),
            'interval': params.get('interval', 'unknown')
        }
        
        with Timer(system_metrics['indicator_calc_latency'], labels):
            try:
                return await self.wrapped_port.calculate(
                    indicator_type, data, params
                )
            except Exception as e:
                error_labels = {**labels, 'error_type': type(e).__name__}
                system_metrics['indicator_calc_errors'].inc(labels=error_labels)
                raise
    
    async def calculate_multiple(
        self,
        indicators: List[Dict[str, Any]],
        data: List[Dict[str, float]]
    ) -> Dict[str, List[float]]:
        """Calculate multiple indicators with metrics"""
        results = {}
        
        for indicator in indicators:
            indicator_type = indicator.get('type', 'unknown')
            params = indicator.get('params', {})
            
            labels = {
                'indicator': indicator_type,
                'symbol': params.get('symbol', 'unknown'),
                'interval': params.get('interval', 'unknown')
            }
            
            with Timer(system_metrics['indicator_calc_latency'], labels):
                try:
                    result = await self.wrapped_port.calculate(
                        indicator_type, data, params
                    )
                    results[indicator_type] = result
                except Exception as e:
                    error_labels = {**labels, 'error_type': type(e).__name__}
                    system_metrics['indicator_calc_errors'].inc(labels=error_labels)
                    raise
        
        return results


class InstrumentedBacktestPort(BacktestPort):
    """Backtest port with metrics instrumentation"""
    
    def __init__(self, wrapped_port: BacktestPort):
        """
        Initialize instrumented port
        
        Args:
            wrapped_port: The actual backtest port to wrap
        """
        self.wrapped_port = wrapped_port
    
    async def run(self, input_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run backtest with metrics"""
        strategy = input_config.get('strategy', 'unknown')
        symbol = input_config.get('symbol', 'unknown')
        interval = input_config.get('timeframe', 'unknown')
        
        labels = {
            'strategy': strategy,
            'symbol': symbol,
            'interval': interval
        }
        
        with Timer(system_metrics['backtest_duration'], labels):
            result = await self.wrapped_port.run(input_config)
        
        # Track trade metrics
        metrics = result.get('metrics', {})
        winning_trades = metrics.get('winning_trades', 0)
        losing_trades = metrics.get('losing_trades', 0)
        
        system_metrics['backtest_trades'].inc(
            winning_trades,
            labels={**labels, 'result': 'win'}
        )
        system_metrics['backtest_trades'].inc(
            losing_trades,
            labels={**labels, 'result': 'loss'}
        )
        
        return result
    
    async def validate_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate config"""
        return await self.wrapped_port.validate_config(config)
    
    async def estimate_duration(self, config: Dict[str, Any]) -> float:
        """Estimate duration"""
        return await self.wrapped_port.estimate_duration(config)
    
    async def get_available_data_range(
        self, symbol: str, interval: str
    ) -> tuple[datetime, datetime]:
        """Get data range"""
        return await self.wrapped_port.get_available_data_range(symbol, interval)
    
    async def run_batch(
        self,
        strategy_name: str,
        search_space: Dict[str, List[Any]],
        base_config: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Any]:
        """Run batch backtest with metrics"""
        symbol = base_config.get('symbol', 'unknown')
        interval = base_config.get('timeframe', 'unknown')
        
        labels = {
            'strategy': strategy_name,
            'symbol': symbol,
            'interval': interval
        }
        
        with Timer(system_metrics['backtest_duration'], labels):
            return await self.wrapped_port.run_batch(
                strategy_name, search_space, base_config
            )


class InstrumentedExecutionPort(ExecutionPort):
    """Execution port with metrics instrumentation"""
    
    def __init__(self, wrapped_port: ExecutionPort):
        """
        Initialize instrumented port
        
        Args:
            wrapped_port: The actual execution port to wrap
        """
        self.wrapped_port = wrapped_port
        self._order_queue: List[float] = []
        self._max_queue_size = 100
    
    async def submit_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Submit order with metrics"""
        exchange = order.get('exchange', 'binance')
        symbol = order.get('symbol', 'unknown')
        order_type = order.get('type', 'market')
        side = order.get('side', 'unknown')
        
        labels = {
            'exchange': exchange,
            'symbol': symbol,
            'order_type': order_type
        }
        
        # Update queue depth
        self._order_queue.append(time.time())
        cutoff = time.time() - 60
        self._order_queue = [t for t in self._order_queue if t > cutoff]
        system_metrics['queue_depth'].set(
            len(self._order_queue),
            labels={'queue_name': 'order_queue'}
        )
        
        # Track order submission
        with Timer(system_metrics['live_order_latency'], labels):
            try:
                result = await self.wrapped_port.submit_order(order)
                
                # Track successful order
                status = result.get('status', 'unknown')
                system_metrics['live_orders'].inc(
                    labels={
                        'exchange': exchange,
                        'symbol': symbol,
                        'side': side,
                        'status': status
                    }
                )
                
                return result
                
            except Exception as e:
                error_labels = {**labels, 'error_type': type(e).__name__}
                system_metrics['live_order_errors'].inc(labels=error_labels)
                
                # Track failed order
                system_metrics['live_orders'].inc(
                    labels={
                        'exchange': exchange,
                        'symbol': symbol,
                        'side': side,
                        'status': 'failed'
                    }
                )
                raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        return await self.wrapped_port.cancel_order(order_id)
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status"""
        return await self.wrapped_port.get_order_status(order_id)
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get positions"""
        return await self.wrapped_port.get_positions()
    
    async def close_position(self, position_id: str) -> bool:
        """Close position"""
        return await self.wrapped_port.close_position(position_id)