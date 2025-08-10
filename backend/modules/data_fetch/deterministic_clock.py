"""
Deterministic clock for replay testing.

Provides consistent time progression for reproducible tests.
"""

from datetime import datetime, timedelta
from typing import Optional, Callable, List
import asyncio
import logging

logger = logging.getLogger(__name__)


class DeterministicClock:
    """
    A deterministic clock that can be controlled programmatically.
    
    Used in replay testing to ensure time-based operations are reproducible.
    """
    
    def __init__(self, start_time: Optional[datetime] = None):
        """
        Initialize deterministic clock.
        
        Args:
            start_time: Initial time (defaults to current time)
        """
        self._current_time = start_time or datetime.now()
        self._is_running = False
        self._speed = 1.0  # Time multiplier
        self._subscribers: List[Callable[[datetime], None]] = []
        self._tick_interval = timedelta(seconds=1)
        self._task: Optional[asyncio.Task] = None
    
    @property
    def now(self) -> datetime:
        """Get current time."""
        return self._current_time
    
    def advance(self, delta: timedelta):
        """
        Advance clock by specified duration.
        
        Args:
            delta: Time to advance
        """
        self._current_time += delta
        self._notify_subscribers()
    
    def advance_to(self, target_time: datetime):
        """
        Advance clock to specific time.
        
        Args:
            target_time: Target time
        """
        if target_time < self._current_time:
            raise ValueError("Cannot go back in time")
        
        self._current_time = target_time
        self._notify_subscribers()
    
    def set_speed(self, speed: float):
        """
        Set clock speed multiplier.
        
        Args:
            speed: Speed multiplier (1.0 = real-time, 0 = instant)
        """
        self._speed = speed
    
    async def start(self):
        """Start automatic time progression."""
        if self._is_running:
            return
        
        self._is_running = True
        self._task = asyncio.create_task(self._run())
    
    async def stop(self):
        """Stop automatic time progression."""
        self._is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _run(self):
        """Run clock progression loop."""
        while self._is_running:
            if self._speed > 0:
                # Wait based on speed
                await asyncio.sleep(self._tick_interval.total_seconds() / self._speed)
                self.advance(self._tick_interval)
            else:
                # Instant mode - just yield control
                await asyncio.sleep(0)
                self.advance(self._tick_interval)
    
    def subscribe(self, callback: Callable[[datetime], None]):
        """
        Subscribe to time updates.
        
        Args:
            callback: Function to call on time updates
        """
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[datetime], None]):
        """
        Unsubscribe from time updates.
        
        Args:
            callback: Function to unsubscribe
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    def _notify_subscribers(self):
        """Notify all subscribers of time change."""
        for callback in self._subscribers:
            try:
                callback(self._current_time)
            except Exception as e:
                logger.error(f"Subscriber notification failed: {e}")
    
    def reset(self, start_time: Optional[datetime] = None):
        """
        Reset clock to initial state.
        
        Args:
            start_time: New start time
        """
        self._current_time = start_time or datetime.now()
        self._notify_subscribers()


class TimeController:
    """
    Controller for managing deterministic time in tests.
    
    Coordinates time between multiple components.
    """
    
    def __init__(self):
        self.clock = DeterministicClock()
        self._checkpoints: List[tuple[datetime, str]] = []
        self._time_listeners: Dict[str, Callable] = {}
    
    def register_component(self, name: str, time_getter: Callable[[], datetime]):
        """
        Register a component's time getter.
        
        Args:
            name: Component name
            time_getter: Function that returns component's current time
        """
        self._time_listeners[name] = time_getter
    
    def checkpoint(self, label: str):
        """
        Create a time checkpoint.
        
        Args:
            label: Checkpoint label
        """
        self._checkpoints.append((self.clock.now, label))
    
    def verify_synchronization(self) -> bool:
        """
        Verify all components are synchronized.
        
        Returns:
            True if all components have the same time
        """
        if not self._time_listeners:
            return True
        
        times = {
            name: getter()
            for name, getter in self._time_listeners.items()
        }
        
        # All times should be equal
        unique_times = set(times.values())
        
        if len(unique_times) > 1:
            logger.warning(f"Time desynchronization detected: {times}")
            return False
        
        return True
    
    def get_checkpoint_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of all checkpoints.
        
        Returns:
            List of checkpoint details
        """
        return [
            {
                "time": checkpoint[0].isoformat(),
                "label": checkpoint[1],
                "elapsed": (checkpoint[0] - self._checkpoints[0][0]).total_seconds()
                if self._checkpoints else 0
            }
            for checkpoint in self._checkpoints
        ]
    
    async def advance_with_validation(self, delta: timedelta) -> bool:
        """
        Advance time with synchronization validation.
        
        Args:
            delta: Time to advance
            
        Returns:
            True if synchronization maintained
        """
        # Advance clock
        self.clock.advance(delta)
        
        # Wait for propagation
        await asyncio.sleep(0.01)
        
        # Verify synchronization
        return self.verify_synchronization()


# Global instance for test coordination
_test_clock: Optional[DeterministicClock] = None


def get_test_clock() -> DeterministicClock:
    """Get or create global test clock."""
    global _test_clock
    if _test_clock is None:
        _test_clock = DeterministicClock()
    return _test_clock


def reset_test_clock(start_time: Optional[datetime] = None):
    """Reset global test clock."""
    global _test_clock
    if _test_clock:
        _test_clock.reset(start_time)
    else:
        _test_clock = DeterministicClock(start_time)