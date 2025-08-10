"""
Telemetry Port

Abstract interface for telemetry and observability operations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class TelemetryPort(ABC):
    """Abstract interface for telemetry operations"""
    
    @abstractmethod
    def emit_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Emit a metric data point
        
        Args:
            name: Metric name (e.g., "trades.executed", "pnl.realized")
            value: Metric value
            labels: Optional labels/tags for the metric
            timestamp: Optional timestamp (defaults to now)
        """
        pass
    
    @abstractmethod
    def emit_event(
        self,
        name: str,
        payload: Dict[str, Any],
        severity: str = "info",
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Emit a telemetry event
        
        Args:
            name: Event name (e.g., "order.placed", "strategy.started")
            payload: Event data payload
            severity: Event severity (debug, info, warning, error, critical)
            timestamp: Optional timestamp (defaults to now)
        """
        pass
    
    @abstractmethod
    def emit_trace(
        self,
        span_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None
    ) -> str:
        """
        Start a trace span
        
        Args:
            span_name: Name of the span (e.g., "backtest.run", "order.execute")
            attributes: Optional span attributes
            parent_span_id: Optional parent span for nested traces
            
        Returns:
            Span ID for correlation
        """
        pass
    
    @abstractmethod
    def end_trace(
        self,
        span_id: str,
        status: str = "ok",
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        End a trace span
        
        Args:
            span_id: Span ID to end
            status: Span completion status (ok, error, cancelled)
            attributes: Additional attributes to add at span end
        """
        pass
    
    @abstractmethod
    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Increment a counter metric
        
        Args:
            name: Counter name
            value: Increment value (default 1)
            labels: Optional labels for the counter
        """
        pass
    
    @abstractmethod
    def record_histogram(
        self,
        name: str,
        value: float,
        buckets: Optional[list[float]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a value in a histogram
        
        Args:
            name: Histogram name
            value: Value to record
            buckets: Optional custom bucket boundaries
            labels: Optional labels
        """
        pass
    
    @abstractmethod
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Set a gauge metric value
        
        Args:
            name: Gauge name
            value: Current value
            labels: Optional labels
        """
        pass