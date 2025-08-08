"""
Backtest Repository

Repository for persisting and retrieving backtest results from PostgreSQL.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID
import asyncpg
from asyncpg import Connection, Pool

from src.domain.strategy.value_objects.strategy_configuration import StrategyConfiguration

logger = logging.getLogger(__name__)


class BacktestRepository:
    """
    Repository for backtest results persistence.
    
    Handles:
    - Saving backtest results to database
    - Retrieving historical results
    - Querying by various filters
    - Performance metrics aggregation
    """
    
    def __init__(self, connection_pool: Pool):
        """
        Initialize the repository.
        
        Args:
            connection_pool: AsyncPG connection pool
        """
        self.pool = connection_pool
    
    async def save_backtest_result(self,
                                  job_id: UUID,
                                  strategy_config: StrategyConfiguration,
                                  result: Any) -> None:
        """
        Save main backtest result to database.
        
        Args:
            job_id: Unique job identifier
            strategy_config: Strategy configuration used
            result: UnifiedBacktestResult object
        """
        async with self.pool.acquire() as conn:
            try:
                # Prepare portfolio stats
                portfolio_stats = result.portfolio_stats or {}
                
                # Insert main backtest result
                await conn.execute("""
                    INSERT INTO backtest_results (
                        id,
                        strategy_name,
                        symbol,
                        interval,
                        start_date,
                        end_date,
                        initial_capital,
                        leverage,
                        market_commission,
                        limit_commission,
                        strategy_params,
                        base_return_pct,
                        leveraged_return_pct,
                        sharpe_ratio,
                        max_drawdown_pct,
                        win_rate_pct,
                        total_trades,
                        status,
                        created_at,
                        completed_at,
                        execution_time_ms,
                        full_stats
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19,
                        $20, $21, $22
                    )
                """,
                    job_id,
                    strategy_config.strategy_id.id,
                    'PORTFOLIO',  # Special symbol for portfolio results
                    strategy_config.interval,
                    result.start_time,
                    result.end_time,
                    result.initial_capital,
                    strategy_config.leverage,
                    strategy_config.market_commission,
                    strategy_config.limit_commission,
                    json.dumps(strategy_config.params),
                    portfolio_stats.get('avg_return', 0),
                    portfolio_stats.get('total_return', 0),
                    portfolio_stats.get('avg_sharpe_ratio', 0),
                    portfolio_stats.get('worst_drawdown', 0),
                    portfolio_stats.get('avg_win_rate', 0),
                    portfolio_stats.get('total_trades', 0),
                    'completed',
                    result.created_at,
                    datetime.utcnow(),
                    result.execution_time_ms,
                    json.dumps(portfolio_stats)
                )
                
                logger.info(f"Saved backtest result {job_id} to database")
                
            except Exception as e:
                logger.error(f"Failed to save backtest result: {str(e)}")
                raise
    
    async def save_symbol_result(self,
                                job_id: UUID,
                                symbol: str,
                                result: Any) -> None:
        """
        Save individual symbol backtest result.
        
        Args:
            job_id: Parent job identifier
            symbol: Trading symbol
            result: SymbolBacktestResult object
        """
        async with self.pool.acquire() as conn:
            try:
                stats = result.stats
                futures_metrics = result.futures_metrics or {}
                
                # Insert symbol-specific result
                await conn.execute("""
                    INSERT INTO backtest_results (
                        id,
                        strategy_name,
                        symbol,
                        interval,
                        start_date,
                        end_date,
                        initial_capital,
                        base_return_pct,
                        leveraged_return_pct,
                        sharpe_ratio,
                        sortino_ratio,
                        calmar_ratio,
                        max_drawdown_pct,
                        win_rate_pct,
                        profit_factor,
                        kelly_criterion,
                        sqn,
                        total_trades,
                        long_trades,
                        short_trades,
                        winning_trades,
                        losing_trades,
                        long_win_rate_pct,
                        short_win_rate_pct,
                        avg_trade_pct,
                        best_trade_pct,
                        worst_trade_pct,
                        volatility_annual_pct,
                        leveraged_volatility_pct,
                        status,
                        created_at,
                        chart_html,
                        full_stats
                    ) VALUES (
                        gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9,
                        $10, $11, $12, $13, $14, $15, $16, $17, $18, $19,
                        $20, $21, $22, $23, $24, $25, $26, $27, $28, $29,
                        $30, $31, $32, $33
                    )
                """,
                    f"{symbol}_{job_id}",  # Composite strategy name
                    symbol,
                    '1h',  # Default interval
                    stats.get('Start', datetime.utcnow()),
                    stats.get('End', datetime.utcnow()),
                    stats.get('Initial Capital', 10000),
                    stats.get('Base Return [%]', stats.get('Return [%]', 0)),
                    stats.get('Leveraged Return [%]', stats.get('Return [%]', 0)),
                    stats.get('Sharpe Ratio', 0),
                    stats.get('Sortino Ratio', 0),
                    stats.get('Calmar Ratio', 0),
                    stats.get('Max. Drawdown [%]', 0),
                    stats.get('Win Rate [%]', 0),
                    stats.get('Profit Factor', 0),
                    stats.get('Kelly Criterion', 0),
                    stats.get('SQN', 0),
                    stats.get('# Trades', 0),
                    futures_metrics.get('total_longs', 0),
                    futures_metrics.get('total_shorts', 0),
                    int(stats.get('# Trades', 0) * stats.get('Win Rate [%]', 0) / 100),
                    int(stats.get('# Trades', 0) * (100 - stats.get('Win Rate [%]', 0)) / 100),
                    futures_metrics.get('long_win_rate', 0),
                    futures_metrics.get('short_win_rate', 0),
                    stats.get('Avg. Trade [%]', 0),
                    stats.get('Best Trade [%]', 0),
                    stats.get('Worst Trade [%]', 0),
                    stats.get('Volatility (Ann.) [%]', 0),
                    stats.get('Leveraged Volatility [%]', 0),
                    'completed',
                    datetime.utcnow(),
                    result.chart_html,
                    json.dumps(result.to_dict())
                )
                
                # Save trades if available
                if not result.trades.empty:
                    await self._save_trades(conn, job_id, symbol, result.trades)
                
                logger.info(f"Saved symbol result for {symbol} to database")
                
            except Exception as e:
                logger.error(f"Failed to save symbol result: {str(e)}")
                raise
    
    async def _save_trades(self,
                          conn: Connection,
                          job_id: UUID,
                          symbol: str,
                          trades: Any) -> None:
        """
        Save individual trades to database.
        
        Args:
            conn: Database connection
            job_id: Parent job identifier
            symbol: Trading symbol
            trades: DataFrame of trades
        """
        try:
            # Prepare trade data
            trade_records = []
            
            for idx, trade in trades.iterrows():
                direction = trade.get('Direction', 'LONG')
                if direction not in ['LONG', 'SHORT']:
                    direction = 'LONG' if trade.get('Size', 0) > 0 else 'SHORT'
                
                trade_records.append((
                    job_id,
                    idx + 1,  # Trade number
                    direction,
                    trade.get('EntryTime', datetime.utcnow()),
                    trade.get('ExitTime', datetime.utcnow()),
                    float(trade.get('EntryPrice', 0)),
                    float(trade.get('ExitPrice', 0)),
                    float(abs(trade.get('Size', 0))),
                    float(trade.get('PnL', 0)),
                    float(trade.get('ReturnPct', 0)),
                    float(trade.get('LeveragedReturnPct', trade.get('ReturnPct', 0))),
                    float(trade.get('EntryCommission', 0)),
                    float(trade.get('ExitCommission', 0)),
                    str(trade.get('Duration', '0:00:00')),
                    trade.get('EntryReason', 'Signal'),
                    trade.get('ExitReason', 'Signal')
                ))
            
            # Bulk insert trades
            await conn.executemany("""
                INSERT INTO backtest_trades (
                    backtest_id,
                    trade_num,
                    direction,
                    entry_time,
                    exit_time,
                    entry_price,
                    exit_price,
                    size,
                    pnl,
                    pnl_pct,
                    leveraged_pnl_pct,
                    entry_commission,
                    exit_commission,
                    duration,
                    entry_reason,
                    exit_reason
                ) VALUES (
                    $1, $2, $3::position_direction, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14::interval, $15, $16
                )
            """, trade_records)
            
            logger.debug(f"Saved {len(trade_records)} trades for {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to save trades: {str(e)}")
            # Don't re-raise, trades are optional
    
    async def get_backtest_results(self,
                                  strategy_id: Optional[str] = None,
                                  symbol: Optional[str] = None,
                                  start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical backtest results with filters.
        
        Args:
            strategy_id: Filter by strategy
            symbol: Filter by symbol
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results to return
        
        Returns:
            List of backtest results
        """
        async with self.pool.acquire() as conn:
            try:
                # Build query with filters
                query = """
                    SELECT 
                        id,
                        strategy_name,
                        symbol,
                        interval,
                        start_date,
                        end_date,
                        initial_capital,
                        leverage,
                        leveraged_return_pct,
                        sharpe_ratio,
                        max_drawdown_pct,
                        win_rate_pct,
                        total_trades,
                        status,
                        created_at,
                        execution_time_ms,
                        full_stats
                    FROM backtest_results
                    WHERE 1=1
                """
                
                params = []
                param_count = 0
                
                if strategy_id:
                    param_count += 1
                    query += f" AND strategy_name = ${param_count}"
                    params.append(strategy_id)
                
                if symbol:
                    param_count += 1
                    query += f" AND symbol = ${param_count}"
                    params.append(symbol)
                
                if start_date:
                    param_count += 1
                    query += f" AND start_date >= ${param_count}"
                    params.append(start_date)
                
                if end_date:
                    param_count += 1
                    query += f" AND end_date <= ${param_count}"
                    params.append(end_date)
                
                query += " ORDER BY created_at DESC"
                
                param_count += 1
                query += f" LIMIT ${param_count}"
                params.append(limit)
                
                # Execute query
                rows = await conn.fetch(query, *params)
                
                # Convert to dictionaries
                results = []
                for row in rows:
                    results.append({
                        'id': str(row['id']),
                        'strategy_name': row['strategy_name'],
                        'symbol': row['symbol'],
                        'interval': row['interval'],
                        'start_date': row['start_date'].isoformat(),
                        'end_date': row['end_date'].isoformat(),
                        'initial_capital': float(row['initial_capital']),
                        'leverage': float(row['leverage']),
                        'return_pct': float(row['leveraged_return_pct']),
                        'sharpe_ratio': float(row['sharpe_ratio']),
                        'max_drawdown_pct': float(row['max_drawdown_pct']),
                        'win_rate_pct': float(row['win_rate_pct']),
                        'total_trades': row['total_trades'],
                        'status': row['status'],
                        'created_at': row['created_at'].isoformat(),
                        'execution_time_ms': row['execution_time_ms'],
                        'full_stats': json.loads(row['full_stats']) if row['full_stats'] else {}
                    })
                
                return results
                
            except Exception as e:
                logger.error(f"Failed to get backtest results: {str(e)}")
                return []
    
    async def get_strategy_performance(self,
                                      strategy_id: str,
                                      days: int = 30) -> Dict[str, Any]:
        """
        Get aggregated performance metrics for a strategy.
        
        Args:
            strategy_id: Strategy identifier
            days: Number of days to look back
        
        Returns:
            Aggregated performance metrics
        """
        async with self.pool.acquire() as conn:
            try:
                result = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as backtest_count,
                        AVG(leveraged_return_pct) as avg_return,
                        MAX(leveraged_return_pct) as max_return,
                        MIN(leveraged_return_pct) as min_return,
                        AVG(sharpe_ratio) as avg_sharpe,
                        AVG(win_rate_pct) as avg_win_rate,
                        AVG(total_trades) as avg_trades,
                        SUM(total_trades) as total_trades
                    FROM backtest_results
                    WHERE strategy_name = $1
                    AND created_at > CURRENT_DATE - INTERVAL '%s days'
                    AND status = 'completed'
                """ % days, strategy_id)
                
                if result:
                    return {
                        'strategy_id': strategy_id,
                        'period_days': days,
                        'backtest_count': result['backtest_count'],
                        'avg_return': float(result['avg_return'] or 0),
                        'max_return': float(result['max_return'] or 0),
                        'min_return': float(result['min_return'] or 0),
                        'avg_sharpe': float(result['avg_sharpe'] or 0),
                        'avg_win_rate': float(result['avg_win_rate'] or 0),
                        'avg_trades': float(result['avg_trades'] or 0),
                        'total_trades': result['total_trades'] or 0
                    }
                
                return {}
                
            except Exception as e:
                logger.error(f"Failed to get strategy performance: {str(e)}")
                return {}
    
    async def get_best_performers(self,
                                 metric: str = 'leveraged_return_pct',
                                 limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get best performing strategies by metric.
        
        Args:
            metric: Metric to sort by
            limit: Number of results
        
        Returns:
            List of best performers
        """
        async with self.pool.acquire() as conn:
            try:
                # Validate metric column
                valid_metrics = [
                    'leveraged_return_pct', 'sharpe_ratio', 'win_rate_pct',
                    'profit_factor', 'calmar_ratio', 'sortino_ratio'
                ]
                
                if metric not in valid_metrics:
                    metric = 'leveraged_return_pct'
                
                rows = await conn.fetch(f"""
                    SELECT 
                        strategy_name,
                        symbol,
                        {metric} as metric_value,
                        leveraged_return_pct,
                        sharpe_ratio,
                        max_drawdown_pct,
                        total_trades,
                        created_at
                    FROM backtest_results
                    WHERE status = 'completed'
                    AND symbol != 'PORTFOLIO'
                    ORDER BY {metric} DESC NULLS LAST
                    LIMIT $1
                """, limit)
                
                results = []
                for row in rows:
                    results.append({
                        'strategy_name': row['strategy_name'],
                        'symbol': row['symbol'],
                        'metric': metric,
                        'metric_value': float(row['metric_value'] or 0),
                        'return_pct': float(row['leveraged_return_pct'] or 0),
                        'sharpe_ratio': float(row['sharpe_ratio'] or 0),
                        'max_drawdown_pct': float(row['max_drawdown_pct'] or 0),
                        'total_trades': row['total_trades'],
                        'created_at': row['created_at'].isoformat()
                    })
                
                return results
                
            except Exception as e:
                logger.error(f"Failed to get best performers: {str(e)}")
                return []