"""
Strategy Bridge for Live Trading

Bridges backtested strategies to live trading by converting
strategy signals to domain events.
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID, uuid4

import pandas as pd
import numpy as np

from src.domain.strategy.events import SignalGenerated
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.brokers.binance_futures_broker import BinanceFuturesBroker

logger = logging.getLogger(__name__)


@dataclass
class StrategyState:
    """Current state of a strategy"""
    strategy_id: UUID
    symbol: str
    last_signal: Optional[str] = None
    last_signal_time: Optional[datetime] = None
    position_open: bool = False
    entry_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    
    # Grid strategy specific
    buy_levels: List[Decimal] = None
    sell_levels: List[Decimal] = None
    midpoint: Optional[Decimal] = None
    range_upper: Optional[Decimal] = None
    range_lower: Optional[Decimal] = None


class OptimalGridStrategyLive:
    """
    Live implementation of Optimal Grid Strategy.
    
    Adapts the backtested grid strategy for live trading.
    """
    
    def __init__(
        self,
        symbol: str,
        atr_period: int = 14,
        grid_levels: int = 5,
        atr_multiplier: float = 1.0,
        take_profit_pct: float = 0.02,
        stop_loss_pct: float = 0.05
    ):
        """
        Initialize live grid strategy.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            atr_period: ATR calculation period
            grid_levels: Number of grid levels per side
            atr_multiplier: Range multiplier for ATR
            take_profit_pct: Take profit percentage
            stop_loss_pct: Stop loss percentage
        """
        self.symbol = symbol
        self.atr_period = atr_period
        self.grid_levels = grid_levels
        self.atr_multiplier = atr_multiplier
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        
        # State tracking
        self.state = StrategyState(
            strategy_id=uuid4(),
            symbol=symbol,
            buy_levels=[],
            sell_levels=[]
        )
        
        # Price history for ATR calculation
        self.price_history: pd.DataFrame = pd.DataFrame()
        self.daily_atr: Optional[Decimal] = None
        self.last_grid_update: Optional[datetime] = None
        
        logger.info(f"OptimalGridStrategyLive initialized for {symbol}")
    
    def update_price_history(self, ohlcv_data: pd.DataFrame) -> None:
        """
        Update price history with new OHLCV data.
        
        Args:
            ohlcv_data: DataFrame with OHLCV data
        """
        self.price_history = ohlcv_data
        self._calculate_atr()
    
    def _calculate_atr(self) -> None:
        """Calculate ATR from price history"""
        if len(self.price_history) < self.atr_period:
            return
        
        df = self.price_history.copy()
        
        # Calculate True Range
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR
        atr = tr.ewm(alpha=1/self.atr_period, adjust=False).mean()
        self.daily_atr = Decimal(str(atr.iloc[-1]))
        
        logger.debug(f"ATR calculated: {self.daily_atr}")
    
    def _update_grid_levels(self, current_price: Decimal) -> None:
        """
        Update grid levels based on current price and ATR.
        
        Args:
            current_price: Current market price
        """
        if not self.daily_atr:
            return
        
        # Calculate range
        half_range = self.daily_atr * Decimal(str(self.atr_multiplier)) / 2
        
        # Set midpoint and range
        self.state.midpoint = current_price
        self.state.range_upper = current_price + half_range
        self.state.range_lower = current_price - half_range
        
        # Calculate grid spacing
        grid_spacing = half_range / Decimal(str(self.grid_levels))
        
        # Generate buy levels (below midpoint)
        self.state.buy_levels = []
        for i in range(1, self.grid_levels + 1):
            level = self.state.midpoint - (grid_spacing * Decimal(str(i)))
            self.state.buy_levels.append(level)
        
        # Generate sell levels (above midpoint)
        self.state.sell_levels = []
        for i in range(1, self.grid_levels + 1):
            level = self.state.midpoint + (grid_spacing * Decimal(str(i)))
            self.state.sell_levels.append(level)
        
        self.last_grid_update = datetime.utcnow()
        
        logger.info(f"Grid levels updated - Midpoint: {self.state.midpoint}, "
                   f"Range: [{self.state.range_lower}, {self.state.range_upper}]")
    
    def generate_signal(self, current_price: Decimal) -> Optional[str]:
        """
        Generate trading signal based on current price.
        
        Args:
            current_price: Current market price
            
        Returns:
            Signal type or None
        """
        # Update grid if needed (once per day or on first run)
        now = datetime.utcnow()
        if (not self.last_grid_update or 
            (now - self.last_grid_update) > timedelta(hours=24)):
            self._update_grid_levels(current_price)
        
        if not self.state.midpoint:
            return None
        
        self.state.current_price = current_price
        
        # Check if we have an open position
        if self.state.position_open and self.state.entry_price:
            # Check exit conditions
            pnl_pct = (current_price - self.state.entry_price) / self.state.entry_price
            
            if self.state.last_signal in ["BUY", "STRONG_BUY"]:
                # Long position
                if pnl_pct >= Decimal(str(self.take_profit_pct)):
                    logger.info(f"Take profit triggered for long at {pnl_pct:.2%}")
                    return "CLOSE_LONG"
                elif pnl_pct <= -Decimal(str(self.stop_loss_pct)):
                    logger.info(f"Stop loss triggered for long at {pnl_pct:.2%}")
                    return "CLOSE_LONG"
            
            elif self.state.last_signal in ["SELL", "STRONG_SELL"]:
                # Short position
                if pnl_pct <= -Decimal(str(self.take_profit_pct)):
                    logger.info(f"Take profit triggered for short at {-pnl_pct:.2%}")
                    return "CLOSE_SHORT"
                elif pnl_pct >= Decimal(str(self.stop_loss_pct)):
                    logger.info(f"Stop loss triggered for short at {-pnl_pct:.2%}")
                    return "CLOSE_SHORT"
        
        # Generate new signals based on grid levels
        if current_price < self.state.midpoint:
            # Price below midpoint - check buy levels
            for i, buy_level in enumerate(self.state.buy_levels):
                if abs(current_price - buy_level) / buy_level < Decimal("0.001"):  # 0.1% tolerance
                    # Stronger signal for levels further from midpoint
                    if i >= len(self.state.buy_levels) - 2:  # Bottom 2 levels
                        return "STRONG_BUY"
                    else:
                        return "BUY"
        
        elif current_price > self.state.midpoint:
            # Price above midpoint - check sell levels
            for i, sell_level in enumerate(self.state.sell_levels):
                if abs(current_price - sell_level) / sell_level < Decimal("0.001"):  # 0.1% tolerance
                    # Stronger signal for levels further from midpoint
                    if i >= len(self.state.sell_levels) - 2:  # Top 2 levels
                        return "STRONG_SELL"
                    else:
                        return "SELL"
        
        return "HOLD"  # No action


class StrategyBridge:
    """
    Bridge between trading strategies and live trading system.
    
    Converts strategy signals to domain events for execution.
    """
    
    def __init__(
        self,
        event_bus: InMemoryEventBus,
        broker: Optional[BinanceFuturesBroker] = None
    ):
        """
        Initialize strategy bridge.
        
        Args:
            event_bus: Event bus for publishing signals
            broker: Broker for market data (optional)
        """
        self.event_bus = event_bus
        self.broker = broker
        self.strategies: Dict[str, Any] = {}
        self.running = False
        self._tasks: List[asyncio.Task] = []
        
        logger.info("StrategyBridge initialized")
    
    def add_strategy(self, symbol: str, strategy: Any) -> None:
        """
        Add a strategy to monitor.
        
        Args:
            symbol: Trading symbol
            strategy: Strategy instance
        """
        self.strategies[symbol] = strategy
        logger.info(f"Added strategy for {symbol}")
    
    async def start(self) -> None:
        """Start the strategy bridge"""
        if self.running:
            logger.warning("Strategy bridge already running")
            return
        
        self.running = True
        
        # Start monitoring tasks for each strategy
        for symbol, strategy in self.strategies.items():
            task = asyncio.create_task(self._monitor_strategy(symbol, strategy))
            self._tasks.append(task)
        
        logger.info(f"Strategy bridge started with {len(self.strategies)} strategies")
    
    async def stop(self) -> None:
        """Stop the strategy bridge"""
        self.running = False
        
        # Cancel all monitoring tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        logger.info("Strategy bridge stopped")
    
    async def _monitor_strategy(self, symbol: str, strategy: Any) -> None:
        """
        Monitor a strategy and generate signals.
        
        Args:
            symbol: Trading symbol
            strategy: Strategy instance
        """
        logger.info(f"Starting monitor for {symbol}")
        
        while self.running:
            try:
                # Get current market data
                market_data = await self._get_market_data(symbol)
                
                if market_data:
                    current_price = Decimal(str(market_data['last']))
                    
                    # Update strategy with market data
                    if hasattr(strategy, 'update_price_history'):
                        # For strategies that need historical data
                        ohlcv = await self._get_ohlcv_data(symbol, limit=100)
                        if ohlcv is not None:
                            strategy.update_price_history(ohlcv)
                    
                    # Generate signal
                    signal = strategy.generate_signal(current_price)
                    
                    if signal and signal != "HOLD":
                        # Convert to domain event
                        await self._publish_signal(symbol, signal, strategy, current_price)
                        
                        # Update strategy state
                        if hasattr(strategy, 'state'):
                            strategy.state.last_signal = signal
                            strategy.state.last_signal_time = datetime.utcnow()
                            
                            if signal in ["BUY", "STRONG_BUY", "SELL", "STRONG_SELL"]:
                                strategy.state.position_open = True
                                strategy.state.entry_price = current_price
                            elif signal in ["CLOSE_LONG", "CLOSE_SHORT"]:
                                strategy.state.position_open = False
                                strategy.state.entry_price = None
                
                # Wait before next check (adjust based on timeframe)
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring {symbol}: {e}")
                await asyncio.sleep(10)  # Wait before retry
        
        logger.info(f"Monitor stopped for {symbol}")
    
    async def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get current market data for symbol"""
        if self.broker:
            try:
                ticker = await self.broker.get_ticker(symbol)
                return {
                    'last': ticker.get('lastPrice'),
                    'bid': ticker.get('bidPrice'),
                    'ask': ticker.get('askPrice'),
                    'volume': ticker.get('volume')
                }
            except Exception as e:
                logger.error(f"Failed to get market data for {symbol}: {e}")
        
        return None
    
    async def _get_ohlcv_data(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[pd.DataFrame]:
        """Get OHLCV data for symbol"""
        if self.broker:
            try:
                klines = await self.broker.get_klines(symbol, interval, limit)
                
                # Convert to DataFrame
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                    'taker_buy_quote', 'ignore'
                ])
                
                # Convert types
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                
                return df
                
            except Exception as e:
                logger.error(f"Failed to get OHLCV data for {symbol}: {e}")
        
        return None
    
    async def _publish_signal(
        self,
        symbol: str,
        signal_type: str,
        strategy: Any,
        current_price: Decimal
    ) -> None:
        """
        Publish signal as domain event.
        
        Args:
            symbol: Trading symbol
            signal_type: Type of signal
            strategy: Strategy that generated signal
            current_price: Current market price
        """
        # Calculate signal strength and confidence
        strength = self._calculate_signal_strength(signal_type)
        confidence = self._calculate_signal_confidence(strategy, signal_type)
        
        # Create SignalGenerated event
        event = SignalGenerated(
            strategy_id=strategy.state.strategy_id if hasattr(strategy, 'state') else uuid4(),
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            parameters={
                'current_price': float(current_price),
                'strategy_type': type(strategy).__name__,
                'midpoint': float(strategy.state.midpoint) if hasattr(strategy, 'state') and strategy.state.midpoint else None,
                'atr': float(strategy.daily_atr) if hasattr(strategy, 'daily_atr') and strategy.daily_atr else None
            }
        )
        
        # Publish event
        await self.event_bus.publish(event)
        
        logger.info(f"Signal published: {symbol} {signal_type} "
                   f"(strength: {strength:.2f}, confidence: {confidence:.2f})")
    
    def _calculate_signal_strength(self, signal_type: str) -> Decimal:
        """Calculate signal strength based on type"""
        strength_map = {
            "STRONG_BUY": Decimal("1.0"),
            "BUY": Decimal("0.7"),
            "WEAK_BUY": Decimal("0.4"),
            "STRONG_SELL": Decimal("1.0"),
            "SELL": Decimal("0.7"),
            "WEAK_SELL": Decimal("0.4"),
            "CLOSE_LONG": Decimal("1.0"),
            "CLOSE_SHORT": Decimal("1.0"),
            "HOLD": Decimal("0.0")
        }
        
        return strength_map.get(signal_type, Decimal("0.5"))
    
    def _calculate_signal_confidence(self, strategy: Any, signal_type: str) -> Decimal:
        """Calculate signal confidence based on strategy state"""
        # Base confidence
        confidence = Decimal("0.6")
        
        # Adjust based on strategy-specific factors
        if hasattr(strategy, 'state'):
            state = strategy.state
            
            # Higher confidence if signal aligns with grid levels
            if signal_type in ["BUY", "STRONG_BUY"] and state.buy_levels:
                confidence += Decimal("0.2")
            elif signal_type in ["SELL", "STRONG_SELL"] and state.sell_levels:
                confidence += Decimal("0.2")
            
            # Higher confidence for closing positions with profit
            if signal_type in ["CLOSE_LONG", "CLOSE_SHORT"] and state.unrealized_pnl:
                if state.unrealized_pnl > 0:
                    confidence += Decimal("0.3")
        
        return min(confidence, Decimal("1.0"))