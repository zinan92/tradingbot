"""
Batch Backtest Engine

Implementation of batch backtesting with parameter optimization.
"""
import asyncio
import csv
import itertools
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from decimal import Decimal

try:
    from tqdm.asyncio import tqdm as atqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

from src.domain.shared.ports.backtest_port import BacktestPort
from src.domain.shared.ports.strategy_registry_port import StrategyRegistryPort
from src.infrastructure.backtesting.artifact_writer import BacktestArtifactWriter


class BatchBacktestEngine(BacktestPort):
    """
    Batch backtest engine with parameter optimization
    
    Runs multiple backtests across parameter combinations,
    selects the best parameters, and persists them to the registry.
    """
    
    def __init__(
        self,
        backtest_engine,  # Underlying single backtest engine
        strategy_registry: Optional[StrategyRegistryPort] = None,
        output_dir: str = "artifacts",
        max_workers: int = 4,
        max_search_space: int = 10000
    ):
        """
        Initialize batch backtest engine
        
        Args:
            backtest_engine: Engine for running individual backtests
            strategy_registry: Registry for persisting best parameters
            output_dir: Directory for output artifacts
            max_workers: Maximum concurrent backtests
            max_search_space: Maximum allowed parameter combinations
        """
        self.backtest_engine = backtest_engine
        self.strategy_registry = strategy_registry
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_writer = BacktestArtifactWriter(str(self.output_dir))
        self.max_workers = max_workers
        self.max_search_space = max_search_space
    
    async def run(self, input_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single backtest"""
        return await self.backtest_engine.run(input_config)
    
    async def validate_config(self, config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate backtest configuration"""
        return await self.backtest_engine.validate_config(config)
    
    async def estimate_duration(self, config: Dict[str, Any]) -> float:
        """Estimate backtest duration"""
        return await self.backtest_engine.estimate_duration(config)
    
    async def get_available_data_range(self, symbol: str, interval: str) -> tuple[datetime, datetime]:
        """Get available data range"""
        return await self.backtest_engine.get_available_data_range(symbol, interval)
    
    async def run_batch(
        self,
        strategy_name: str,
        search_space: Dict[str, List[Any]],
        base_config: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Path]:
        """
        Run batch backtests with parameter optimization
        
        Args:
            strategy_name: Name of the strategy to optimize
            search_space: Parameter combinations to test
            base_config: Base configuration for all runs
            
        Returns:
            Tuple of (best_params, leaderboard_path)
        """
        print(f"\n{'='*60}")
        print(f"BATCH BACKTEST: {strategy_name}")
        print(f"{'='*60}")
        
        # Validate search space size
        param_combinations = self._generate_param_combinations(search_space)
        total_combinations = len(param_combinations)
        
        if total_combinations > self.max_search_space:
            raise ValueError(
                f"Search space too large: {total_combinations} combinations "
                f"(max: {self.max_search_space}). Reduce parameter ranges or increase max_search_space."
            )
        
        if total_combinations == 0:
            raise ValueError("Empty search space provided")
        
        print(f"Parameter combinations to test: {total_combinations}")
        print(f"Search space: {search_space}")
        print(f"Max concurrent workers: {self.max_workers}")
        
        # Track timing
        start_time = time.time()
        
        # Run backtests with concurrency control
        if self.max_workers > 1:
            results = await self._run_concurrent_backtests(
                strategy_name, param_combinations, base_config
            )
        else:
            results = await self._run_sequential_backtests(
                strategy_name, param_combinations, base_config
            )
        
        # Calculate total time
        total_time = time.time() - start_time
        avg_time = total_time / total_combinations if total_combinations > 0 else 0
        
        # Select best parameters
        best_params, best_result = self._select_best_params(results)
        
        # Generate leaderboard
        leaderboard_path = self._write_leaderboard(results, strategy_name)
        
        # Persist best parameters to registry if available
        if self.strategy_registry and best_params:
            await self._persist_best_params(strategy_name, best_params, best_result)
        
        print(f"\n{'='*60}")
        print(f"OPTIMIZATION COMPLETE")
        print(f"Total time: {total_time:.1f}s (avg {avg_time:.2f}s per backtest)")
        print(f"Best parameters: {best_params}")
        print(f"Best Sharpe: {best_result['sharpe']:.2f}")
        print(f"Best MaxDD: {best_result['max_dd']:.1f}%")
        print(f"Leaderboard: {leaderboard_path}")
        print(f"{'='*60}")
        
        return best_params, leaderboard_path
    
    async def _run_concurrent_backtests(
        self,
        strategy_name: str,
        param_combinations: List[Dict[str, Any]],
        base_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Run backtests concurrently with controlled parallelism
        
        Args:
            strategy_name: Strategy name
            param_combinations: List of parameter combinations
            base_config: Base configuration
            
        Returns:
            List of results
        """
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def run_with_semaphore(params: Dict[str, Any], index: int) -> Dict[str, Any]:
            """Run single backtest with semaphore control"""
            async with semaphore:
                # Merge params with base config
                config = {**base_config}
                config['strategy'] = strategy_name
                config['params'] = params
                
                try:
                    # Run single backtest
                    result = await self._run_single_backtest(config)
                    
                    # Extract metrics
                    metrics = result.get('metrics', {})
                    
                    return {
                        'params': params,
                        'sharpe': metrics.get('sharpe', 0.0),
                        'profit_factor': metrics.get('profit_factor', 0.0),
                        'win_rate': metrics.get('win_rate', 0.0),
                        'max_dd': metrics.get('max_dd', 100.0),
                        'returns': metrics.get('returns', 0.0),
                        'total_trades': metrics.get('total_trades', 0),
                        'status': 'success'
                    }
                    
                except Exception as e:
                    return {
                        'params': params,
                        'sharpe': -999,
                        'profit_factor': 0,
                        'win_rate': 0,
                        'max_dd': 100,
                        'returns': -100,
                        'total_trades': 0,
                        'status': f'failed: {str(e)}'
                    }
        
        # Create tasks for all combinations
        tasks = [
            run_with_semaphore(params, i) 
            for i, params in enumerate(param_combinations)
        ]
        
        # Use tqdm if available for progress tracking
        if TQDM_AVAILABLE:
            # Run with progress bar
            results = []
            with atqdm(total=len(tasks), desc=f"Optimizing {strategy_name}") as pbar:
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    
                    # Update progress bar with metrics
                    if result['status'] == 'success':
                        pbar.set_postfix({
                            'Sharpe': f"{result['sharpe']:.2f}",
                            'MaxDD': f"{result['max_dd']:.1f}%"
                        })
                    pbar.update(1)
        else:
            # Run without progress bar
            print(f"Running {len(tasks)} backtests concurrently...")
            results = await asyncio.gather(*tasks)
            
        return results
    
    async def _run_sequential_backtests(
        self,
        strategy_name: str,
        param_combinations: List[Dict[str, Any]],
        base_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Run backtests sequentially (fallback for max_workers=1)
        
        Args:
            strategy_name: Strategy name
            param_combinations: List of parameter combinations
            base_config: Base configuration
            
        Returns:
            List of results
        """
        results = []
        total = len(param_combinations)
        
        for i, params in enumerate(param_combinations, 1):
            print(f"\n[{i}/{total}] Testing parameters: {params}")
            
            # Merge params with base config
            config = {**base_config}
            config['strategy'] = strategy_name
            config['params'] = params
            
            try:
                # Run single backtest
                result = await self._run_single_backtest(config)
                
                # Extract metrics
                metrics = result.get('metrics', {})
                
                # Store result with parameters
                results.append({
                    'params': params,
                    'sharpe': metrics.get('sharpe', 0.0),
                    'profit_factor': metrics.get('profit_factor', 0.0),
                    'win_rate': metrics.get('win_rate', 0.0),
                    'max_dd': metrics.get('max_dd', 100.0),
                    'returns': metrics.get('returns', 0.0),
                    'total_trades': metrics.get('total_trades', 0),
                    'status': 'success'
                })
                
                print(f"   ✓ Sharpe: {metrics.get('sharpe', 0):.2f}, "
                      f"MaxDD: {metrics.get('max_dd', 0):.1f}%, "
                      f"Returns: {metrics.get('returns', 0):.1f}%")
                
            except Exception as e:
                print(f"   ✗ Backtest failed: {e}")
                results.append({
                    'params': params,
                    'sharpe': -999,
                    'profit_factor': 0,
                    'win_rate': 0,
                    'max_dd': 100,
                    'returns': -100,
                    'total_trades': 0,
                    'status': f'failed: {str(e)}'
                })
        
        return results
    
    def _generate_param_combinations(self, search_space: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """
        Generate all parameter combinations from search space
        
        Args:
            search_space: Dict of parameter names to lists of values
            
        Returns:
            List of parameter dictionaries
        """
        if not search_space:
            return [{}]
        
        # Get parameter names and value lists
        param_names = list(search_space.keys())
        param_values = [search_space[name] for name in param_names]
        
        # Generate all combinations
        combinations = []
        for values in itertools.product(*param_values):
            param_dict = dict(zip(param_names, values))
            combinations.append(param_dict)
        
        return combinations
    
    async def _run_single_backtest(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single backtest
        
        Args:
            config: Backtest configuration
            
        Returns:
            Backtest results with metrics
        """
        # Call the actual backtest engine
        return await self.backtest_engine.run(config)
    
    def _select_best_params(
        self,
        results: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Select best parameters based on Sharpe ratio with MaxDD tiebreaker
        
        Args:
            results: List of backtest results with parameters
            
        Returns:
            Tuple of (best_params, best_result)
        """
        if not results:
            return {}, {}
        
        # Filter out failed results
        valid_results = [r for r in results if r['status'] == 'success']
        
        if not valid_results:
            # Return first result even if failed
            return results[0]['params'], results[0]
        
        # Sort by Sharpe (descending) then by MaxDD (ascending)
        sorted_results = sorted(
            valid_results,
            key=lambda x: (-x['sharpe'], x['max_dd'])
        )
        
        best_result = sorted_results[0]
        return best_result['params'], best_result
    
    def _calculate_extended_metrics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate additional performance metrics
        
        Args:
            result: Backtest result with basic metrics
            
        Returns:
            Extended metrics dictionary
        """
        sharpe = result.get('sharpe', 0.0)
        max_dd = result.get('max_dd', 100.0)
        returns = result.get('returns', 0.0)
        win_rate = result.get('win_rate', 0.0)
        total_trades = result.get('total_trades', 0)
        
        # Calculate Calmar ratio (returns / max_dd)
        calmar_ratio = returns / max_dd if max_dd > 0 else 0.0
        
        # Calculate recovery factor (similar to Calmar but for total gains)
        recovery_factor = abs(returns) / max_dd if max_dd > 0 else 0.0
        
        # Calculate expectancy (average profit per trade)
        avg_profit_per_trade = returns / total_trades if total_trades > 0 else 0.0
        
        # Risk-adjusted metrics
        risk_reward_ratio = sharpe * (100 - max_dd) / 100 if sharpe > 0 else 0.0
        
        return {
            'calmar_ratio': round(calmar_ratio, 3),
            'recovery_factor': round(recovery_factor, 3),
            'avg_profit_per_trade': round(avg_profit_per_trade, 2),
            'risk_reward_ratio': round(risk_reward_ratio, 3),
            'trades_per_param': total_trades  # Useful for understanding strategy activity
        }
    
    def _write_leaderboard(
        self,
        results: List[Dict[str, Any]],
        strategy_name: str
    ) -> Path:
        """
        Write enhanced leaderboard CSV file with extended metrics
        
        Args:
            results: List of backtest results
            strategy_name: Name of the strategy
            
        Returns:
            Path to leaderboard file
        """
        leaderboard_path = self.output_dir / "leaderboard.csv"
        
        # Sort results by Sharpe then MaxDD
        sorted_results = sorted(
            results,
            key=lambda x: (-x['sharpe'] if x['status'] == 'success' else 999, 
                          x['max_dd'])
        )
        
        # Prepare rows for CSV with extended metrics
        rows = []
        for i, result in enumerate(sorted_results, 1):
            # Calculate extended metrics
            extended = self._calculate_extended_metrics(result) if result['status'] == 'success' else {
                'calmar_ratio': 0,
                'recovery_factor': 0,
                'avg_profit_per_trade': 0,
                'risk_reward_ratio': 0,
                'trades_per_param': 0
            }
            
            row = {
                'rank': i,
                'strategy': strategy_name,
                'sharpe': result['sharpe'],
                'calmar_ratio': extended['calmar_ratio'],
                'max_dd': result['max_dd'],
                'profit_factor': result['profit_factor'],
                'win_rate': result['win_rate'],
                'returns': result['returns'],
                'recovery_factor': extended['recovery_factor'],
                'avg_profit_per_trade': extended['avg_profit_per_trade'],
                'risk_reward_ratio': extended['risk_reward_ratio'],
                'total_trades': result['total_trades'],
                'status': result['status']
            }
            
            # Add parameter columns
            for param_name, param_value in result['params'].items():
                row[f'param_{param_name}'] = param_value
            
            rows.append(row)
        
        # Get all column names
        if rows:
            fieldnames = list(rows[0].keys())
        else:
            fieldnames = ['rank', 'strategy', 'sharpe', 'calmar_ratio', 'max_dd', 'status']
        
        # Write CSV
        with open(leaderboard_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        # Also generate a summary statistics file
        self._write_optimization_summary(sorted_results, strategy_name)
        
        return leaderboard_path
    
    def _write_optimization_summary(
        self,
        sorted_results: List[Dict[str, Any]],
        strategy_name: str
    ):
        """
        Write optimization summary with statistics
        
        Args:
            sorted_results: Sorted list of results
            strategy_name: Strategy name
        """
        summary_path = self.output_dir / "optimization_summary.json"
        
        successful = [r for r in sorted_results if r['status'] == 'success']
        failed = [r for r in sorted_results if r['status'] != 'success']
        
        if successful:
            # Calculate summary statistics
            sharpe_values = [r['sharpe'] for r in successful]
            returns_values = [r['returns'] for r in successful]
            max_dd_values = [r['max_dd'] for r in successful]
            
            summary = {
                'strategy': strategy_name,
                'total_combinations': len(sorted_results),
                'successful_runs': len(successful),
                'failed_runs': len(failed),
                'success_rate': round(len(successful) / len(sorted_results) * 100, 1),
                'best_sharpe': max(sharpe_values),
                'worst_sharpe': min(sharpe_values),
                'avg_sharpe': round(sum(sharpe_values) / len(sharpe_values), 2),
                'best_returns': max(returns_values),
                'worst_returns': min(returns_values),
                'avg_returns': round(sum(returns_values) / len(returns_values), 2),
                'best_max_dd': min(max_dd_values),
                'worst_max_dd': max(max_dd_values),
                'avg_max_dd': round(sum(max_dd_values) / len(max_dd_values), 2),
                'timestamp': datetime.now().isoformat()
            }
        else:
            summary = {
                'strategy': strategy_name,
                'total_combinations': len(sorted_results),
                'successful_runs': 0,
                'failed_runs': len(failed),
                'success_rate': 0,
                'error': 'All backtests failed',
                'timestamp': datetime.now().isoformat()
            }
        
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
    
    async def _persist_best_params(
        self,
        strategy_name: str,
        best_params: Dict[str, Any],
        best_result: Dict[str, Any]
    ):
        """
        Persist best parameters to strategy registry
        
        Args:
            strategy_name: Name of the strategy
            best_params: Best parameter values
            best_result: Best backtest result
        """
        if not self.strategy_registry:
            return
        
        try:
            # Create metadata
            metadata = {
                'optimized_at': datetime.now().isoformat(),
                'sharpe': best_result['sharpe'],
                'max_dd': best_result['max_dd'],
                'returns': best_result['returns'],
                'optimization_method': 'grid_search'
            }
            
            # Register or update strategy with best params
            await self.strategy_registry.register(
                name=strategy_name,
                version='optimized',
                params=best_params,
                metadata=metadata
            )
            
            print(f"✓ Best parameters persisted to registry for {strategy_name}")
            
        except Exception as e:
            print(f"✗ Failed to persist parameters: {e}")