"""
Dependency Injection Container

Manages dependencies and provides dependency injection for the backend modules.
Follows hexagonal architecture principles with clean separation of concerns.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Import core modules
from backend.modules.data_fetch.core_fetch_planner import FetchPlanner
from backend.modules.data_analysis.service_indicator_calc import IndicatorService
from backend.modules.backtesting.core_backtest_engine import UnifiedBacktestEngine
from backend.modules.backtesting.port_results_store import InMemoryResultsStore, ResultsFormatter
from backend.modules.live_trade.core_live_trading import LiveTradingEngine
from backend.modules.live_trade.service_live_trading import LiveTradingService
from backend.modules.risk.core_risk_engine import RiskEngine

logger = logging.getLogger(__name__)


@dataclass
class ContainerConfig:
    """Configuration for the dependency injection container"""
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    database_url: Optional[str] = None
    redis_url: Optional[str] = None
    broker_config: Dict[str, Any] = None


class MockBrokerPort:
    """Mock broker port implementation for development"""
    
    async def place_order(self, order) -> str:
        """Mock order placement"""
        return f"mock_order_{order.order_id}"
    
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Mock order cancellation"""
        return True
    
    async def get_order_status(self, broker_order_id: str):
        """Mock order status"""
        return "FILLED"
    
    async def get_account_balance(self):
        """Mock account balance"""
        return 10000.0
    
    async def get_position(self, symbol: str):
        """Mock position"""
        return None


class MockPortfolioPort:
    """Mock portfolio port implementation for development"""
    
    def __init__(self):
        self.portfolios = {}
    
    async def get_portfolio(self, portfolio_id: str):
        """Mock get portfolio"""
        return self.portfolios.get(portfolio_id)
    
    async def update_portfolio(self, portfolio):
        """Mock update portfolio"""
        self.portfolios[portfolio.portfolio_id] = portfolio
    
    async def add_order(self, portfolio_id: str, order):
        """Mock add order"""
        if portfolio_id in self.portfolios:
            self.portfolios[portfolio_id].orders[order.order_id] = order
    
    async def update_order(self, order):
        """Mock update order"""
        pass


class MockRiskPort:
    """Mock risk port implementation for development"""
    
    async def validate_signal(self, signal, portfolio) -> bool:
        """Mock signal validation"""
        return True
    
    async def calculate_position_size(self, signal, portfolio):
        """Mock position size calculation"""
        return signal.quantity


class MockEventPort:
    """Mock event port implementation for development"""
    
    async def publish_event(self, event_type: str, event_data: Dict):
        """Mock event publishing"""
        logger.info(f"Mock event: {event_type} - {event_data}")


class DependencyContainer:
    """
    Dependency injection container that manages all application dependencies.
    """
    
    def __init__(self, config: ContainerConfig):
        self.config = config
        self._instances: Dict[str, Any] = {}
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize all dependencies"""
        if self._initialized:
            return
        
        logger.info(f"Initializing container for {self.config.environment}")
        
        # Configure logging
        log_level = getattr(logging, self.config.log_level.upper())
        logging.basicConfig(level=log_level)
        
        # Initialize core components
        self._initialize_data_components()
        self._initialize_backtesting_components()
        self._initialize_live_trading_components()
        self._initialize_risk_components()
        
        self._initialized = True
        logger.info("Container initialization complete")
    
    def _initialize_data_components(self):
        """Initialize data-related components"""
        # Fetch planner
        self._instances['fetch_planner'] = FetchPlanner()
        
        # Indicator service
        self._instances['indicator_service'] = IndicatorService()
        
        logger.debug("Data components initialized")
    
    def _initialize_backtesting_components(self):
        """Initialize backtesting components"""
        # Results store
        results_store = InMemoryResultsStore()
        self._instances['results_store'] = results_store
        
        # Results formatter
        self._instances['results_formatter'] = ResultsFormatter()
        
        # Backtest engine
        self._instances['backtest_engine'] = UnifiedBacktestEngine()
        
        logger.debug("Backtesting components initialized")
    
    def _initialize_live_trading_components(self):
        """Initialize live trading components"""
        # Mock ports for development
        broker_port = MockBrokerPort()
        portfolio_port = MockPortfolioPort()
        risk_port = MockRiskPort()
        event_port = MockEventPort()
        
        self._instances['broker_port'] = broker_port
        self._instances['portfolio_port'] = portfolio_port
        self._instances['event_port'] = event_port
        
        # Live trading engine
        live_trading_engine = LiveTradingEngine(
            broker_port=broker_port,
            portfolio_port=portfolio_port,
            risk_port=risk_port,
            event_port=event_port
        )
        self._instances['live_trading_engine'] = live_trading_engine
        
        # Live trading service
        self._instances['live_trading_service'] = LiveTradingService(live_trading_engine)
        
        logger.debug("Live trading components initialized")
    
    def _initialize_risk_components(self):
        """Initialize risk management components"""
        # Risk engine
        self._instances['risk_engine'] = RiskEngine()
        
        logger.debug("Risk components initialized")
    
    def get(self, component_name: str) -> Any:
        """Get a component by name"""
        if not self._initialized:
            self.initialize()
        
        if component_name not in self._instances:
            raise ValueError(f"Component '{component_name}' not found in container")
        
        return self._instances[component_name]
    
    def get_fetch_planner(self) -> FetchPlanner:
        """Get fetch planner instance"""
        return self.get('fetch_planner')
    
    def get_indicator_service(self) -> IndicatorService:
        """Get indicator service instance"""
        return self.get('indicator_service')
    
    def get_backtest_engine(self) -> UnifiedBacktestEngine:
        """Get backtest engine instance"""
        return self.get('backtest_engine')
    
    def get_results_store(self) -> InMemoryResultsStore:
        """Get results store instance"""
        return self.get('results_store')
    
    def get_live_trading_service(self) -> LiveTradingService:
        """Get live trading service instance"""
        return self.get('live_trading_service')
    
    def get_risk_engine(self) -> RiskEngine:
        """Get risk engine instance"""
        return self.get('risk_engine')
    
    def shutdown(self) -> None:
        """Shutdown the container and cleanup resources"""
        logger.info("Shutting down container")
        
        # Cleanup live trading service
        if 'live_trading_service' in self._instances:
            import asyncio
            try:
                asyncio.create_task(self._instances['live_trading_service'].cleanup())
            except Exception as e:
                logger.error(f"Error during live trading service cleanup: {e}")
        
        self._instances.clear()
        self._initialized = False
        logger.info("Container shutdown complete")


# Global container instance
_container: Optional[DependencyContainer] = None


def get_container() -> DependencyContainer:
    """Get the global container instance"""
    global _container
    
    if _container is None:
        from backend.boot.settings import get_settings
        settings = get_settings()
        
        config = ContainerConfig(
            environment=settings.environment,
            debug=settings.debug,
            log_level=settings.log_level,
            database_url=settings.database_url,
            redis_url=settings.redis_url
        )
        
        _container = DependencyContainer(config)
        _container.initialize()
    
    return _container


def set_container(container: DependencyContainer) -> None:
    """Set the global container instance (for testing)"""
    global _container
    _container = container