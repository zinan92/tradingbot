"""
Core logic for planning data fetch operations

This module handles:
- Fetch plan creation
- Batch optimization
- Time range calculations
"""

from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FetchPlan:
    """Represents a single fetch operation"""
    symbol: str
    interval: str
    start: datetime
    end: datetime
    priority: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'interval': self.interval,
            'start': self.start,
            'end': self.end,
            'priority': self.priority
        }


class FetchPlanner:
    """
    Core logic for planning data fetch operations
    """
    
    # Interval to milliseconds mapping
    INTERVAL_MS = {
        '1m': 60 * 1000,
        '3m': 3 * 60 * 1000,
        '5m': 5 * 60 * 1000,
        '15m': 15 * 60 * 1000,
        '30m': 30 * 60 * 1000,
        '1h': 60 * 60 * 1000,
        '2h': 2 * 60 * 60 * 1000,
        '4h': 4 * 60 * 60 * 1000,
        '6h': 6 * 60 * 60 * 1000,
        '8h': 8 * 60 * 60 * 1000,
        '12h': 12 * 60 * 60 * 1000,
        '1d': 24 * 60 * 60 * 1000,
        '3d': 3 * 24 * 60 * 60 * 1000,
        '1w': 7 * 24 * 60 * 60 * 1000,
        '1M': 30 * 24 * 60 * 60 * 1000,  # Approximate
    }
    
    # Maximum candles per request (exchange limit)
    MAX_CANDLES_PER_REQUEST = 1000
    
    def __init__(self, max_batch_size: int = 1000):
        self.max_batch_size = max_batch_size
    
    def create_fetch_plan(
        self,
        symbols: List[str],
        intervals: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, any]]:
        """
        Create an optimized fetch plan for downloading data
        
        Args:
            symbols: List of trading symbols
            intervals: List of kline intervals
            start_date: Start date for data fetch
            end_date: End date for data fetch
        
        Returns:
            List of fetch operations
        """
        fetch_plan = []
        
        for symbol in symbols:
            for interval in intervals:
                # Calculate time chunks for this interval
                chunks = self._calculate_time_chunks(
                    interval=interval,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Create fetch operations for each chunk
                for chunk_start, chunk_end in chunks:
                    plan_item = FetchPlan(
                        symbol=symbol,
                        interval=interval,
                        start=chunk_start,
                        end=chunk_end,
                        priority=self._calculate_priority(interval)
                    )
                    fetch_plan.append(plan_item.to_dict())
        
        # Sort by priority (lower intervals first)
        fetch_plan.sort(key=lambda x: x['priority'])
        
        logger.debug(f"Created fetch plan with {len(fetch_plan)} operations")
        
        return fetch_plan
    
    def _calculate_time_chunks(
        self,
        interval: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Tuple[datetime, datetime]]:
        """
        Calculate optimal time chunks for fetching data
        
        Args:
            interval: Kline interval
            start_date: Start date
            end_date: End date
        
        Returns:
            List of (start, end) datetime tuples
        """
        chunks = []
        
        # Get interval in milliseconds
        interval_ms = self.INTERVAL_MS.get(interval)
        if not interval_ms:
            logger.warning(f"Unknown interval {interval}, using 1h as default")
            interval_ms = self.INTERVAL_MS['1h']
        
        # Calculate maximum time span per request
        max_span_ms = interval_ms * self.MAX_CANDLES_PER_REQUEST
        max_span = timedelta(milliseconds=max_span_ms)
        
        # Generate chunks
        current_start = start_date
        while current_start < end_date:
            current_end = min(current_start + max_span, end_date)
            chunks.append((current_start, current_end))
            current_start = current_end
        
        return chunks
    
    def _calculate_priority(self, interval: str) -> int:
        """
        Calculate priority for an interval (lower = higher priority)
        
        Args:
            interval: Kline interval
        
        Returns:
            Priority value
        """
        priority_map = {
            '1m': 10,
            '3m': 9,
            '5m': 8,
            '15m': 7,
            '30m': 6,
            '1h': 5,
            '2h': 4,
            '4h': 3,
            '6h': 3,
            '8h': 3,
            '12h': 2,
            '1d': 1,
            '3d': 1,
            '1w': 0,
            '1M': 0,
        }
        return priority_map.get(interval, 5)
    
    def optimize_plan(self, fetch_plan: List[Dict]) -> List[Dict]:
        """
        Optimize fetch plan for efficiency
        
        Args:
            fetch_plan: Original fetch plan
        
        Returns:
            Optimized fetch plan
        """
        # Group by symbol to minimize connection overhead
        grouped = {}
        for item in fetch_plan:
            key = item['symbol']
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(item)
        
        # Rebuild plan with grouped operations
        optimized = []
        for symbol, items in grouped.items():
            # Sort by interval priority and time
            items.sort(key=lambda x: (x['priority'], x['start']))
            optimized.extend(items)
        
        return optimized
    
    def estimate_download_time(
        self,
        fetch_plan: List[Dict],
        avg_request_time: float = 0.5
    ) -> Dict[str, any]:
        """
        Estimate download time for a fetch plan
        
        Args:
            fetch_plan: Fetch plan to estimate
            avg_request_time: Average time per request in seconds
        
        Returns:
            Estimation details
        """
        total_requests = len(fetch_plan)
        total_candles = 0
        
        for item in fetch_plan:
            interval = item['interval']
            start = item['start']
            end = item['end']
            
            # Calculate number of candles
            time_diff_ms = (end - start).total_seconds() * 1000
            interval_ms = self.INTERVAL_MS.get(interval, self.INTERVAL_MS['1h'])
            candles = int(time_diff_ms / interval_ms)
            total_candles += candles
        
        estimated_time = total_requests * avg_request_time
        
        return {
            'total_requests': total_requests,
            'estimated_candles': total_candles,
            'estimated_time_seconds': estimated_time,
            'estimated_time_minutes': estimated_time / 60,
            'estimated_time_hours': estimated_time / 3600
        }
    
    def split_by_date_ranges(
        self,
        fetch_plan: List[Dict],
        date_ranges: List[Tuple[datetime, datetime]]
    ) -> List[Dict]:
        """
        Split fetch plan by specific date ranges
        
        Args:
            fetch_plan: Original fetch plan
            date_ranges: List of (start, end) date ranges
        
        Returns:
            Filtered fetch plan
        """
        filtered = []
        
        for item in fetch_plan:
            item_start = item['start']
            item_end = item['end']
            
            for range_start, range_end in date_ranges:
                # Check if item overlaps with range
                if item_start < range_end and item_end > range_start:
                    # Adjust to fit within range
                    adjusted_start = max(item_start, range_start)
                    adjusted_end = min(item_end, range_end)
                    
                    if adjusted_start < adjusted_end:
                        adjusted_item = item.copy()
                        adjusted_item['start'] = adjusted_start
                        adjusted_item['end'] = adjusted_end
                        filtered.append(adjusted_item)
        
        return filtered