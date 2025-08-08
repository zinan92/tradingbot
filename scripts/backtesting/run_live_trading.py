#!/usr/bin/env python
"""
Live Trading Runner

Main entry point for running live trading with configured strategies.
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime
from decimal import Decimal
from uuid import UUID
import os
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/live_trading_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)

logger = logging.getLogger(__name__)

# Import required modules
from src.config.trading_config import get_config, TradingMode
from src.infrastructure.messaging.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.persistence.postgres.repositories import (
    PostgresPortfolioRepository,
    PostgresOrderRepository,
    PostgresPositionRepository
)
from src.application.trading.services.live_trading_service import LiveTradingService
from src.application.trading.services.state_recovery_service import StateRecoveryService
from src.application.trading.services.strategy_bridge import StrategyBridge, OptimalGridStrategyLive
from src.application.trading.services.pretrade_risk_validator import PreTradeRiskValidator
from src.application.trading.adapters.signal_order_adapter import SignalOrderAdapter
from src.application.trading.adapters.live_broker_adapter import LiveBrokerAdapter, BrokerType
from src.infrastructure.brokers.binance_futures_broker import BinanceFuturesBroker


class LiveTradingRunner:
    """
    Main runner for live trading operations.
    """
    
    def __init__(self):
        """Initialize the live trading runner"""
        self.config = get_config()
        self.event_bus = InMemoryEventBus()
        
        # Services
        self.live_trading_service = None
        self.state_recovery_service = None
        self.strategy_bridge = None
        self.risk_validator = None
        self.signal_adapter = None
        self.broker_adapter = None
        
        # Control flags
        self.running = False
        self.portfolio_id = None
        
        logger.info(f"LiveTradingRunner initialized in {self.config.mode.value} mode")
    
    async def initialize_services(self):
        """Initialize all required services"""
        logger.info("Initializing services...")
        
        # Initialize repositories
        portfolio_repo = PostgresPortfolioRepository()
        order_repo = PostgresOrderRepository()
        position_repo = PostgresPositionRepository()
        
        # Initialize state recovery
        self.state_recovery_service = StateRecoveryService(
            state_dir="./trading_state",
            snapshot_interval_seconds=60,
            max_snapshots=100,
            retention_days=7
        )
        
        # Try to recover previous state
        recovered_state = await self.state_recovery_service.recover_state()
        
        # Initialize broker adapter
        broker_config = {
            'api_key': self.config.binance.api_key,
            'api_secret': self.config.binance.api_secret,
            'testnet': self.config.binance.testnet
        }
        
        self.broker_adapter = LiveBrokerAdapter(
            broker_type=BrokerType.BINANCE_FUTURES,
            config=broker_config
        )
        
        broker = self.broker_adapter.create_adapter(self.event_bus)
        
        # Initialize live trading service
        self.live_trading_service = LiveTradingService(
            portfolio_repository=portfolio_repo,
            order_repository=order_repo,
            position_repository=position_repo,
            event_bus=self.event_bus,
            config=self.config
        )
        
        # Initialize risk validator
        self.risk_validator = PreTradeRiskValidator(
            portfolio_repository=portfolio_repo,
            position_repository=position_repo,
            order_repository=order_repo,
            config=self.config
        )
        
        # Initialize signal adapter
        self.signal_adapter = SignalOrderAdapter(config=self.config)
        
        # Initialize strategy bridge
        self.strategy_bridge = StrategyBridge(
            event_bus=self.event_bus,
            broker=broker if isinstance(broker, BinanceFuturesBroker) else None
        )
        
        # Add strategies
        await self._setup_strategies()
        
        # Recover portfolio from previous session
        if recovered_state and recovered_state.portfolio_id:
            self.portfolio_id = recovered_state.portfolio_id
            logger.info(f"Recovered portfolio ID: {self.portfolio_id}")
        
        logger.info("All services initialized")
    
    async def _setup_strategies(self):
        """Set up trading strategies"""
        if not self.config.signal.auto_execute:
            logger.warning("Auto-execute disabled - strategies will not generate signals")
            return
        
        # Get strategy parameters
        grid_config = {
            'atr_period': int(os.getenv('GRID_ATR_PERIOD', '14')),
            'grid_levels': int(os.getenv('GRID_LEVELS', '5')),
            'atr_multiplier': float(os.getenv('GRID_ATR_MULTIPLIER', '1.0')),
            'take_profit_pct': float(os.getenv('GRID_TAKE_PROFIT_PCT', '0.02')),
            'stop_loss_pct': float(os.getenv('GRID_STOP_LOSS_PCT', '0.05'))
        }
        
        # Add strategies for configured symbols
        symbols = os.getenv('TRADING_SYMBOLS', 'BTCUSDT').split(',')
        
        for symbol in symbols:
            symbol = symbol.strip()
            strategy = OptimalGridStrategyLive(
                symbol=symbol,
                **grid_config
            )
            self.strategy_bridge.add_strategy(symbol, strategy)
            logger.info(f"Added OptimalGridStrategy for {symbol}")
    
    async def get_or_create_portfolio(self) -> UUID:
        """Get existing portfolio or create a new one"""
        if self.portfolio_id:
            return self.portfolio_id
        
        # Try to get the first portfolio
        portfolio_repo = PostgresPortfolioRepository()
        portfolios = await portfolio_repo.get_all()
        
        if portfolios:
            portfolio = portfolios[0]
            logger.info(f"Using existing portfolio: {portfolio.name} (ID: {portfolio.id})")
            return portfolio.id
        
        # Create a new portfolio
        from src.domain.trading.aggregates.portfolio import Portfolio
        
        initial_capital = Decimal(os.getenv('INITIAL_CAPITAL', '1000'))
        portfolio = Portfolio.create(
            name="Live Trading Portfolio",
            initial_capital=initial_capital,
            currency="USDT"
        )
        
        await portfolio_repo.save(portfolio)
        logger.info(f"Created new portfolio with {initial_capital} USDT")
        
        return portfolio.id
    
    async def start(self):
        """Start live trading"""
        if self.running:
            logger.warning("Trading already running")
            return
        
        try:
            # Validate configuration
            if not self.config.validate():
                raise ValueError("Invalid configuration")
            
            if not self.config.enabled:
                raise ValueError("Trading is disabled in configuration")
            
            # Initialize services
            await self.initialize_services()
            
            # Connect to broker
            await self.broker_adapter.connect()
            
            # Get or create portfolio
            self.portfolio_id = await self.get_or_create_portfolio()
            
            # Start trading session
            session = await self.live_trading_service.start_session(self.portfolio_id)
            logger.info(f"Trading session started: {session.id}")
            
            # Start strategy bridge
            await self.strategy_bridge.start()
            
            self.running = True
            logger.info("Live trading started successfully")
            
            # Start monitoring loop
            await self._monitor_loop()
            
        except Exception as e:
            logger.error(f"Failed to start live trading: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """Stop live trading"""
        logger.info("Stopping live trading...")
        
        self.running = False
        
        # Stop strategy bridge
        if self.strategy_bridge:
            await self.strategy_bridge.stop()
        
        # Save state before stopping
        if self.state_recovery_service and self.live_trading_service:
            if self.live_trading_service.current_session:
                await self.state_recovery_service.save_critical_state(
                    session=self.live_trading_service.current_session,
                    reason="Graceful shutdown",
                    additional_data={
                        "active_orders": len(self.live_trading_service.active_orders),
                        "active_positions": len(self.live_trading_service.active_positions)
                    }
                )
        
        # Stop trading session
        if self.live_trading_service:
            await self.live_trading_service.stop_session("User requested")
        
        # Disconnect from broker
        if self.broker_adapter:
            await self.broker_adapter.disconnect()
        
        logger.info("Live trading stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        save_interval = 60  # Save state every minute
        last_save = datetime.now()
        
        while self.running:
            try:
                # Save state periodically
                if (datetime.now() - last_save).total_seconds() >= save_interval:
                    await self._save_state()
                    last_save = datetime.now()
                
                # Log status
                if self.live_trading_service and self.live_trading_service.current_session:
                    session = self.live_trading_service.current_session
                    logger.info(f"Session status - Trades: {session.total_trades}, "
                              f"PnL: {session.total_pnl:.2f} USDT, "
                              f"Win rate: {session.get_win_rate():.1%}")
                
                # Check for manual intervention commands
                # This could be extended to read from a file or API
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(10)
    
    async def _save_state(self):
        """Save current state"""
        if not self.live_trading_service or not self.state_recovery_service:
            return
        
        try:
            await self.state_recovery_service.save_state(
                session=self.live_trading_service.current_session,
                active_orders=self.live_trading_service.active_orders,
                active_positions=self.live_trading_service.active_positions,
                monitored_symbols=self.live_trading_service.monitored_symbols,
                risk_metrics=self.risk_validator.get_risk_metrics(self.portfolio_id) if self.portfolio_id else None
            )
            
            logger.debug("State saved")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")


async def main():
    """Main entry point"""
    runner = LiveTradingRunner()
    
    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        asyncio.create_task(runner.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start trading
        await runner.start()
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await runner.stop()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await runner.stop()
        sys.exit(1)


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Check if API keys are configured
    config = get_config()
    
    if config.mode != TradingMode.PAPER:
        if not config.binance.api_key or config.binance.api_key == "YOUR_BINANCE_API_KEY_HERE":
            logger.error("Please configure your Binance API credentials in .env file")
            sys.exit(1)
    
    # Print startup information
    logger.info("=" * 60)
    logger.info("Live Trading System Starting")
    logger.info(f"Mode: {config.mode.value}")
    logger.info(f"Testnet: {config.binance.testnet}")
    logger.info(f"Auto-execute: {config.signal.auto_execute}")
    logger.info(f"Max leverage: {config.risk.max_leverage}x")
    logger.info(f"Max position size: {config.risk.max_position_size_usdt} USDT")
    logger.info(f"Daily loss limit: {config.risk.daily_loss_limit_usdt} USDT")
    logger.info("=" * 60)
    
    # Run the main function
    asyncio.run(main())