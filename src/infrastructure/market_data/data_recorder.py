"""
Market data recorder for capturing live data to files.

Records ticks and klines for later replay in deterministic tests.
"""

import asyncio
import json
import gzip
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
import logging
from dataclasses import dataclass, field

from src.domain.ports.market_data_port import (
    MarketDataPort, MarketDataConfig, Tick, Kline, TimeFrame
)

logger = logging.getLogger(__name__)


@dataclass
class RecordingSession:
    """Recording session metadata."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    symbols: Set[str] = field(default_factory=set)
    timeframes: Set[TimeFrame] = field(default_factory=set)
    tick_count: int = 0
    kline_count: int = 0
    file_size_bytes: int = 0
    compressed: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "symbols": list(self.symbols),
            "timeframes": [tf.value for tf in self.timeframes],
            "tick_count": self.tick_count,
            "kline_count": self.kline_count,
            "file_size_bytes": self.file_size_bytes,
            "compressed": self.compressed
        }


class DataRecorder:
    """
    Records market data from live sources for replay testing.
    
    Features:
    - Buffered writing for efficiency
    - Compression support
    - Multiple file formats
    - Session management
    - Data validation
    """
    
    def __init__(
        self,
        source_adapter: MarketDataPort,
        output_path: str = "data/recordings",
        buffer_size: int = 1000,
        compress: bool = True
    ):
        self.source_adapter = source_adapter
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        self.buffer_size = buffer_size
        self.compress = compress
        
        # Recording state
        self.recording = False
        self.session: Optional[RecordingSession] = None
        self.recording_task: Optional[asyncio.Task] = None
        
        # Data buffers
        self.tick_buffers: Dict[str, List[Tick]] = defaultdict(list)
        self.kline_buffers: Dict[tuple, List[Kline]] = defaultdict(list)
        
        # File handles
        self.file_handles: Dict[str, Any] = {}
        
        # Statistics
        self.stats = {
            "sessions_recorded": 0,
            "total_ticks": 0,
            "total_klines": 0,
            "total_bytes_written": 0,
            "errors": 0
        }
    
    async def start_recording(
        self,
        symbols: List[str],
        timeframes: List[TimeFrame],
        duration: Optional[timedelta] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Start recording market data.
        
        Args:
            symbols: Symbols to record
            timeframes: Timeframes to record
            duration: Optional recording duration
            session_id: Optional session ID
            
        Returns:
            Session ID
        """
        if self.recording:
            raise RuntimeError("Already recording")
        
        # Create session
        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.session = RecordingSession(
            session_id=session_id,
            start_time=datetime.now(),
            symbols=set(symbols),
            timeframes=set(timeframes),
            compressed=self.compress
        )
        
        # Connect to source if needed
        if not await self.source_adapter.is_connected():
            config = MarketDataConfig(
                symbols=symbols,
                timeframes=timeframes
            )
            await self.source_adapter.connect(config)
        
        # Subscribe to data
        for symbol in symbols:
            self.source_adapter.subscribe_tick(
                symbol,
                lambda tick, s=symbol: self._on_tick(s, tick)
            )
            
            for timeframe in timeframes:
                self.source_adapter.subscribe_kline(
                    symbol,
                    timeframe,
                    lambda kline, s=symbol, tf=timeframe: self._on_kline(s, tf, kline)
                )
        
        # Start recording task
        self.recording = True
        self.recording_task = asyncio.create_task(
            self._recording_loop(duration)
        )
        
        logger.info(
            f"Started recording session {session_id} for "
            f"{len(symbols)} symbols, {len(timeframes)} timeframes"
        )
        
        return session_id
    
    async def stop_recording(self) -> RecordingSession:
        """
        Stop recording and save data.
        
        Returns:
            Recording session metadata
        """
        if not self.recording:
            raise RuntimeError("Not recording")
        
        self.recording = False
        
        # Cancel recording task
        if self.recording_task:
            self.recording_task.cancel()
            try:
                await self.recording_task
            except asyncio.CancelledError:
                pass
        
        # Unsubscribe
        self.source_adapter.unsubscribe_all()
        
        # Flush all buffers
        await self._flush_all_buffers()
        
        # Close file handles
        for handle in self.file_handles.values():
            if hasattr(handle, 'close'):
                handle.close()
        self.file_handles.clear()
        
        # Update session
        self.session.end_time = datetime.now()
        
        # Save session metadata
        await self._save_session_metadata()
        
        # Update statistics
        self.stats["sessions_recorded"] += 1
        
        logger.info(
            f"Stopped recording session {self.session.session_id}: "
            f"{self.session.tick_count} ticks, {self.session.kline_count} klines"
        )
        
        session = self.session
        self.session = None
        
        return session
    
    def _on_tick(self, symbol: str, tick: Tick):
        """Handle incoming tick."""
        if not self.recording:
            return
        
        self.tick_buffers[symbol].append(tick)
        self.session.tick_count += 1
        
        # Flush if buffer full
        if len(self.tick_buffers[symbol]) >= self.buffer_size:
            asyncio.create_task(self._flush_tick_buffer(symbol))
    
    def _on_kline(self, symbol: str, timeframe: TimeFrame, kline: Kline):
        """Handle incoming kline."""
        if not self.recording:
            return
        
        key = (symbol, timeframe)
        self.kline_buffers[key].append(kline)
        self.session.kline_count += 1
        
        # Flush if buffer full
        if len(self.kline_buffers[key]) >= self.buffer_size:
            asyncio.create_task(self._flush_kline_buffer(symbol, timeframe))
    
    async def _recording_loop(self, duration: Optional[timedelta]):
        """Main recording loop."""
        start_time = datetime.now()
        
        try:
            while self.recording:
                # Check duration
                if duration:
                    elapsed = datetime.now() - start_time
                    if elapsed >= duration:
                        logger.info("Recording duration reached")
                        await self.stop_recording()
                        break
                
                # Periodic flush
                await self._flush_all_buffers()
                
                # Wait
                await asyncio.sleep(10)  # Flush every 10 seconds
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Recording loop error: {e}")
            self.stats["errors"] += 1
    
    async def _flush_tick_buffer(self, symbol: str):
        """Flush tick buffer to file."""
        if symbol not in self.tick_buffers:
            return
        
        ticks = self.tick_buffers[symbol]
        if not ticks:
            return
        
        # Clear buffer
        self.tick_buffers[symbol] = []
        
        # Get file handle
        file_key = f"ticks_{symbol}"
        if file_key not in self.file_handles:
            file_path = self._get_file_path(symbol, "ticks")
            self.file_handles[file_key] = self._open_file(file_path, "w")
            # Write header
            self._write_data(self.file_handles[file_key], {
                "type": "ticks",
                "symbol": symbol,
                "session_id": self.session.session_id,
                "data": []
            })
        
        # Convert to dict
        tick_data = [tick.to_dict() for tick in ticks]
        
        # Append to file
        self._append_data(self.file_handles[file_key], tick_data)
        
        # Update stats
        self.stats["total_ticks"] += len(ticks)
    
    async def _flush_kline_buffer(self, symbol: str, timeframe: TimeFrame):
        """Flush kline buffer to file."""
        key = (symbol, timeframe)
        if key not in self.kline_buffers:
            return
        
        klines = self.kline_buffers[key]
        if not klines:
            return
        
        # Clear buffer
        self.kline_buffers[key] = []
        
        # Get file handle
        file_key = f"klines_{symbol}_{timeframe.value}"
        if file_key not in self.file_handles:
            file_path = self._get_file_path(symbol, f"klines_{timeframe.value}")
            self.file_handles[file_key] = self._open_file(file_path, "w")
            # Write header
            self._write_data(self.file_handles[file_key], {
                "type": "klines",
                "symbol": symbol,
                "timeframe": timeframe.value,
                "session_id": self.session.session_id,
                "data": []
            })
        
        # Convert to dict
        kline_data = [kline.to_dict() for kline in klines]
        
        # Append to file
        self._append_data(self.file_handles[file_key], kline_data)
        
        # Update stats
        self.stats["total_klines"] += len(klines)
    
    async def _flush_all_buffers(self):
        """Flush all data buffers."""
        # Flush tick buffers
        for symbol in list(self.tick_buffers.keys()):
            await self._flush_tick_buffer(symbol)
        
        # Flush kline buffers
        for symbol, timeframe in list(self.kline_buffers.keys()):
            await self._flush_kline_buffer(symbol, timeframe)
    
    async def _save_session_metadata(self):
        """Save session metadata to file."""
        if not self.session:
            return
        
        metadata_path = self.output_path / f"{self.session.session_id}_metadata.json"
        
        with open(metadata_path, 'w') as f:
            json.dump(self.session.to_dict(), f, indent=2)
        
        logger.info(f"Saved session metadata to {metadata_path}")
    
    def _get_file_path(self, symbol: str, data_type: str) -> Path:
        """Get file path for data."""
        filename = f"{self.session.session_id}_{symbol}_{data_type}"
        
        if self.compress:
            filename += ".json.gz"
        else:
            filename += ".json"
        
        return self.output_path / filename
    
    def _open_file(self, path: Path, mode: str):
        """Open file handle."""
        if self.compress:
            return gzip.open(path, mode + 't')
        else:
            return open(path, mode)
    
    def _write_data(self, handle, data: Dict[str, Any]):
        """Write data to file."""
        json.dump(data, handle)
        handle.flush()
        
        # Update size
        if hasattr(handle, 'tell'):
            self.session.file_size_bytes = handle.tell()
    
    def _append_data(self, handle, data: List[Dict[str, Any]]):
        """Append data to existing file."""
        # This is simplified - in production would handle proper JSON array appending
        for item in data:
            handle.write(json.dumps(item) + "\n")
        handle.flush()
    
    async def create_combined_file(self, session_id: str) -> Path:
        """
        Create a combined file with all data from a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Path to combined file
        """
        # Find all files for session
        session_files = list(self.output_path.glob(f"{session_id}_*.json*"))
        
        if not session_files:
            raise FileNotFoundError(f"No files found for session {session_id}")
        
        # Load metadata
        metadata_file = self.output_path / f"{session_id}_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        # Combine all data
        combined_data = {
            "metadata": metadata,
            "ticks": {},
            "klines": {}
        }
        
        for file_path in session_files:
            if "metadata" in file_path.name:
                continue
            
            # Load data
            if file_path.suffix == ".gz":
                with gzip.open(file_path, 'rt') as f:
                    # Read line by line for appended data
                    lines = f.readlines()
                    if lines:
                        header = json.loads(lines[0])
                        data = [json.loads(line) for line in lines[1:] if line.strip()]
            else:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        header = json.loads(lines[0])
                        data = [json.loads(line) for line in lines[1:] if line.strip()]
            
            # Add to combined data
            if header.get("type") == "ticks":
                symbol = header["symbol"]
                if symbol not in combined_data["ticks"]:
                    combined_data["ticks"][symbol] = []
                combined_data["ticks"][symbol].extend(data)
                
            elif header.get("type") == "klines":
                symbol = header["symbol"]
                timeframe = header["timeframe"]
                
                if symbol not in combined_data["klines"]:
                    combined_data["klines"][symbol] = {}
                if timeframe not in combined_data["klines"][symbol]:
                    combined_data["klines"][symbol][timeframe] = []
                
                combined_data["klines"][symbol][timeframe].extend(data)
        
        # Save combined file
        output_path = self.output_path / f"{session_id}_combined.json"
        
        if self.compress:
            output_path = output_path.with_suffix(".json.gz")
            with gzip.open(output_path, 'wt') as f:
                json.dump(combined_data, f, indent=2)
        else:
            with open(output_path, 'w') as f:
                json.dump(combined_data, f, indent=2)
        
        logger.info(f"Created combined file: {output_path}")
        
        return output_path
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get recorder statistics."""
        stats = self.stats.copy()
        
        if self.session:
            stats["current_session"] = self.session.to_dict()
            stats["recording"] = self.recording
        
        return stats