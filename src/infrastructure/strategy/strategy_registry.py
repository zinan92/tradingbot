"""
Strategy Registry

Central registry for managing trading strategy configurations.
Supports loading from JSON/YAML files and dynamic strategy discovery.
"""

import json
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass

from src.domain.strategy.value_objects.strategy_configuration import (
    StrategyConfiguration,
    StrategyID,
    StrategyCategory,
    OrderType,
    TradingMode,
    PositionSizing,
    PositionSizingType,
    RiskManagement
)

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    Central registry for strategy configurations.
    
    Manages:
    - Strategy configuration storage
    - Dynamic strategy class loading
    - Configuration validation
    - Strategy discovery
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the strategy registry.
        
        Args:
            config_dir: Directory containing strategy configuration files
        """
        self.config_dir = config_dir or Path(__file__).parent / "configs"
        self._configurations: Dict[str, StrategyConfiguration] = {}
        self._strategy_classes: Dict[str, Type] = {}
        
        # Load built-in strategy classes
        self._load_strategy_classes()
        
        # Load configurations from files if directory exists
        if self.config_dir.exists():
            self._load_configurations()
        else:
            # Load default configurations
            self._load_default_configurations()
    
    def _load_strategy_classes(self):
        """Load available strategy classes"""
        # Import all strategy classes
        try:
            # Spot strategies
            from src.application.backtesting.strategies.sma_cross_strategy import (
                SmaCrossStrategy,
                EnhancedSmaCrossStrategy,
                AdaptiveSmaCrossStrategy
            )
            
            # Futures strategies
            from src.application.backtesting.strategies.futures_sma_cross_strategy import (
                FuturesSmaCrossStrategy,
                FuturesMeanReversionStrategy,
                FuturesMomentumStrategy
            )
            
            # Grid strategies
            from src.infrastructure.backtesting.strategies.atr_grid_strategy import (
                ATRGridStrategy,
                OptimizedATRGridStrategy
            )
            
            # Register classes
            self._strategy_classes.update({
                'SmaCrossStrategy': SmaCrossStrategy,
                'EnhancedSmaCrossStrategy': EnhancedSmaCrossStrategy,
                'AdaptiveSmaCrossStrategy': AdaptiveSmaCrossStrategy,
                'FuturesSmaCrossStrategy': FuturesSmaCrossStrategy,
                'FuturesMeanReversionStrategy': FuturesMeanReversionStrategy,
                'FuturesMomentumStrategy': FuturesMomentumStrategy,
                'ATRGridStrategy': ATRGridStrategy,
                'OptimizedATRGridStrategy': OptimizedATRGridStrategy
            })
            
            logger.info(f"Loaded {len(self._strategy_classes)} strategy classes")
            
        except ImportError as e:
            logger.warning(f"Failed to import some strategy classes: {e}")
    
    def _load_configurations(self):
        """Load strategy configurations from files"""
        # Load JSON files
        for json_file in self.config_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for config_data in data:
                            config = StrategyConfiguration.from_dict(config_data)
                            self.register(config)
                    else:
                        config = StrategyConfiguration.from_dict(data)
                        self.register(config)
                logger.info(f"Loaded configurations from {json_file}")
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")
        
        # Load YAML files
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, list):
                        for config_data in data:
                            config = StrategyConfiguration.from_dict(config_data)
                            self.register(config)
                    else:
                        config = StrategyConfiguration.from_dict(data)
                        self.register(config)
                logger.info(f"Loaded configurations from {yaml_file}")
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")
    
    def _load_default_configurations(self):
        """Load default strategy configurations"""
        # Default SMA Crossover Strategy
        self.register(StrategyConfiguration(
            strategy_id=StrategyID(
                id="sma_cross_basic",
                name="Basic SMA Crossover",
                version="1.0.0",
                category=StrategyCategory.TREND_FOLLOWING
            ),
            class_name="SmaCrossStrategy",
            interval="1h",
            trading_mode=TradingMode.SPOT,
            order_type=OrderType.MARKET,
            position_sizing=PositionSizing(
                type=PositionSizingType.PERCENTAGE,
                value=0.95
            ),
            risk_management=RiskManagement(
                stop_loss_enabled=True,
                stop_loss_percentage=0.02,
                take_profit_enabled=True,
                take_profit_percentage=0.05
            ),
            params={
                "n1": 10,
                "n2": 20
            },
            description="Basic SMA crossover strategy with 10/20 periods"
        ))
        
        # Futures Momentum Strategy
        self.register(StrategyConfiguration(
            strategy_id=StrategyID(
                id="momentum_macd_futures",
                name="MACD Momentum Futures",
                version="1.0.0",
                category=StrategyCategory.MOMENTUM
            ),
            class_name="FuturesMomentumStrategy",
            interval="4h",
            trading_mode=TradingMode.FUTURES,
            order_type=OrderType.MARKET,
            leverage=8.0,
            position_sizing=PositionSizing(
                type=PositionSizingType.PERCENTAGE,
                value=0.9
            ),
            risk_management=RiskManagement(
                stop_loss_enabled=True,
                stop_loss_percentage=0.025,
                take_profit_enabled=True,
                take_profit_percentage=0.06,
                trailing_stop_enabled=True,
                trailing_stop_percentage=0.03
            ),
            params={
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "rsi_period": 14,
                "trend_sma": 50
            },
            market_commission=0.0004,
            limit_commission=0.0002,
            description="MACD-based momentum strategy for futures with 8x leverage"
        ))
        
        # Mean Reversion Strategy
        self.register(StrategyConfiguration(
            strategy_id=StrategyID(
                id="mean_reversion_bb",
                name="Bollinger Bands Mean Reversion",
                version="1.0.0",
                category=StrategyCategory.REVERSION
            ),
            class_name="FuturesMeanReversionStrategy",
            interval="1h",
            trading_mode=TradingMode.FUTURES,
            order_type=OrderType.LIMIT,
            leverage=5.0,
            position_sizing=PositionSizing(
                type=PositionSizingType.PERCENTAGE,
                value=0.8
            ),
            risk_management=RiskManagement(
                stop_loss_enabled=True,
                stop_loss_percentage=0.03,
                take_profit_enabled=True,
                take_profit_percentage=0.04,
                trailing_stop_enabled=True,
                trailing_stop_percentage=0.025,
                trailing_stop_activation=0.02
            ),
            params={
                "bb_period": 20,
                "bb_std": 2,
                "rsi_period": 14,
                "rsi_oversold": 30,
                "rsi_overbought": 70
            },
            market_commission=0.0004,
            limit_commission=0.0002,
            description="Mean reversion strategy using Bollinger Bands and RSI"
        ))
        
        # Grid Trading Strategy
        self.register(StrategyConfiguration(
            strategy_id=StrategyID(
                id="grid_atr_dynamic",
                name="Dynamic ATR Grid",
                version="1.0.0",
                category=StrategyCategory.GRID
            ),
            class_name="ATRGridStrategy",
            interval="1h",
            trading_mode=TradingMode.SPOT,
            order_type=OrderType.LIMIT,
            position_sizing=PositionSizing(
                type=PositionSizingType.FIXED,
                value=0.1,
                max_position_size=0.5
            ),
            risk_management=RiskManagement(
                stop_loss_enabled=True,
                stop_loss_atr_multiplier=2.0,
                take_profit_enabled=False,  # Disable take profit for grid
                max_open_positions=10
            ),
            params={
                "atr_multiplier": 0.75,
                "grid_levels": 5,
                "atr_period": 14,
                "use_regime": True,
                "initial_regime": "range"
            },
            description="ATR-based dynamic grid strategy with regime detection"
        ))
        
        # Scalping Strategy
        self.register(StrategyConfiguration(
            strategy_id=StrategyID(
                id="scalping_ema_cross",
                name="EMA Scalping",
                version="1.0.0",
                category=StrategyCategory.SCALPING
            ),
            class_name="EnhancedSmaCrossStrategy",
            interval="5m",
            trading_mode=TradingMode.FUTURES,
            order_type=OrderType.MARKET,
            leverage=10.0,
            position_sizing=PositionSizing(
                type=PositionSizingType.PERCENTAGE,
                value=0.5,
                scale_with_confidence=True
            ),
            risk_management=RiskManagement(
                stop_loss_enabled=True,
                stop_loss_percentage=0.005,
                take_profit_enabled=True,
                take_profit_percentage=0.01,
                max_daily_trades=50,
                max_daily_loss=0.05
            ),
            params={
                "n1": 5,
                "n2": 13,
                "volume_threshold": 1.5,
                "atr_period": 14
            },
            description="High-frequency scalping strategy using EMA crossovers"
        ))
        
        logger.info(f"Loaded {len(self._configurations)} default configurations")
    
    def register(self, configuration: StrategyConfiguration) -> None:
        """
        Register a strategy configuration.
        
        Args:
            configuration: Strategy configuration to register
        
        Raises:
            ValueError: If configuration is invalid
        """
        # Validate configuration
        errors = configuration.validate()
        if errors:
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")
        
        # Check if strategy class exists
        if configuration.class_name not in self._strategy_classes:
            logger.warning(
                f"Strategy class {configuration.class_name} not found for {configuration.strategy_id.id}"
            )
        
        # Register configuration
        self._configurations[configuration.strategy_id.id] = configuration
        logger.debug(f"Registered strategy: {configuration.strategy_id}")
    
    def get(self, strategy_id: str) -> Optional[StrategyConfiguration]:
        """
        Get a strategy configuration by ID.
        
        Args:
            strategy_id: Strategy ID to retrieve
        
        Returns:
            Strategy configuration or None if not found
        """
        return self._configurations.get(strategy_id)
    
    def get_strategy_class(self, class_name: str) -> Optional[Type]:
        """
        Get a strategy class by name.
        
        Args:
            class_name: Name of the strategy class
        
        Returns:
            Strategy class or None if not found
        """
        return self._strategy_classes.get(class_name)
    
    def list_strategies(self, 
                       category: Optional[StrategyCategory] = None,
                       trading_mode: Optional[TradingMode] = None,
                       enabled_only: bool = True) -> List[StrategyConfiguration]:
        """
        List available strategies with optional filters.
        
        Args:
            category: Filter by strategy category
            trading_mode: Filter by trading mode
            enabled_only: Only return enabled strategies
        
        Returns:
            List of matching strategy configurations
        """
        strategies = list(self._configurations.values())
        
        # Apply filters
        if category:
            strategies = [s for s in strategies if s.strategy_id.category == category]
        
        if trading_mode:
            strategies = [s for s in strategies if s.trading_mode == trading_mode]
        
        if enabled_only:
            strategies = [s for s in strategies if s.enabled]
        
        return strategies
    
    def list_categories(self) -> List[StrategyCategory]:
        """
        List all available strategy categories.
        
        Returns:
            List of unique categories
        """
        categories = set()
        for config in self._configurations.values():
            categories.add(config.strategy_id.category)
        return sorted(list(categories), key=lambda x: x.value)
    
    def save_configuration(self, configuration: StrategyConfiguration, 
                          filename: Optional[str] = None) -> Path:
        """
        Save a strategy configuration to file.
        
        Args:
            configuration: Configuration to save
            filename: Optional filename (defaults to strategy_id.json)
        
        Returns:
            Path to saved file
        """
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
        
        filename = filename or f"{configuration.strategy_id.id}.json"
        filepath = self.config_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(configuration.to_dict(), f, indent=2)
        
        logger.info(f"Saved configuration to {filepath}")
        return filepath
    
    def export_all(self, output_dir: Path) -> None:
        """
        Export all configurations to a directory.
        
        Args:
            output_dir: Directory to export configurations to
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for strategy_id, config in self._configurations.items():
            filepath = output_dir / f"{strategy_id}.json"
            with open(filepath, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
        
        logger.info(f"Exported {len(self._configurations)} configurations to {output_dir}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        strategies = list(self._configurations.values())
        
        return {
            'total_strategies': len(strategies),
            'enabled_strategies': len([s for s in strategies if s.enabled]),
            'categories': {
                cat.value: len([s for s in strategies if s.strategy_id.category == cat])
                for cat in self.list_categories()
            },
            'trading_modes': {
                mode.value: len([s for s in strategies if s.trading_mode == mode])
                for mode in TradingMode
            },
            'strategy_classes': list(self._strategy_classes.keys())
        }


# Global registry instance
_registry: Optional[StrategyRegistry] = None


def get_registry() -> StrategyRegistry:
    """
    Get the global strategy registry instance.
    
    Returns:
        Global StrategyRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = StrategyRegistry()
    return _registry