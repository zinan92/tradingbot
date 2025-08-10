"""
Replay adapter for deterministic market data playback.

Reads recorded ticks and klines from files for reproducible testing.
"""

import asyncio
import json
import gzip
from pathlib import Path
from typing import List, Optional, Dict, Any, AsyncIterator, Callable, Set
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from src.domain.ports.market_data_port import (
    MarketDataPort, MarketDataConfig, Tick, Kline, TimeFrame
)

logger = logging.getLogger(__name__)


@dataclass
class ReplayState:
    """State of replay playback."""
    current_time: datetime
    start_time: datetime
    end_time: datetime
    speed: float
    is_playing: bool = False
    is_paused: bool = False
    ticks_processed: int = 0
    klines_processed: int = 0
    
    @property
    def progress(self) -> float:
        """Get playback progress as percentage."""
        if self.end_time <= self.start_time:
            return 0.0
        
        total_duration = (self.end_time - self.start_time).total_seconds()
        elapsed = (self.current_time - self.start_time).total_seconds()
        return min(100.0, (elapsed / total_duration) * 100)


@dataclass
class RecordedData:
    """Container for recorded market data."""
    ticks: List[Tick] = field(default_factory=list)
    klines: Dict[TimeFrame, List[Kline]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def sort_by_time(self):
        """Sort all data by timestamp."""
        self.ticks.sort(key=lambda t: t.timestamp)
        for timeframe_klines in self.klines.values():
            timeframe_klines.sort(key=lambda k: k.timestamp)


class ReplayAdapter(MarketDataPort):
    """
    Replay adapter for deterministic market data playback.
    
    Features:
    - Reads recorded data from JSON/compressed files
    - Supports variable playback speed
    - Deterministic time handling for reproducible tests
    - Memory-efficient streaming
    """
    
    def __init__(self, data_path: str = "data/replay"):
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        self.config: Optional[MarketDataConfig] = None
        self.connected = False
        
        # Recorded data per symbol
        self.recorded_data: Dict[str, RecordedData] = {}
        
        # Replay state
        self.replay_state: Optional[ReplayState] = None
        self.replay_task: Optional[asyncio.Task] = None
        
        # Subscriptions
        self.tick_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.kline_callbacks: Dict[tuple, List[Callable]] = defaultdict(list)
        
        # Current data cache
        self.current_ticks: Dict[str, Tick] = {}
        self.current_klines: Dict[tuple, Kline] = {}
        
        # Statistics
        self.stats = {
            "ticks_replayed": 0,
            "klines_replayed": 0,
            "files_loaded": 0,
            "total_data_points": 0,
            "start_time": None,
            "end_time": None
        }
    
    async def connect(self, config: MarketDataConfig) -> bool:
        """Connect to replay data source."""
        try:
            self.config = config
            
            # Load recorded data for requested symbols
            for symbol in config.symbols:
                data = await self._load_recorded_data(symbol)
                if data:
                    self.recorded_data[symbol] = data
                    self.stats["files_loaded"] += 1
            
            if not self.recorded_data:
                logger.error("No recorded data found for requested symbols")
                return False
            
            # Initialize replay state
            self._initialize_replay_state()
            
            # Start replay if not in deterministic mode
            if not config.deterministic:
                self.replay_task = asyncio.create_task(self._replay_loop())
            
            self.connected = True
            logger.info(
                f"Connected to replay adapter with {len(self.recorded_data)} symbols, "
                f"{self.stats['total_data_points']} data points"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect replay adapter: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from replay data source."""
        if self.replay_task:
            self.replay_task.cancel()
            try:
                await self.replay_task
            except asyncio.CancelledError:
                pass
        
        self.connected = False
        self.recorded_data.clear()
        self.current_ticks.clear()
        self.current_klines.clear()
        
        logger.info("Disconnected from replay adapter")
        return True
    
    async def is_connected(self) -> bool:
        """Check connection status."""
        return self.connected
    
    async def get_tick(self, symbol: str) -> Optional[Tick]:
        """Get current tick for symbol."""
        return self.current_ticks.get(symbol)
    
    async def get_kline(self, symbol: str, timeframe: TimeFrame) -> Optional[Kline]:
        """Get current kline for symbol and timeframe."""
        return self.current_klines.get((symbol, timeframe))
    
    async def get_klines(
        self,
        symbol: str,
        timeframe: TimeFrame,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Kline]:
        """Get historical klines from recorded data."""
        if symbol not in self.recorded_data:
            return []
        
        klines = self.recorded_data[symbol].klines.get(timeframe, [])
        
        # Filter by time range
        if start_time:
            klines = [k for k in klines if k.timestamp >= start_time]
        if end_time:
            klines = [k for k in klines if k.timestamp <= end_time]
        
        # Limit results
        if len(klines) > limit:
            klines = klines[-limit:]
        
        return klines
    
    async def stream_ticks(self, symbols: List[str]) -> AsyncIterator[Tick]:
        """Stream ticks in replay order."""
        if self.config and self.config.deterministic:
            # In deterministic mode, yield all ticks at once
            for symbol in symbols:
                if symbol in self.recorded_data:
                    for tick in self.recorded_data[symbol].ticks:
                        yield tick
        else:
            # In replay mode, yield ticks as they're replayed
            while self.connected:
                for symbol in symbols:
                    if symbol in self.current_ticks:
                        yield self.current_ticks[symbol]
                await asyncio.sleep(0.1)
    
    async def stream_klines(
        self,
        symbols: List[str],
        timeframe: TimeFrame
    ) -> AsyncIterator[Kline]:
        """Stream klines in replay order."""
        if self.config and self.config.deterministic:
            # In deterministic mode, yield all klines at once
            for symbol in symbols:
                if symbol in self.recorded_data:
                    klines = self.recorded_data[symbol].klines.get(timeframe, [])
                    for kline in klines:
                        yield kline
        else:
            # In replay mode, yield klines as they're replayed
            while self.connected:
                for symbol in symbols:
                    key = (symbol, timeframe)
                    if key in self.current_klines:
                        yield self.current_klines[key]
                await asyncio.sleep(1.0)
    
    def subscribe_tick(self, symbol: str, callback: Callable[[Tick], None]):
        """Subscribe to tick updates."""
        self.tick_callbacks[symbol].append(callback)
    
    def subscribe_kline(
        self,
        symbol: str,
        timeframe: TimeFrame,
        callback: Callable[[Kline], None]
    ):
        """Subscribe to kline updates."""
        self.kline_callbacks[(symbol, timeframe)].append(callback)
    
    def unsubscribe_all(self):
        """Unsubscribe from all subscriptions."""
        self.tick_callbacks.clear()
        self.kline_callbacks.clear()
    
    def get_adapter_name(self) -> str:
        """Get adapter name."""
        return "replay"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        stats = self.stats.copy()
        
        if self.replay_state:
            stats.update({
                "current_time": self.replay_state.current_time.isoformat(),
                "progress": f"{self.replay_state.progress:.2f}%",
                "speed": self.replay_state.speed,
                "is_playing": self.replay_state.is_playing,
                "ticks_processed": self.replay_state.ticks_processed,
                "klines_processed": self.replay_state.klines_processed
            })
        
        return stats
    
    async def _load_recorded_data(self, symbol: str) -> Optional[RecordedData]:
        """Load recorded data from file."""
        data = RecordedData()
        
        # Try different file formats
        file_paths = [
            self.data_path / f"{symbol}.json",
            self.data_path / f"{symbol}.json.gz",
            self.data_path / f"{symbol}_ticks.json",
            self.data_path / f"{symbol}_klines.json"
        ]
        
        for file_path in file_paths:
            if file_path.exists():
                try:
                    # Load data
                    if file_path.suffix == ".gz":
                        with gzip.open(file_path, 'rt') as f:
                            raw_data = json.load(f)
                    else:
                        with open(file_path, 'r') as f:
                            raw_data = json.load(f)
                    
                    # Parse ticks
                    if "ticks" in raw_data:
                        for tick_data in raw_data["ticks"]:
                            data.ticks.append(Tick.from_dict(tick_data))
                    
                    # Parse klines
                    if "klines" in raw_data:
                        for timeframe_str, kline_list in raw_data["klines"].items():
                            timeframe = TimeFrame(timeframe_str)
                            data.klines[timeframe] = []
                            for kline_data in kline_list:
                                data.klines[timeframe].append(Kline.from_dict(kline_data))
                    
                    # Parse metadata
                    if "metadata" in raw_data:
                        data.metadata = raw_data["metadata"]
                    
                    # Sort by timestamp
                    data.sort_by_time()
                    
                    # Update statistics
                    self.stats["total_data_points"] += len(data.ticks)
                    for klines in data.klines.values():
                        self.stats["total_data_points"] += len(klines)
                    
                    logger.info(
                        f"Loaded {len(data.ticks)} ticks and "
                        f"{sum(len(k) for k in data.klines.values())} klines for {symbol}"
                    )
                    
                    return data
                    
                except Exception as e:
                    logger.error(f"Failed to load {file_path}: {e}")
        
        logger.warning(f"No recorded data found for {symbol}")
        return None
    
    def _initialize_replay_state(self):
        """Initialize replay state from loaded data."""
        if not self.recorded_data:
            return
        
        # Find time range
        min_time = datetime.max
        max_time = datetime.min
        
        for data in self.recorded_data.values():
            if data.ticks:
                min_time = min(min_time, data.ticks[0].timestamp)
                max_time = max(max_time, data.ticks[-1].timestamp)
            
            for klines in data.klines.values():
                if klines:
                    min_time = min(min_time, klines[0].timestamp)
                    max_time = max(max_time, klines[-1].timestamp)
        
        # Apply config time range if specified
        if self.config:
            if self.config.start_time:
                min_time = max(min_time, self.config.start_time)
            if self.config.end_time:
                max_time = min(max_time, self.config.end_time)
        
        self.replay_state = ReplayState(
            current_time=min_time,
            start_time=min_time,
            end_time=max_time,
            speed=self.config.replay_speed if self.config else 1.0
        )
        
        self.stats["start_time"] = min_time.isoformat()
        self.stats["end_time"] = max_time.isoformat()
    
    async def _replay_loop(self):
        """Main replay loop for streaming data."""
        if not self.replay_state:
            return
        
        self.replay_state.is_playing = True
        last_real_time = datetime.now()
        
        try:
            while self.connected and self.replay_state.current_time <= self.replay_state.end_time:
                if self.replay_state.is_paused:
                    await asyncio.sleep(0.1)
                    continue
                
                # Calculate time advancement
                if self.replay_state.speed > 0:
                    real_time_elapsed = (datetime.now() - last_real_time).total_seconds()
                    replay_time_advance = real_time_elapsed * self.replay_state.speed
                    self.replay_state.current_time += timedelta(seconds=replay_time_advance)
                else:
                    # Speed 0 means as fast as possible
                    self.replay_state.current_time += timedelta(seconds=1)
                
                last_real_time = datetime.now()
                
                # Process data up to current replay time
                await self._process_data_to_time(self.replay_state.current_time)
                
                # Small delay to prevent CPU spinning
                if self.replay_state.speed == 0:
                    await asyncio.sleep(0.001)
                else:
                    await asyncio.sleep(0.1)
        
        finally:
            self.replay_state.is_playing = False
    
    async def _process_data_to_time(self, target_time: datetime):
        """Process all data up to target time."""
        for symbol, data in self.recorded_data.items():
            # Process ticks
            for tick in data.ticks:
                if tick.timestamp > target_time:
                    break
                
                if tick.timestamp > self.replay_state.current_time - timedelta(seconds=1):
                    self.current_ticks[symbol] = tick
                    self.replay_state.ticks_processed += 1
                    
                    # Notify subscribers
                    for callback in self.tick_callbacks.get(symbol, []):
                        try:
                            callback(tick)
                        except Exception as e:
                            logger.error(f"Tick callback error: {e}")
            
            # Process klines
            for timeframe, klines in data.klines.items():
                for kline in klines:
                    if kline.timestamp > target_time:
                        break
                    
                    key = (symbol, timeframe)
                    self.current_klines[key] = kline
                    self.replay_state.klines_processed += 1
                    
                    # Notify subscribers
                    for callback in self.kline_callbacks.get(key, []):
                        try:
                            callback(kline)
                        except Exception as e:
                            logger.error(f"Kline callback error: {e}")
    
    def advance_to_time(self, target_time: datetime):
        """
        Advance replay to specific time (for deterministic testing).
        
        This method is synchronous for use in deterministic tests.
        """
        if not self.replay_state:
            return
        
        if target_time > self.replay_state.end_time:
            target_time = self.replay_state.end_time
        
        if target_time < self.replay_state.current_time:
            logger.warning("Cannot go back in time in replay")
            return
        
        # Process all data up to target time
        asyncio.create_task(self._process_data_to_time(target_time))
        self.replay_state.current_time = target_time
    
    def pause(self):
        """Pause replay."""
        if self.replay_state:
            self.replay_state.is_paused = True
    
    def resume(self):
        """Resume replay."""
        if self.replay_state:
            self.replay_state.is_paused = False
    
    def set_speed(self, speed: float):
        """Set replay speed."""
        if self.replay_state:
            self.replay_state.speed = speed