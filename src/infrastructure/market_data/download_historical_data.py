#!/usr/bin/env python3
"""
Main script to download 3 years of historical market data for top 30 Binance Futures symbols

This script orchestrates the entire process:
1. Fetches top 30 symbols by volume
2. Downloads historical kline data for multiple intervals
3. Calculates technical indicators
4. Validates data integrity
5. Provides progress tracking and resume capability
"""

import asyncio
import logging
import sys
import os
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.persistence.postgres.market_data_tables import Base
from src.infrastructure.market_data.bulk_data_loader import BulkDataLoader
from src.infrastructure.market_data.data_manager import DataManager
from src.infrastructure.indicators.indicator_service import IndicatorService
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download_historical_data.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HistoricalDataDownloader:
    """
    Orchestrates the download and processing of historical market data
    """
    
    def __init__(self, 
                 database_url: str,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 config_file: str = 'download_config.json'):
        
        # Database setup
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db_session = Session()
        
        # Services setup
        self.bulk_loader = BulkDataLoader(self.db_session, api_key, api_secret)
        self.data_manager = DataManager(self.db_session)
        self.event_bus = InMemoryEventBus()
        self.indicator_service = IndicatorService(self.db_session, self.event_bus)
        
        # Configuration
        self.config_file = config_file
        self.config = self.load_config()
        
        # Progress tracking
        self.progress_file = 'download_progress.json'
        self.progress = self.load_progress()
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        default_config = {
            'top_symbols_count': 30,
            'years_back': 3,
            'intervals': ['5m', '15m', '30m', '1h', '2h', '4h', '1d'],
            'parallel_workers': 4,
            'batch_size': 1000,
            'calculate_indicators': True,
            'validate_data': True,
            'cleanup_on_error': False,
            'custom_symbols': []  # Override top symbols with custom list
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
                    logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.warning(f"Error loading config file: {e}, using defaults")
        
        return default_config
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def load_progress(self) -> Dict[str, Any]:
        """Load progress from previous run"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)
                    logger.info("Loaded progress from previous run")
                    return progress
            except Exception as e:
                logger.warning(f"Error loading progress file: {e}")
        
        return {
            'symbols_downloaded': [],
            'indicators_calculated': [],
            'validation_complete': False,
            'start_time': None,
            'last_update': None
        }
    
    def save_progress(self):
        """Save current progress"""
        self.progress['last_update'] = datetime.now().isoformat()
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(self.progress, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving progress: {e}")
    
    async def run(self):
        """Main execution method"""
        try:
            logger.info("=" * 80)
            logger.info("HISTORICAL DATA DOWNLOAD STARTED")
            logger.info("=" * 80)
            
            self.progress['start_time'] = datetime.now().isoformat()
            
            # Step 1: Check storage space
            logger.info("\n📊 Step 1: Checking storage space...")
            storage_info = self.data_manager.check_storage_space()
            logger.info(f"Free space: {storage_info['free_gb']:.2f} GB")
            
            if not storage_info['sufficient_space']:
                logger.error("Insufficient storage space! Need at least 10 GB free.")
                if not self.confirm_continue("Continue anyway?"):
                    return
            
            # Step 2: Get symbols to download
            logger.info("\n🎯 Step 2: Getting symbols to download...")
            symbols = await self.get_symbols_to_download()
            logger.info(f"Will download data for {len(symbols)} symbols: {symbols[:5]}...")
            
            # Step 3: Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * self.config['years_back'])
            logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
            
            # Step 4: Estimate data volume
            logger.info("\n📈 Step 4: Estimating data volume...")
            estimated_candles = self.estimate_total_candles(symbols)
            estimated_storage_gb = estimated_candles * 200 / (1024**3)  # ~200 bytes per candle
            logger.info(f"Estimated candles: {estimated_candles:,}")
            logger.info(f"Estimated storage: {estimated_storage_gb:.2f} GB")
            
            if not self.confirm_continue(f"Download {estimated_candles:,} candles (~{estimated_storage_gb:.2f} GB)?"):
                return
            
            # Step 5: Start services
            logger.info("\n🚀 Step 5: Starting services...")
            await self.bulk_loader.start()
            
            # Step 6: Download historical data
            logger.info("\n📥 Step 6: Downloading historical data...")
            download_stats = await self.download_data(symbols, start_date, end_date)
            
            # Step 7: Calculate indicators (if enabled)
            if self.config['calculate_indicators']:
                logger.info("\n📊 Step 7: Calculating technical indicators...")
                indicator_stats = await self.calculate_indicators(symbols, start_date, end_date)
            else:
                logger.info("\n⏭️  Step 7: Skipping indicator calculation (disabled in config)")
                indicator_stats = None
            
            # Step 8: Validate data (if enabled)
            if self.config['validate_data']:
                logger.info("\n✅ Step 8: Validating data integrity...")
                validation_report = await self.validate_data(symbols, start_date, end_date)
            else:
                logger.info("\n⏭️  Step 8: Skipping data validation (disabled in config)")
                validation_report = None
            
            # Step 9: Optimize database
            logger.info("\n🔧 Step 9: Optimizing database...")
            optimization_stats = self.data_manager.optimize_database()
            
            # Step 10: Generate final report
            logger.info("\n📋 Step 10: Generating final report...")
            final_report = self.generate_final_report(
                download_stats, indicator_stats, validation_report, optimization_stats
            )
            
            # Save report
            report_file = f"download_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(final_report, f, indent=2, default=str)
            
            logger.info(f"Report saved to {report_file}")
            
            # Print summary
            self.print_summary(final_report)
            
            logger.info("\n" + "=" * 80)
            logger.info("DOWNLOAD COMPLETED SUCCESSFULLY! ✨")
            logger.info("=" * 80)
            
        except KeyboardInterrupt:
            logger.warning("\n\n⚠️  Download interrupted by user")
            self.save_progress()
            logger.info("Progress saved. Run again to resume.")
            
        except Exception as e:
            logger.error(f"\n\n❌ Error during download: {e}")
            self.save_progress()
            raise
            
        finally:
            # Cleanup
            await self.cleanup()
    
    async def get_symbols_to_download(self) -> List[str]:
        """Get list of symbols to download"""
        # Check if custom symbols are specified
        if self.config.get('custom_symbols'):
            symbols = self.config['custom_symbols']
            logger.info(f"Using custom symbols from config: {symbols}")
        else:
            # Get top symbols by volume
            symbols = await self.bulk_loader.get_top_futures_symbols(
                self.config['top_symbols_count']
            )
        
        # Filter out already completed symbols if resuming
        if self.progress['symbols_downloaded']:
            remaining = [s for s in symbols if s not in self.progress['symbols_downloaded']]
            logger.info(f"Resuming download. {len(self.progress['symbols_downloaded'])} symbols already complete.")
            logger.info(f"Remaining symbols: {remaining}")
            return remaining
        
        return symbols
    
    async def download_data(self, 
                           symbols: List[str],
                           start_date: datetime,
                           end_date: datetime) -> Dict[str, Any]:
        """Download historical data for all symbols"""
        
        # Download in batches to avoid overwhelming the system
        batch_size = 5  # Process 5 symbols at a time
        all_stats = {
            'total_candles': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'download_time': 0
        }
        
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            logger.info(f"\nDownloading batch {i//batch_size + 1}/{(len(symbols) + batch_size - 1)//batch_size}")
            logger.info(f"Symbols: {batch}")
            
            stats = await self.bulk_loader.download_historical_data(
                symbols=batch,
                intervals=self.config['intervals'],
                start_date=start_date,
                end_date=end_date
            )
            
            # Update overall statistics
            all_stats['total_candles'] += stats['total_candles']
            all_stats['successful_downloads'] += stats['successful']
            all_stats['failed_downloads'] += stats['failed']
            all_stats['download_time'] += stats['download_time']
            
            # Update progress
            self.progress['symbols_downloaded'].extend(batch)
            self.save_progress()
            
            # Brief pause between batches
            if i + batch_size < len(symbols):
                logger.info("Pausing 10 seconds before next batch...")
                await asyncio.sleep(10)
        
        return all_stats
    
    async def calculate_indicators(self,
                                  symbols: List[str],
                                  start_date: datetime,
                                  end_date: datetime) -> Dict[str, Any]:
        """Calculate indicators for all downloaded data"""
        
        # Filter to only calculate for downloaded symbols
        symbols_to_calculate = [
            s for s in symbols 
            if s in self.progress['symbols_downloaded'] and 
            s not in self.progress.get('indicators_calculated', [])
        ]
        
        if not symbols_to_calculate:
            logger.info("All indicators already calculated")
            return {'total_indicators': 0}
        
        logger.info(f"Calculating indicators for {len(symbols_to_calculate)} symbols")
        
        stats = await self.indicator_service.batch_calculate_historical(
            symbols=symbols_to_calculate,
            intervals=self.config['intervals'],
            start_date=start_date,
            end_date=end_date,
            parallel_workers=self.config['parallel_workers']
        )
        
        # Update progress
        if 'indicators_calculated' not in self.progress:
            self.progress['indicators_calculated'] = []
        self.progress['indicators_calculated'].extend(symbols_to_calculate)
        self.save_progress()
        
        return stats
    
    async def validate_data(self,
                           symbols: List[str],
                           start_date: datetime,
                           end_date: datetime) -> Dict[str, Any]:
        """Validate downloaded data"""
        
        validation_report = self.data_manager.validate_data_integrity(
            symbols=symbols,
            intervals=self.config['intervals'],
            start_date=start_date,
            end_date=end_date
        )
        
        # Mark validation as complete
        self.progress['validation_complete'] = True
        self.save_progress()
        
        return validation_report
    
    def estimate_total_candles(self, symbols: List[str]) -> int:
        """Estimate total number of candles to download"""
        days = 365 * self.config['years_back']
        
        candles_per_day = {
            '1m': 1440, '3m': 480, '5m': 288, '15m': 96,
            '30m': 48, '1h': 24, '2h': 12, '4h': 6,
            '6h': 4, '8h': 3, '12h': 2, '1d': 1
        }
        
        total = 0
        for interval in self.config['intervals']:
            if interval in candles_per_day:
                total += candles_per_day[interval] * days * len(symbols)
        
        return total
    
    def generate_final_report(self,
                             download_stats: Dict[str, Any],
                             indicator_stats: Optional[Dict[str, Any]],
                             validation_report: Optional[Dict[str, Any]],
                             optimization_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive final report"""
        
        report = {
            'execution_time': datetime.now().isoformat(),
            'configuration': self.config,
            'download_statistics': download_stats,
            'indicator_statistics': indicator_stats,
            'validation_report': validation_report,
            'optimization_statistics': optimization_stats,
            'storage_statistics': self.data_manager.get_storage_statistics(),
            'progress': self.progress
        }
        
        # Calculate totals
        if download_stats:
            report['summary'] = {
                'total_candles_downloaded': download_stats.get('total_candles', 0),
                'total_indicators_calculated': indicator_stats.get('total_indicators', 0) if indicator_stats else 0,
                'data_completeness': validation_report['summary']['completeness_pct'] if validation_report else 0,
                'total_download_time_hours': download_stats.get('download_time', 0) / 3600,
                'database_size_gb': report['storage_statistics']['storage']['database_size_mb'] / 1024
            }
        
        return report
    
    def print_summary(self, report: Dict[str, Any]):
        """Print a nice summary of the download"""
        
        print("\n" + "=" * 80)
        print("DOWNLOAD SUMMARY")
        print("=" * 80)
        
        if 'summary' in report:
            summary = report['summary']
            print(f"📊 Total Candles Downloaded: {summary['total_candles_downloaded']:,}")
            print(f"📈 Total Indicators Calculated: {summary['total_indicators_calculated']:,}")
            print(f"✅ Data Completeness: {summary['data_completeness']:.1f}%")
            print(f"⏱️  Total Download Time: {summary['total_download_time_hours']:.2f} hours")
            print(f"💾 Database Size: {summary['database_size_gb']:.2f} GB")
        
        if 'download_statistics' in report:
            stats = report['download_statistics']
            print(f"\n📥 Download Statistics:")
            print(f"   - Successful: {stats.get('successful_downloads', 0)}")
            print(f"   - Failed: {stats.get('failed_downloads', 0)}")
        
        if 'validation_report' in report and report['validation_report']:
            val = report['validation_report']['summary']
            print(f"\n✅ Validation Results:")
            print(f"   - Complete: {val['complete']}")
            print(f"   - Incomplete: {val['incomplete']}")
            print(f"   - Missing: {val['missing']}")
            print(f"   - Total Issues: {val['total_issues']}")
        
        print("=" * 80)
    
    def confirm_continue(self, message: str) -> bool:
        """Ask user for confirmation"""
        if os.environ.get('NON_INTERACTIVE'):
            return True
        
        response = input(f"\n{message} (y/n): ").lower()
        return response == 'y'
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            await self.bulk_loader.stop()
            await self.indicator_service.stop()
            self.db_session.close()
            self.engine.dispose()
            logger.info("Cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

async def main():
    """Main entry point"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Download historical market data from Binance Futures'
    )
    parser.add_argument(
        '--database-url',
        default=os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost/tradingbot'),
        help='PostgreSQL database URL'
    )
    parser.add_argument(
        '--api-key',
        default=os.environ.get('BINANCE_API_KEY'),
        help='Binance API key (optional for public data)'
    )
    parser.add_argument(
        '--api-secret',
        default=os.environ.get('BINANCE_API_SECRET'),
        help='Binance API secret (optional for public data)'
    )
    parser.add_argument(
        '--config',
        default='download_config.json',
        help='Configuration file path'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Specific symbols to download (overrides top symbols)'
    )
    parser.add_argument(
        '--intervals',
        nargs='+',
        default=['5m', '15m', '30m', '1h', '2h', '4h', '1d'],
        help='Intervals to download'
    )
    parser.add_argument(
        '--years',
        type=int,
        default=3,
        help='Number of years of data to download'
    )
    parser.add_argument(
        '--no-indicators',
        action='store_true',
        help='Skip indicator calculation'
    )
    parser.add_argument(
        '--no-validation',
        action='store_true',
        help='Skip data validation'
    )
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Run without user prompts'
    )
    
    args = parser.parse_args()
    
    # Set environment for non-interactive mode
    if args.non_interactive:
        os.environ['NON_INTERACTIVE'] = '1'
    
    # Create downloader
    downloader = HistoricalDataDownloader(
        database_url=args.database_url,
        api_key=args.api_key,
        api_secret=args.api_secret,
        config_file=args.config
    )
    
    # Override config with command line arguments
    if args.symbols:
        downloader.config['custom_symbols'] = args.symbols
    if args.intervals:
        downloader.config['intervals'] = args.intervals
    if args.years:
        downloader.config['years_back'] = args.years
    if args.no_indicators:
        downloader.config['calculate_indicators'] = False
    if args.no_validation:
        downloader.config['validate_data'] = False
    
    # Save updated config
    downloader.save_config()
    
    # Run the download
    await downloader.run()

if __name__ == "__main__":
    asyncio.run(main())