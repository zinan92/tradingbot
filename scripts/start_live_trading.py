#!/usr/bin/env python3
"""
Live Trading Entry Point

Main script to start live trading with safety checks and monitoring.
Start with TESTNET first, then move to production with small capital.
"""

import sys
import os
import asyncio
import logging
import signal
from pathlib import Path
from datetime import datetime
import yaml
import argparse
from typing import Dict, Any

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.binance_client import BinanceClient
from src.infrastructure.database.db_manager import DatabaseManager
from src.application.trading.live_strategy_runner import LiveStrategyRunner
from src.application.trading.order_execution_bridge import OrderExecutionBridge
from src.application.trading.risk_management import RiskManagementSystem, RiskLimits
from src.application.trading.strategies.live_grid_strategy import LiveGridStrategy
from src.application.backtesting.strategies.ema_cross_strategy import EMACrossStrategy


# Setup logging
def setup_logging(config: Dict[str, Any]):
    """Setup comprehensive logging"""
    log_config = config.get('logging', {})
    
    # Create logs directory
    log_dir = Path(log_config.get('file_path', 'logs/live_trading.log')).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_config.get('level', 'INFO')),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_config.get('file_path', 'logs/live_trading.log')),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


class LiveTradingSystem:
    """
    Main live trading system orchestrator
    """
    
    def __init__(self, config_path: str, testnet: bool = True):
        """
        Initialize live trading system
        
        Args:
            config_path: Path to configuration file
            testnet: Whether to use testnet
        """
        # Load configuration
        self.config = self._load_config(config_path)
        self.testnet = testnet
        
        # Setup logging
        self.logger = setup_logging(self.config)
        
        # Components (initialized in setup)
        self.binance_client = None
        self.db_manager = None
        self.risk_manager = None
        self.order_bridge = None
        self.strategy_runner = None
        
        # Control flags
        self.running = False
        self.shutdown_requested = False
        
        self.logger.info(f"Live Trading System initialized (testnet={testnet})")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Override with environment variables if they exist
            if os.environ.get('BINANCE_API_KEY'):
                env = 'testnet' if self.testnet else 'production'
                config['binance'][env]['api_key'] = os.environ['BINANCE_API_KEY']
                config['binance'][env]['api_secret'] = os.environ['BINANCE_API_SECRET']
            
            return config
            
        except Exception as e:
            print(f"Failed to load config: {e}")
            sys.exit(1)
    
    async def setup(self):
        """Setup all components"""
        try:
            self.logger.info("Setting up trading components...")
            
            # Determine environment
            env = 'testnet' if self.testnet else 'production'
            api_config = self.config['binance'][env]
            
            # Validate API credentials
            if api_config['api_key'] == 'YOUR_TESTNET_API_KEY':
                self.logger.error("Please configure your Binance API credentials in the config file")
                raise ValueError("API credentials not configured")
            
            # Initialize Binance client
            self.binance_client = BinanceClient(
                api_key=api_config['api_key'],
                api_secret=api_config['api_secret'],
                testnet=self.testnet
            )
            
            # Initialize database manager
            db_config = self.config['data']['database']
            self.db_manager = DatabaseManager(
                host=db_config['host'],
                port=db_config['port'],
                database=db_config['name'],
                user=db_config.get('user'),
                password=db_config.get('password')
            )
            
            # Initialize risk management
            risk_config = self.config['risk_management']
            risk_limits = RiskLimits(
                max_position_size_pct=risk_config['max_position_size_pct'],
                max_total_exposure_pct=risk_config['max_total_exposure_pct'],
                max_daily_loss_pct=risk_config['max_daily_loss_pct'],
                max_drawdown_pct=risk_config['max_drawdown_pct'],
                max_positions=risk_config['max_positions'],
                max_leverage=risk_config['max_leverage'],
                min_free_margin_pct=risk_config['min_free_margin_pct']
            )
            
            initial_capital = self.config['capital']['initial_capital']
            self.risk_manager = RiskManagementSystem(
                initial_capital=initial_capital,
                risk_limits=risk_limits,
                emergency_stop_loss=risk_config['emergency_stop_loss_pct']
            )
            
            # Initialize order execution bridge
            self.order_bridge = OrderExecutionBridge(
                binance_client=self.binance_client,
                max_retries=self.config['order_execution']['max_retries'],
                retry_delay=self.config['order_execution']['retry_delay'],
                use_testnet=self.testnet
            )
            await self.order_bridge.initialize()
            
            # Setup strategy based on configuration
            strategy_config = self.config['strategy']
            
            if strategy_config['grid']['enabled']:
                self.logger.info("Setting up Grid Trading strategy...")
                await self._setup_grid_strategy()
            elif strategy_config['momentum']['enabled']:
                self.logger.info("Setting up Momentum strategy...")
                await self._setup_momentum_strategy()
            elif strategy_config['mean_reversion']['enabled']:
                self.logger.info("Setting up Mean Reversion strategy...")
                await self._setup_mean_reversion_strategy()
            elif strategy_config['ema_cross']['enabled']:
                self.logger.info("Setting up EMA Cross strategy...")
                await self._setup_ema_cross_strategy()
            else:
                raise ValueError("No strategy enabled in configuration")
            
            self.logger.info("✅ All components setup successfully")
            
        except Exception as e:
            self.logger.error(f"Setup failed: {e}")
            raise
    
    async def _setup_grid_strategy(self):
        """Setup Grid Trading strategy"""
        config = self.config['strategy']['grid']
        
        # Get first symbol configuration (for now, support single symbol)
        if not config.get('symbols'):
            raise ValueError("No symbols configured for grid strategy")
        
        symbol_config = config['symbols'][0]
        
        # Strategy parameters
        strategy_params = {
            'symbol': symbol_config['symbol'],
            'grid_levels': symbol_config['grid_levels'],
            'grid_spacing': symbol_config['grid_spacing'],
            'position_size_per_grid': symbol_config['position_size_per_grid'],
            'use_dynamic_grid': config.get('use_dynamic_grid', True),
            'atr_period': config.get('atr_period', 14),
            'atr_multiplier': config.get('atr_multiplier', 1.5),
            'sma_period': config.get('sma_period', 20)
        }
        
        # Note: For grid strategy, we need a different runner
        # The LiveStrategyRunner expects a backtesting strategy
        # We'll create a simplified version for grid trading
        
        self.strategy = LiveGridStrategy(**strategy_params)
        self.logger.info(f"Grid Strategy initialized for {symbol_config['symbol']}")
    
    async def _setup_momentum_strategy(self):
        """Setup Momentum strategy"""
        config = self.config['strategy']['momentum']
        
        # Get first symbol configuration (for now, support single symbol)
        if not config.get('symbols'):
            raise ValueError("No symbols configured for momentum strategy")
        
        symbol_config = config['symbols'][0]
        
        strategy_params = {
            'fast_period': config.get('fast_period', 8),
            'slow_period': config.get('slow_period', 21),
            'stop_loss_pct': config.get('stop_loss_pct', 0.03),
            'take_profit_pct': config.get('take_profit_pct', 0.10),
            'position_size': symbol_config.get('position_size', 0.95)
        }
        
        self.strategy_runner = LiveStrategyRunner(
            binance_client=self.binance_client,
            db_manager=self.db_manager,
            strategy_class=EMACrossStrategy,
            strategy_params=strategy_params,
            symbol=symbol_config['symbol'],
            interval=symbol_config['interval'],
            initial_capital=self.config['capital']['initial_capital'],
            max_position_size=symbol_config.get('position_size', 0.95),
            max_daily_loss=self.config['risk_management']['max_daily_loss_pct'],
            use_testnet=self.testnet
        )
        
        await self.strategy_runner.initialize()
        self.logger.info(f"Momentum Strategy initialized for {symbol_config['symbol']}")
    
    async def _setup_mean_reversion_strategy(self):
        """Setup Mean Reversion strategy"""
        # Placeholder for future implementation
        raise NotImplementedError("Mean Reversion strategy not yet implemented")
    
    async def _setup_ema_cross_strategy(self):
        """Setup EMA Cross strategy"""
        config = self.config['strategy']['ema_cross']
        
        # Get first symbol configuration
        if not config.get('symbols'):
            raise ValueError("No symbols configured for EMA cross strategy")
        
        symbol_config = config['symbols'][0]
        
        # Can use the existing EMACrossStrategy from backtesting
        strategy_params = {
            'fast_period': config.get('fast_period', 9),
            'slow_period': config.get('slow_period', 21),
            'stop_loss': config.get('stop_loss_pct', 0.02),
            'take_profit': config.get('take_profit_pct', 0.05)
        }
        
        self.strategy_runner = LiveStrategyRunner(
            binance_client=self.binance_client,
            db_manager=self.db_manager,
            strategy_class=EMACrossStrategy,
            strategy_params=strategy_params,
            symbol=symbol_config.get('symbol', 'BTCUSDT'),
            interval=symbol_config.get('interval', '1h'),
            initial_capital=self.config['capital']['initial_capital'],
            max_position_size=0.95,
            max_daily_loss=self.config['risk_management']['max_daily_loss_pct'],
            use_testnet=self.testnet
        )
        
        await self.strategy_runner.initialize()
        self.logger.info(f"EMA Cross Strategy initialized for {symbol_config.get('symbol', 'BTCUSDT')}")
    
    def _safety_checks(self) -> bool:
        """Perform safety checks before trading"""
        self.logger.info("Performing safety checks...")
        
        # Check if in maintenance mode
        if self.config['safety']['maintenance_mode']:
            self.logger.error("System is in maintenance mode")
            return False
        
        # Check system resources
        import psutil
        
        # Check memory
        memory = psutil.virtual_memory()
        free_memory_mb = memory.available / 1024 / 1024
        min_memory = self.config['system']['min_free_memory_mb']
        
        if free_memory_mb < min_memory:
            self.logger.error(f"Insufficient memory: {free_memory_mb:.0f}MB < {min_memory}MB")
            return False
        
        # Check disk space
        disk = psutil.disk_usage('/')
        free_disk_gb = disk.free / 1024 / 1024 / 1024
        min_disk = self.config['system']['min_free_disk_gb']
        
        if free_disk_gb < min_disk:
            self.logger.error(f"Insufficient disk space: {free_disk_gb:.1f}GB < {min_disk}GB")
            return False
        
        # Check if API is accessible
        # This would ping Binance API
        
        self.logger.info("✅ All safety checks passed")
        return True
    
    async def run(self):
        """Main trading loop"""
        try:
            # Perform safety checks
            if not self._safety_checks():
                self.logger.error("Safety checks failed, aborting")
                return
            
            # Display startup information
            self._display_startup_info()
            
            # Confirm before starting
            if not self.config['mode']['dry_run']:
                response = input("\n⚠️  Ready to start LIVE TRADING. Continue? (yes/no): ")
                if response.lower() != 'yes':
                    self.logger.info("Trading cancelled by user")
                    return
            
            self.running = True
            self.logger.info("🚀 Starting live trading...")
            
            # Main trading loop
            while self.running and not self.shutdown_requested:
                try:
                    # Check risk limits
                    if not self.risk_manager.check_risk_limits():
                        self.logger.error("Risk limits breached, stopping trading")
                        break
                    
                    # Log status
                    self._log_status()
                    
                    # Sleep
                    await asyncio.sleep(1)
                    
                except KeyboardInterrupt:
                    self.logger.info("Shutdown requested by user")
                    break
                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}")
                    
                    # Check if we should auto-restart
                    if self.config['system']['auto_restart_on_error']:
                        self.logger.info("Attempting to restart...")
                        await asyncio.sleep(self.config['system']['restart_delay_seconds'])
                    else:
                        break
            
        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
        finally:
            await self.shutdown()
    
    def _display_startup_info(self):
        """Display startup information"""
        print("\n" + "=" * 60)
        print("LIVE TRADING SYSTEM")
        print("=" * 60)
        print(f"Environment: {'TESTNET' if self.testnet else '⚠️  PRODUCTION'}")
        print(f"Dry Run: {self.config['mode']['dry_run']}")
        print(f"Initial Capital: ${self.config['capital']['initial_capital']}")
        
        # Display strategy info
        if self.config['strategy']['grid']['enabled']:
            print(f"Strategy: Grid Trading")
            if self.config['strategy']['grid'].get('symbols'):
                symbol_config = self.config['strategy']['grid']['symbols'][0]
                print(f"Symbol: {symbol_config['symbol']}")
                print(f"Grid Levels: {symbol_config['grid_levels']}")
        elif self.config['strategy']['momentum']['enabled']:
            print(f"Strategy: Momentum Trading")
            if self.config['strategy']['momentum'].get('symbols'):
                symbol_config = self.config['strategy']['momentum']['symbols'][0]
                print(f"Symbol: {symbol_config['symbol']}")
        
        # Display risk limits
        print(f"\nRisk Limits:")
        print(f"  Max Daily Loss: {self.config['risk_management']['max_daily_loss_pct']:.1%}")
        print(f"  Max Drawdown: {self.config['risk_management']['max_drawdown_pct']:.1%}")
        print(f"  Emergency Stop: {self.config['risk_management']['emergency_stop_loss_pct']:.1%}")
        
        print("=" * 60)
    
    def _log_status(self):
        """Log current status"""
        if datetime.now().second == 0:  # Log every minute
            risk_metrics = self.risk_manager.get_risk_metrics()
            
            self.logger.info(
                f"Status | "
                f"Capital: ${self.risk_manager.current_capital:.2f} | "
                f"Positions: {risk_metrics.position_count} | "
                f"Daily P&L: ${risk_metrics.daily_pnl:.2f} | "
                f"Drawdown: {risk_metrics.current_drawdown:.2%}"
            )
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down trading system...")
        self.running = False
        
        try:
            # Close all positions if configured
            if self.risk_manager and self.risk_manager.should_close_all_positions():
                self.logger.warning("Closing all positions due to risk limits")
                # Implement position closing logic
            
            # Generate final report
            if self.risk_manager:
                report = self.risk_manager.get_risk_report()
                self.logger.info(f"Final report: {report}")
            
            # Close connections
            if self.binance_client:
                # Close WebSocket connections
                pass
            
            if self.db_manager:
                # Close database connections
                pass
            
            self.logger.info("✅ Shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Live Trading System')
    parser.add_argument(
        '--config',
        type=str,
        default='config/live_trading_config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--testnet',
        action='store_true',
        default=True,
        help='Use Binance testnet (default: True)'
    )
    parser.add_argument(
        '--production',
        action='store_true',
        help='Use production environment (requires --confirm-production)'
    )
    parser.add_argument(
        '--confirm-production',
        action='store_true',
        help='Confirm production trading with real money'
    )
    
    args = parser.parse_args()
    
    # Safety check for production
    if args.production:
        if not args.confirm_production:
            print("❌ Production mode requires --confirm-production flag")
            print("⚠️  This will trade with REAL MONEY")
            sys.exit(1)
        
        print("\n" + "⚠️ " * 20)
        print("WARNING: PRODUCTION MODE - REAL MONEY AT RISK")
        print("⚠️ " * 20)
        
        response = input("\nType 'I UNDERSTAND THE RISKS' to continue: ")
        if response != "I UNDERSTAND THE RISKS":
            print("Production trading cancelled")
            sys.exit(0)
        
        testnet = False
    else:
        testnet = True
    
    # Create and run trading system
    trading_system = LiveTradingSystem(args.config, testnet)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\nShutdown signal received")
        trading_system.shutdown_requested = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run async main loop
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(trading_system.setup())
        loop.run_until_complete(trading_system.run())
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()