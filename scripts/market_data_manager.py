#!/usr/bin/env python3
"""
Market Data Manager - Main entry point for all market data operations

Commands:
    download-historical  Download historical data for configured symbols
    start-live          Start live WebSocket streaming
    start-all           Download historical then start live streaming
    status              Show current data status
    check-gaps          Check for data gaps
    stop                Stop all data operations
"""

import asyncio
import sys
import os
import signal
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.market_data.unified_data_manager import UnifiedDataManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/market_data_manager.log')
    ]
)
logger = logging.getLogger(__name__)

class MarketDataManagerCLI:
    """Command-line interface for market data management"""
    
    def __init__(self):
        self.manager = None
        self.running = False
        
    async def initialize(self, config_path: str = None):
        """Initialize the data manager"""
        database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/tradingbot')
        
        self.manager = UnifiedDataManager(
            config_path=config_path,
            database_url=database_url
        )
        
        await self.manager.start()
        logger.info("Market Data Manager initialized")
        
    async def download_historical(self, symbols: list = None, days: int = None):
        """Download historical data"""
        try:
            print("\n" + "="*80)
            print("DOWNLOADING HISTORICAL DATA")
            print("="*80)
            
            # Use config if no symbols specified
            if not symbols:
                symbols = self.manager.config.get('symbols', [])
            
            days = days or self.manager.config.get('historical', {}).get('days_back', 30)
            
            print(f"Symbols: {len(symbols)}")
            print(f"Days: {days}")
            print(f"Intervals: {self.manager.config.get('intervals', [])}")
            print("\nStarting download...")
            
            await self.manager.download_historical(
                symbols=symbols,
                days_back=days
            )
            
            print("\n✅ Historical download complete!")
            
        except Exception as e:
            logger.error(f"Error downloading historical data: {e}")
            print(f"\n❌ Error: {e}")
            
    async def start_live(self, symbols: list = None):
        """Start live streaming"""
        try:
            print("\n" + "="*80)
            print("STARTING LIVE DATA STREAMING")
            print("="*80)
            
            if not symbols:
                symbols = self.manager.config.get('symbols', [])
            
            print(f"Symbols: {len(symbols)}")
            print("\nStarting WebSocket connections...")
            
            await self.manager.start_live_streaming(symbols=symbols)
            
            print("\n✅ Live streaming started!")
            print("Press Ctrl+C to stop...")
            
            # Keep running
            self.running = True
            while self.running:
                await asyncio.sleep(60)
                
                # Print periodic status
                status = self.manager.get_status()
                active_streams = status['market_service_stats']['active_streams']
                print(f"\r⚡ Active streams: {active_streams} | Updates: {status['market_service_stats']['klines_received']:,}", end='')
                
        except KeyboardInterrupt:
            print("\n\nStopping live streaming...")
        except Exception as e:
            logger.error(f"Error in live streaming: {e}")
            print(f"\n❌ Error: {e}")
            
    async def start_all(self, symbols: list = None):
        """Start hybrid mode - historical download then live streaming"""
        try:
            print("\n" + "="*80)
            print("STARTING HYBRID MODE (Historical + Live)")
            print("="*80)
            
            if not symbols:
                symbols = self.manager.config.get('symbols', [])
            
            print(f"Symbols: {len(symbols)}")
            
            await self.manager.start_hybrid_mode(symbols=symbols)
            
            print("\n✅ Hybrid mode active!")
            print("Press Ctrl+C to stop...")
            
            # Keep running
            self.running = True
            while self.running:
                await asyncio.sleep(60)
                
                # Print periodic status
                status = self.manager.get_status()
                print(f"\r⚡ Mode: {status['mode']} | Active: {len(status['active_symbols'])} symbols", end='')
                
        except KeyboardInterrupt:
            print("\n\nStopping...")
        except Exception as e:
            logger.error(f"Error in hybrid mode: {e}")
            print(f"\n❌ Error: {e}")
            
    async def show_status(self):
        """Show current status"""
        try:
            print("\n" + "="*80)
            print("MARKET DATA STATUS")
            print("="*80)
            
            status = self.manager.get_status()
            
            print(f"\nMode: {status['mode']}")
            print(f"Active Symbols: {len(status['active_symbols'])}")
            
            if status['active_symbols']:
                print("\nLast Updates:")
                for symbol, update_info in status.get('last_updates', {}).items():
                    minutes_ago = update_info.get('minutes_ago', 0)
                    if minutes_ago < 10:
                        status_icon = "🟢"
                    elif minutes_ago < 60:
                        status_icon = "🟡"
                    else:
                        status_icon = "🔴"
                    
                    print(f"  {status_icon} {symbol}: {minutes_ago:.1f} minutes ago")
            
            # Market service stats
            ms_stats = status.get('market_service_stats', {})
            print(f"\nMarket Service:")
            print(f"  Active Streams: {ms_stats.get('active_streams', 0)}")
            print(f"  Klines Received: {ms_stats.get('klines_received', 0):,}")
            print(f"  Events Published: {ms_stats.get('events_published', 0):,}")
            print(f"  Errors: {ms_stats.get('errors', 0)}")
            
            # Database stats
            db_stats = status.get('database_stats', {}).get('database', {})
            if db_stats:
                print(f"\nDatabase:")
                total_rows = 0
                total_size = 0
                for table, info in db_stats.items():
                    rows = info.get('row_count', 0)
                    size = info.get('size_mb', 0)
                    total_rows += rows
                    total_size += size
                    if rows > 0:
                        print(f"  {table}: {rows:,} rows ({size:.1f} MB)")
                
                print(f"  Total: {total_rows:,} rows ({total_size:.1f} MB)")
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            print(f"\n❌ Error: {e}")
            
    async def check_gaps(self):
        """Check for data gaps"""
        try:
            print("\n" + "="*80)
            print("CHECKING DATA COMPLETENESS")
            print("="*80)
            
            report = await self.manager.check_data_completeness()
            
            summary = report['summary']
            print(f"\nSummary:")
            print(f"  Total Symbols: {summary['total_symbols']}")
            print(f"  Complete: {summary['complete_symbols']} ✅")
            print(f"  Incomplete: {summary['incomplete_symbols']} ⚠️")
            print(f"  Total Candles: {summary['total_candles']:,}")
            
            if summary['incomplete_symbols'] > 0:
                print(f"\nIncomplete Symbols:")
                for symbol, data in report['symbols'].items():
                    if not data['is_complete']:
                        print(f"\n  {symbol}:")
                        for interval, info in data['intervals'].items():
                            if info['completeness_pct'] < 95:
                                print(f"    {interval}: {info['completeness_pct']:.1f}% complete "
                                     f"({info['count']}/{info['expected']} candles)")
            
        except Exception as e:
            logger.error(f"Error checking gaps: {e}")
            print(f"\n❌ Error: {e}")
            
    async def cleanup(self):
        """Clean up resources"""
        if self.manager:
            await self.manager.stop()
            
    def handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        print("\n\nReceived shutdown signal...")
        self.running = False


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Market Data Manager')
    parser.add_argument('command', choices=[
        'download-historical',
        'start-live', 
        'start-all',
        'status',
        'check-gaps',
        'test'
    ], help='Command to execute')
    
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--symbols', nargs='+', help='Symbols to process')
    parser.add_argument('--days', type=int, help='Days of historical data')
    
    args = parser.parse_args()
    
    cli = MarketDataManagerCLI()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, cli.handle_signal)
    signal.signal(signal.SIGTERM, cli.handle_signal)
    
    try:
        # Initialize
        await cli.initialize(config_path=args.config)
        
        # Execute command
        if args.command == 'download-historical':
            await cli.download_historical(
                symbols=args.symbols,
                days=args.days
            )
            
        elif args.command == 'start-live':
            await cli.start_live(symbols=args.symbols)
            
        elif args.command == 'start-all':
            await cli.start_all(symbols=args.symbols)
            
        elif args.command == 'status':
            await cli.show_status()
            
        elif args.command == 'check-gaps':
            await cli.check_gaps()
            
        elif args.command == 'test':
            # Quick test with limited symbols
            print("\n🧪 Running test mode with BTCUSDT...")
            await cli.manager.download_historical(
                symbols=['BTCUSDT'],
                intervals=['5m'],
                days_back=1
            )
            await cli.show_status()
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
        
    finally:
        await cli.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        print(f"\n❌ Unhandled error: {e}")
        sys.exit(1)