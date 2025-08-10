"""
Backtest Service (Refactored)

Orchestrates the backtesting workflow using domain ports.
No direct infrastructure dependencies.
"""
import asyncio
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from src.domain.shared.ports import BacktestPort, TelemetryPort
from src.domain.shared.contracts import (
    BacktestInput,
    BacktestReport,
    BacktestMetrics
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestJob:
    """Represents a backtest job"""
    job_id: UUID
    input_config: BacktestInput
    status: str  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    report: Optional[BacktestReport] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'job_id': str(self.job_id),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'strategy': self.input_config.strategy_name,
            'symbol': self.input_config.symbol,
            'start_date': self.input_config.start_date.isoformat(),
            'end_date': self.input_config.end_date.isoformat(),
            'error': self.error
        }


class BacktestService:
    """
    Service for managing backtest execution using domain ports
    
    Provides:
    - Synchronous and asynchronous backtest execution
    - Job management and status tracking
    - Result caching and retrieval
    - No direct infrastructure dependencies
    """
    
    def __init__(
        self,
        backtest_port: BacktestPort,
        telemetry_port: Optional[TelemetryPort] = None
    ):
        """
        Initialize the backtest service
        
        Args:
            backtest_port: Port for backtest operations
            telemetry_port: Optional port for telemetry
        """
        self.backtest_port = backtest_port
        self.telemetry_port = telemetry_port
        self.jobs: Dict[UUID, BacktestJob] = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._running_jobs: set = set()
    
    async def run_backtest(self, input_config: BacktestInput) -> BacktestJob:
        """
        Run a backtest synchronously
        
        Args:
            input_config: Backtest configuration
            
        Returns:
            Completed BacktestJob with results
        """
        # Create job
        job = BacktestJob(
            job_id=uuid4(),
            input_config=input_config,
            status='running',
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow()
        )
        
        # Store job
        self.jobs[job.job_id] = job
        
        # Start telemetry span if available
        span_id = None
        if self.telemetry_port:
            span_id = self.telemetry_port.emit_trace(
                span_name="backtest.run",
                attributes={
                    "job_id": str(job.job_id),
                    "strategy": input_config.strategy_name,
                    "symbol": input_config.symbol
                }
            )
        
        try:
            # Validate configuration
            is_valid, error_msg = await self.backtest_port.validate_config(
                input_config.model_dump()
            )
            
            if not is_valid:
                raise ValueError(f"Invalid configuration: {error_msg}")
            
            # Execute backtest
            logger.info(f"Starting backtest job {job.job_id}")
            
            result_dict = await self.backtest_port.run(input_config.model_dump())
            
            # Create BacktestReport from result
            report = BacktestReport(
                backtest_id=str(job.job_id),
                input_config=input_config,
                metrics=BacktestMetrics(**result_dict.get('metrics', {})),
                trades=result_dict.get('trades', []),
                equity_curve=result_dict.get('equity_curve', []),
                drawdown_curve=result_dict.get('drawdown_curve', []),
                metrics_json=result_dict.get('metrics_json', '{}'),
                equity_csv=result_dict.get('equity_csv', ''),
                trades_csv=result_dict.get('trades_csv', ''),
                html_report=result_dict.get('html_report', ''),
                created_at=datetime.utcnow(),
                execution_time=(datetime.utcnow() - job.started_at).total_seconds(),
                data_points=result_dict.get('data_points', 0),
                warnings=result_dict.get('warnings', [])
            )
            
            # Update job with results
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.report = report
            
            logger.info(f"Backtest job {job.job_id} completed successfully")
            
            # Emit metrics if telemetry available
            if self.telemetry_port:
                self.telemetry_port.emit_metric(
                    name="backtest.completed",
                    value=1,
                    labels={"strategy": input_config.strategy_name}
                )
                
                if report.metrics:
                    self.telemetry_port.emit_metric(
                        name="backtest.sharpe_ratio",
                        value=float(report.metrics.sharpe_ratio),
                        labels={"strategy": input_config.strategy_name}
                    )
            
        except Exception as e:
            # Handle failure
            job.status = 'failed'
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            
            logger.error(f"Backtest job {job.job_id} failed: {str(e)}")
            
            if self.telemetry_port:
                self.telemetry_port.emit_event(
                    name="backtest.failed",
                    payload={
                        "job_id": str(job.job_id),
                        "error": str(e)
                    },
                    severity="error"
                )
        
        finally:
            # End telemetry span
            if span_id and self.telemetry_port:
                self.telemetry_port.end_trace(
                    span_id=span_id,
                    status="ok" if job.status == 'completed' else "error"
                )
        
        return job
    
    async def run_backtest_async(self, input_config: BacktestInput) -> UUID:
        """
        Run a backtest asynchronously
        
        Args:
            input_config: Backtest configuration
            
        Returns:
            Job ID for tracking
        """
        # Create job
        job = BacktestJob(
            job_id=uuid4(),
            input_config=input_config,
            status='pending',
            created_at=datetime.utcnow()
        )
        
        # Store job
        self.jobs[job.job_id] = job
        
        # Submit to executor
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            self.executor,
            lambda: asyncio.run(self._execute_backtest(job))
        )
        
        logger.info(f"Backtest job {job.job_id} submitted for async execution")
        
        if self.telemetry_port:
            self.telemetry_port.emit_event(
                name="backtest.submitted",
                payload={
                    "job_id": str(job.job_id),
                    "strategy": input_config.strategy_name
                }
            )
        
        return job.job_id
    
    async def _execute_backtest(self, job: BacktestJob):
        """
        Execute a backtest job (runs in thread pool)
        
        Args:
            job: BacktestJob to execute
        """
        # Update status
        job.status = 'running'
        job.started_at = datetime.utcnow()
        self._running_jobs.add(job.job_id)
        
        try:
            # Run the backtest
            completed_job = await self.run_backtest(job.input_config)
            
            # Copy results to original job
            job.status = completed_job.status
            job.completed_at = completed_job.completed_at
            job.report = completed_job.report
            job.error = completed_job.error
            
        finally:
            self._running_jobs.discard(job.job_id)
    
    def get_job(self, job_id: UUID) -> Optional[BacktestJob]:
        """Get a backtest job by ID"""
        return self.jobs.get(job_id)
    
    def get_job_status(self, job_id: UUID) -> Optional[str]:
        """Get the status of a backtest job"""
        job = self.get_job(job_id)
        return job.status if job else None
    
    def get_job_report(self, job_id: UUID) -> Optional[BacktestReport]:
        """Get the report of a completed backtest job"""
        job = self.get_job(job_id)
        
        if job and job.status == 'completed':
            return job.report
        
        return None
    
    def list_jobs(self, status: Optional[str] = None) -> List[BacktestJob]:
        """List all backtest jobs with optional status filter"""
        jobs = list(self.jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs
    
    def cancel_job(self, job_id: UUID) -> bool:
        """Cancel a pending or running job"""
        job = self.get_job(job_id)
        
        if not job:
            return False
        
        if job.status in ['completed', 'failed', 'cancelled']:
            return False
        
        # Update status
        job.status = 'cancelled'
        job.completed_at = datetime.utcnow()
        job.error = 'Cancelled by user'
        
        # Remove from running jobs if present
        self._running_jobs.discard(job_id)
        
        logger.info(f"Backtest job {job_id} cancelled")
        
        if self.telemetry_port:
            self.telemetry_port.emit_event(
                name="backtest.cancelled",
                payload={"job_id": str(job_id)}
            )
        
        return True
    
    async def estimate_duration(self, input_config: BacktestInput) -> float:
        """Estimate backtest execution duration"""
        return await self.backtest_port.estimate_duration(input_config.model_dump())
    
    async def get_available_data_range(
        self,
        symbol: str,
        interval: str
    ) -> tuple[datetime, datetime]:
        """Get available data range for a symbol"""
        return await self.backtest_port.get_available_data_range(symbol, interval)
    
    def cleanup_old_jobs(self, days: int = 7):
        """Clean up old completed jobs"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            if job.completed_at and job.completed_at < cutoff:
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
        
        logger.info(f"Cleaned up {len(jobs_to_remove)} old backtest jobs")
    
    def shutdown(self):
        """Shutdown the service and cleanup resources"""
        self.executor.shutdown(wait=True)
        logger.info("Backtest service shutdown complete")