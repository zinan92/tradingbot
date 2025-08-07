"""
Backtest Service

Orchestrates the backtesting workflow and manages backtest execution.
Provides high-level interface for running and managing backtests.
"""

import asyncio
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from src.application.backtesting.commands.run_backtest_command import (
    RunBacktestCommand,
    RunBacktestCommandHandler
)
from src.infrastructure.backtesting.backtest_engine import BacktestResults

logger = logging.getLogger(__name__)


@dataclass
class BacktestJob:
    """Represents a backtest job"""
    job_id: UUID
    command: RunBacktestCommand
    status: str  # 'pending', 'running', 'completed', 'failed'
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Optional[BacktestResults] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'job_id': str(self.job_id),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'strategy': self.command.strategy_name,
            'symbol': self.command.symbol,
            'start_date': self.command.start_date.isoformat(),
            'end_date': self.command.end_date.isoformat(),
            'error': self.error
        }


class BacktestService:
    """
    Service for managing backtest execution
    
    Provides:
    - Synchronous and asynchronous backtest execution
    - Job management and status tracking
    - Result caching and retrieval
    - Optimization capabilities
    """
    
    def __init__(self):
        """Initialize the backtest service"""
        self.handler = RunBacktestCommandHandler()
        self.jobs: Dict[UUID, BacktestJob] = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._running_jobs: set = set()
    
    def run_backtest(self, command: RunBacktestCommand) -> BacktestJob:
        """
        Run a backtest synchronously
        
        Args:
            command: Backtest command to execute
            
        Returns:
            Completed BacktestJob with results
        """
        # Create job
        job = BacktestJob(
            job_id=uuid4(),
            command=command,
            status='running',
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow()
        )
        
        # Store job
        self.jobs[job.job_id] = job
        
        try:
            # Execute backtest
            logger.info(f"Starting backtest job {job.job_id}")
            results = self.handler.handle(command)
            
            # Update job with results
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.results = results
            
            logger.info(f"Backtest job {job.job_id} completed successfully")
            
        except Exception as e:
            # Handle failure
            job.status = 'failed'
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            
            logger.error(f"Backtest job {job.job_id} failed: {str(e)}")
        
        return job
    
    async def run_backtest_async(self, command: RunBacktestCommand) -> UUID:
        """
        Run a backtest asynchronously
        
        Args:
            command: Backtest command to execute
            
        Returns:
            Job ID for tracking
        """
        # Create job
        job = BacktestJob(
            job_id=uuid4(),
            command=command,
            status='pending',
            created_at=datetime.utcnow()
        )
        
        # Store job
        self.jobs[job.job_id] = job
        
        # Submit to executor
        loop = asyncio.get_event_loop()
        loop.run_in_executor(self.executor, self._execute_backtest, job)
        
        logger.info(f"Backtest job {job.job_id} submitted for async execution")
        
        return job.job_id
    
    def _execute_backtest(self, job: BacktestJob):
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
            # Execute backtest
            results = self.handler.handle(job.command)
            
            # Update job with results
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.results = results
            
            logger.info(f"Async backtest job {job.job_id} completed")
            
        except Exception as e:
            # Handle failure
            job.status = 'failed'
            job.completed_at = datetime.utcnow()
            job.error = str(e)
            
            logger.error(f"Async backtest job {job.job_id} failed: {str(e)}")
        
        finally:
            self._running_jobs.discard(job.job_id)
    
    def get_job(self, job_id: UUID) -> Optional[BacktestJob]:
        """
        Get a backtest job by ID
        
        Args:
            job_id: Job ID
            
        Returns:
            BacktestJob or None if not found
        """
        return self.jobs.get(job_id)
    
    def get_job_status(self, job_id: UUID) -> Optional[str]:
        """
        Get the status of a backtest job
        
        Args:
            job_id: Job ID
            
        Returns:
            Status string or None if not found
        """
        job = self.get_job(job_id)
        return job.status if job else None
    
    def get_job_results(self, job_id: UUID) -> Optional[BacktestResults]:
        """
        Get the results of a completed backtest job
        
        Args:
            job_id: Job ID
            
        Returns:
            BacktestResults or None if not found/not completed
        """
        job = self.get_job(job_id)
        
        if job and job.status == 'completed':
            return job.results
        
        return None
    
    def list_jobs(self, status: Optional[str] = None) -> List[BacktestJob]:
        """
        List all backtest jobs
        
        Args:
            status: Optional status filter
            
        Returns:
            List of BacktestJob objects
        """
        jobs = list(self.jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs
    
    def cancel_job(self, job_id: UUID) -> bool:
        """
        Cancel a pending or running job
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        job = self.get_job(job_id)
        
        if not job:
            return False
        
        if job.status in ['completed', 'failed']:
            return False
        
        # Update status
        job.status = 'cancelled'
        job.completed_at = datetime.utcnow()
        job.error = 'Cancelled by user'
        
        # Remove from running jobs if present
        self._running_jobs.discard(job_id)
        
        logger.info(f"Backtest job {job_id} cancelled")
        
        return True
    
    def optimize_strategy(self,
                         strategy_name: str,
                         symbol: str,
                         start_date: datetime,
                         end_date: datetime,
                         param_ranges: Dict[str, Any],
                         maximize: str = 'Sharpe Ratio') -> Dict[str, Any]:
        """
        Optimize strategy parameters
        
        Args:
            strategy_name: Name of strategy to optimize
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            param_ranges: Parameter ranges to optimize
            maximize: Metric to maximize
            
        Returns:
            Dictionary with optimal parameters and results
        """
        logger.info(f"Starting optimization for {strategy_name}")
        
        # Get strategy class
        strategy_class = self.handler._get_strategy_class(strategy_name)
        
        # Prepare data
        data = self.handler._prepare_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval='1h'
        )
        
        # Run optimization
        from src.infrastructure.backtesting import BacktestEngine
        engine = BacktestEngine()
        
        best_params, all_results = engine.optimize(
            data=data,
            strategy_class=strategy_class,
            maximize=maximize,
            **param_ranges
        )
        
        logger.info(f"Optimization complete. Best {maximize}: {best_params[maximize]}")
        
        return {
            'best_params': best_params.to_dict() if hasattr(best_params, 'to_dict') else dict(best_params),
            'best_metric': float(best_params[maximize]),
            'metric_name': maximize
        }
    
    def cleanup_old_jobs(self, days: int = 7):
        """
        Clean up old completed jobs
        
        Args:
            days: Number of days to keep jobs
        """
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