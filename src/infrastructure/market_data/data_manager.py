"""
Data Manager for storage management, validation, and maintenance

This module handles:
- Storage space monitoring
- Data compression and archival
- Data validation and integrity checks
- Database maintenance operations
"""

import os
import logging
import shutil
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import psutil
from sqlalchemy import text
from sqlalchemy.orm import Session
import pandas as pd
import gzip
import json

from ..persistence.postgres.market_data_repository import MarketDataRepository
from ..persistence.postgres.market_data_tables import Base

logger = logging.getLogger(__name__)

class DataManager:
    """
    Manages storage, validation, and maintenance of market data
    """
    
    def __init__(self, db_session: Session, data_dir: str = "/tmp/market_data"):
        self.db_session = db_session
        self.repository = MarketDataRepository(db_session)
        self.data_dir = data_dir
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Storage thresholds
        self.min_free_space_gb = 10  # Minimum free space required
        self.compression_threshold_days = 30  # Compress data older than this
        self.archive_threshold_days = 365  # Archive data older than this
        
    def check_storage_space(self) -> Dict[str, Any]:
        """
        Check available storage space
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            # Get disk usage statistics
            disk_usage = psutil.disk_usage('/')
            
            # Get database size
            db_size = self._get_database_size()
            
            storage_info = {
                'total_gb': disk_usage.total / (1024**3),
                'used_gb': disk_usage.used / (1024**3),
                'free_gb': disk_usage.free / (1024**3),
                'percent_used': disk_usage.percent,
                'database_size_mb': db_size / (1024**2),
                'sufficient_space': disk_usage.free / (1024**3) > self.min_free_space_gb,
                'data_dir_size_mb': self._get_directory_size(self.data_dir) / (1024**2)
            }
            
            if not storage_info['sufficient_space']:
                logger.warning(f"Low disk space: {storage_info['free_gb']:.2f} GB remaining")
            
            return storage_info
            
        except Exception as e:
            logger.error(f"Error checking storage space: {e}")
            return {}
    
    def _get_database_size(self) -> int:
        """Get the size of the database in bytes"""
        try:
            result = self.db_session.execute(
                text("SELECT pg_database_size(current_database())")
            ).scalar()
            return result or 0
        except Exception as e:
            logger.error(f"Error getting database size: {e}")
            return 0
    
    def _get_directory_size(self, path: str) -> int:
        """Get the size of a directory in bytes"""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total += os.path.getsize(filepath)
        except Exception as e:
            logger.error(f"Error calculating directory size: {e}")
        return total
    
    def validate_data_integrity(self,
                              symbols: List[str],
                              intervals: List[str],
                              start_date: datetime,
                              end_date: datetime) -> Dict[str, Any]:
        """
        Validate data integrity and completeness
        
        Args:
            symbols: List of symbols to validate
            intervals: List of intervals to validate
            start_date: Start date of validation range
            end_date: End date of validation range
            
        Returns:
            Validation report
        """
        report = {
            'summary': {},
            'details': {},
            'issues': [],
            'statistics': {}
        }
        
        total_issues = 0
        
        for symbol in symbols:
            symbol_report = {
                'intervals': {},
                'issues': []
            }
            
            for interval in intervals:
                interval_report = self._validate_symbol_interval(
                    symbol, interval, start_date, end_date
                )
                symbol_report['intervals'][interval] = interval_report
                
                if interval_report['issues']:
                    symbol_report['issues'].extend(interval_report['issues'])
                    total_issues += len(interval_report['issues'])
            
            report['details'][symbol] = symbol_report
        
        # Generate summary
        report['summary'] = {
            'symbols_checked': len(symbols),
            'intervals_checked': len(intervals),
            'total_issues': total_issues,
            'validation_time': datetime.now().isoformat(),
            'date_range': f"{start_date.date()} to {end_date.date()}"
        }
        
        return report
    
    def _validate_symbol_interval(self,
                                 symbol: str,
                                 interval: str,
                                 start_date: datetime,
                                 end_date: datetime) -> Dict[str, Any]:
        """
        Validate data for a single symbol/interval combination
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_date: Start date
            end_date: End date
            
        Returns:
            Validation report for this combination
        """
        issues = []
        
        try:
            # Get data statistics
            count = self.repository.count_klines(symbol, interval, start_date, end_date)
            
            if count == 0:
                issues.append({
                    'type': 'missing_data',
                    'message': f"No data found for {symbol} {interval}"
                })
                return {'count': 0, 'issues': issues}
            
            # Check for gaps
            gaps = self.repository.get_data_gaps(symbol, interval, start_date, end_date)
            if gaps:
                for gap_start, gap_end in gaps:
                    duration = (gap_end - gap_start).total_seconds() / 3600  # hours
                    if duration > 1:  # Only report gaps longer than 1 hour
                        issues.append({
                            'type': 'data_gap',
                            'message': f"Gap from {gap_start} to {gap_end} ({duration:.1f} hours)",
                            'gap_start': gap_start.isoformat(),
                            'gap_end': gap_end.isoformat()
                        })
            
            # Check for duplicate data
            duplicates = self._check_duplicates(symbol, interval, start_date, end_date)
            if duplicates:
                issues.append({
                    'type': 'duplicates',
                    'message': f"Found {duplicates} duplicate entries",
                    'count': duplicates
                })
            
            # Check for data anomalies
            anomalies = self._check_anomalies(symbol, interval, start_date, end_date)
            if anomalies:
                issues.extend(anomalies)
            
            # Calculate completeness
            expected_count = self._calculate_expected_candles(interval, start_date, end_date)
            completeness = (count / expected_count * 100) if expected_count > 0 else 0
            
            return {
                'count': count,
                'expected_count': expected_count,
                'completeness_pct': completeness,
                'gaps': len(gaps),
                'issues': issues
            }
            
        except Exception as e:
            logger.error(f"Error validating {symbol} {interval}: {e}")
            issues.append({
                'type': 'validation_error',
                'message': str(e)
            })
            return {'count': 0, 'issues': issues}
    
    def _check_duplicates(self, 
                         symbol: str, 
                         interval: str,
                         start_date: datetime,
                         end_date: datetime) -> int:
        """Check for duplicate entries"""
        try:
            from sqlalchemy import func
            from ..persistence.postgres.market_data_tables import KlineData
            
            # Count duplicates
            subquery = self.db_session.query(
                KlineData.symbol,
                KlineData.interval,
                KlineData.open_time,
                func.count('*').label('count')
            ).filter(
                KlineData.symbol == symbol,
                KlineData.interval == interval,
                KlineData.open_time >= start_date,
                KlineData.open_time <= end_date
            ).group_by(
                KlineData.symbol,
                KlineData.interval,
                KlineData.open_time
            ).having(func.count('*') > 1).subquery()
            
            duplicate_count = self.db_session.query(func.sum(subquery.c.count)).scalar()
            return duplicate_count or 0
            
        except Exception as e:
            logger.error(f"Error checking duplicates: {e}")
            return 0
    
    def _check_anomalies(self,
                        symbol: str,
                        interval: str,
                        start_date: datetime,
                        end_date: datetime) -> List[Dict[str, Any]]:
        """Check for data anomalies"""
        anomalies = []
        
        try:
            klines = self.repository.get_klines(symbol, interval, start_date, end_date, limit=100000)
            
            if not klines:
                return anomalies
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame([{
                'open': k.open_price,
                'high': k.high_price,
                'low': k.low_price,
                'close': k.close_price,
                'volume': k.volume,
                'time': k.open_time
            } for k in klines])
            
            # Check for zero prices
            zero_prices = df[(df['open'] == 0) | (df['high'] == 0) | 
                            (df['low'] == 0) | (df['close'] == 0)]
            if not zero_prices.empty:
                anomalies.append({
                    'type': 'zero_prices',
                    'message': f"Found {len(zero_prices)} candles with zero prices",
                    'count': len(zero_prices)
                })
            
            # Check for invalid OHLC relationships
            invalid_ohlc = df[(df['high'] < df['low']) | 
                             (df['high'] < df['open']) | 
                             (df['high'] < df['close']) |
                             (df['low'] > df['open']) | 
                             (df['low'] > df['close'])]
            if not invalid_ohlc.empty:
                anomalies.append({
                    'type': 'invalid_ohlc',
                    'message': f"Found {len(invalid_ohlc)} candles with invalid OHLC relationships",
                    'count': len(invalid_ohlc)
                })
            
            # Check for extreme price spikes (>50% change)
            df['price_change'] = df['close'].pct_change().abs()
            extreme_changes = df[df['price_change'] > 0.5]
            if not extreme_changes.empty:
                anomalies.append({
                    'type': 'extreme_price_change',
                    'message': f"Found {len(extreme_changes)} candles with >50% price change",
                    'count': len(extreme_changes),
                    'max_change': f"{df['price_change'].max() * 100:.2f}%"
                })
            
            # Check for zero volume
            zero_volume = df[df['volume'] == 0]
            if len(zero_volume) > len(df) * 0.1:  # More than 10% with zero volume
                anomalies.append({
                    'type': 'excessive_zero_volume',
                    'message': f"{len(zero_volume)} candles ({len(zero_volume)/len(df)*100:.1f}%) have zero volume",
                    'count': len(zero_volume)
                })
            
        except Exception as e:
            logger.error(f"Error checking anomalies: {e}")
            anomalies.append({
                'type': 'anomaly_check_error',
                'message': str(e)
            })
        
        return anomalies
    
    def _calculate_expected_candles(self, interval: str, start_date: datetime, end_date: datetime) -> int:
        """Calculate expected number of candles for a time range"""
        duration = end_date - start_date
        minutes = duration.total_seconds() / 60
        
        interval_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480,
            '12h': 720, '1d': 1440, '3d': 4320, '1w': 10080, '1M': 43200
        }
        
        if interval in interval_minutes:
            return int(minutes / interval_minutes[interval])
        return 0
    
    def compress_old_data(self, days_old: int = 30) -> Dict[str, Any]:
        """
        Compress old data to save storage space
        
        Args:
            days_old: Compress data older than this many days
            
        Returns:
            Compression statistics
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)
        stats = {
            'files_compressed': 0,
            'space_saved_mb': 0,
            'errors': []
        }
        
        try:
            # Export old data to compressed files
            for table_name in ['kline_data', 'trade_data', 'orderbook_snapshots']:
                result = self._export_and_compress_table(table_name, cutoff_date)
                if result['success']:
                    stats['files_compressed'] += 1
                    stats['space_saved_mb'] += result['space_saved_mb']
                else:
                    stats['errors'].append(result['error'])
            
            logger.info(f"Compression complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error compressing old data: {e}")
            stats['errors'].append(str(e))
            return stats
    
    def _export_and_compress_table(self, table_name: str, cutoff_date: datetime) -> Dict[str, Any]:
        """Export and compress a single table's old data"""
        try:
            # Create export file path
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = os.path.join(self.data_dir, f"{table_name}_{timestamp}.json")
            compressed_file = f"{export_file}.gz"
            
            # Query old data
            query = text(f"""
                SELECT * FROM {table_name}
                WHERE created_at < :cutoff_date
                ORDER BY created_at
                LIMIT 100000
            """)
            
            result = self.db_session.execute(query, {'cutoff_date': cutoff_date})
            rows = result.fetchall()
            
            if not rows:
                return {'success': False, 'error': f"No old data in {table_name}"}
            
            # Convert to JSON and write compressed
            data = [dict(row) for row in rows]
            
            # Handle datetime serialization
            def json_serial(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            with gzip.open(compressed_file, 'wt', encoding='utf-8') as f:
                json.dump(data, f, default=json_serial)
            
            # Calculate space saved
            original_size = len(json.dumps(data, default=json_serial).encode())
            compressed_size = os.path.getsize(compressed_file)
            space_saved = (original_size - compressed_size) / (1024**2)
            
            logger.info(f"Compressed {table_name}: {len(rows)} rows, saved {space_saved:.2f} MB")
            
            return {
                'success': True,
                'rows_exported': len(rows),
                'space_saved_mb': space_saved,
                'file': compressed_file
            }
            
        except Exception as e:
            logger.error(f"Error exporting {table_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def optimize_database(self) -> Dict[str, Any]:
        """
        Optimize database performance
        
        Returns:
            Optimization statistics
        """
        stats = {
            'tables_analyzed': [],
            'indexes_rebuilt': [],
            'vacuum_complete': False,
            'errors': []
        }
        
        try:
            # Analyze tables for query optimization
            tables = ['kline_data', 'orderbook_snapshots', 'trade_data', 
                     'indicator_values', 'market_metrics']
            
            for table in tables:
                try:
                    self.db_session.execute(text(f"ANALYZE {table}"))
                    stats['tables_analyzed'].append(table)
                except Exception as e:
                    stats['errors'].append(f"Error analyzing {table}: {e}")
            
            # Reindex for better performance
            try:
                self.db_session.execute(text("REINDEX DATABASE CONCURRENTLY"))
                stats['indexes_rebuilt'] = tables
            except Exception as e:
                stats['errors'].append(f"Error rebuilding indexes: {e}")
            
            # Vacuum to reclaim space
            try:
                self.db_session.execute(text("VACUUM ANALYZE"))
                stats['vacuum_complete'] = True
            except Exception as e:
                stats['errors'].append(f"Error vacuuming: {e}")
            
            self.db_session.commit()
            
            logger.info(f"Database optimization complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            self.db_session.rollback()
            stats['errors'].append(str(e))
            return stats
    
    def create_backup(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a backup of critical data
        
        Args:
            backup_dir: Directory to store backup (default: data_dir/backups)
            
        Returns:
            Backup statistics
        """
        if backup_dir is None:
            backup_dir = os.path.join(self.data_dir, 'backups')
        
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_stats = {
            'timestamp': timestamp,
            'tables_backed_up': [],
            'total_size_mb': 0,
            'errors': []
        }
        
        try:
            # Backup symbol info (critical configuration)
            symbol_backup = os.path.join(backup_dir, f"symbol_info_{timestamp}.json.gz")
            symbols = self.db_session.execute(text("SELECT * FROM symbol_info")).fetchall()
            
            with gzip.open(symbol_backup, 'wt') as f:
                json.dump([dict(s) for s in symbols], f, default=str)
            
            backup_stats['tables_backed_up'].append('symbol_info')
            backup_stats['total_size_mb'] += os.path.getsize(symbol_backup) / (1024**2)
            
            # Backup recent indicator values
            indicator_backup = os.path.join(backup_dir, f"indicators_{timestamp}.json.gz")
            indicators = self.db_session.execute(
                text("SELECT * FROM indicator_values WHERE created_at > NOW() - INTERVAL '7 days'")
            ).fetchall()
            
            with gzip.open(indicator_backup, 'wt') as f:
                json.dump([dict(i) for i in indicators], f, default=str)
            
            backup_stats['tables_backed_up'].append('indicator_values')
            backup_stats['total_size_mb'] += os.path.getsize(indicator_backup) / (1024**2)
            
            logger.info(f"Backup created: {backup_stats}")
            return backup_stats
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            backup_stats['errors'].append(str(e))
            return backup_stats
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics"""
        stats = {
            'storage': self.check_storage_space(),
            'database': {},
            'data_dir': {}
        }
        
        try:
            # Database statistics
            for table in ['kline_data', 'trade_data', 'orderbook_snapshots', 
                         'indicator_values', 'market_metrics']:
                count_result = self.db_session.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                ).scalar()
                
                size_result = self.db_session.execute(
                    text(f"SELECT pg_total_relation_size('{table}')")
                ).scalar()
                
                stats['database'][table] = {
                    'row_count': count_result or 0,
                    'size_mb': (size_result or 0) / (1024**2)
                }
            
            # Data directory statistics
            for root, dirs, files in os.walk(self.data_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    if file.endswith('.gz'):
                        if 'compressed_files' not in stats['data_dir']:
                            stats['data_dir']['compressed_files'] = []
                        stats['data_dir']['compressed_files'].append({
                            'name': file,
                            'size_mb': os.path.getsize(filepath) / (1024**2)
                        })
            
        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
        
        return stats