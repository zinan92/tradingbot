"""
Strategy Configuration Value Objects

Defines the core value objects for strategy configuration including
strategy ID, category, order types, and position sizing strategies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4


class StrategyCategory(Enum):
    """Categories of trading strategies"""
    MOMENTUM = "momentum"
    REVERSION = "reversion"
    GRID = "grid"
    SCALPING = "scalping"
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    TREND_FOLLOWING = "trend_following"
    BREAKOUT = "breakout"
    CUSTOM = "custom"


class OrderType(Enum):
    """Order execution types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_MARKET = "stop_market"
    STOP_LIMIT = "stop_limit"
    MIXED = "mixed"  # Strategy decides per trade


class PositionSizingType(Enum):
    """Position sizing strategies"""
    FIXED = "fixed"  # Fixed amount per trade
    PERCENTAGE = "percentage"  # Percentage of capital
    KELLY = "kelly"  # Kelly criterion
    ATR_BASED = "atr_based"  # Based on volatility
    RISK_PARITY = "risk_parity"  # Equal risk allocation
    MARTINGALE = "martingale"  # Double down on losses
    ANTI_MARTINGALE = "anti_martingale"  # Increase on wins


class TradingMode(Enum):
    """Trading mode for the strategy"""
    SPOT = "spot"
    FUTURES = "futures"
    MARGIN = "margin"
    OPTIONS = "options"


@dataclass(frozen=True)
class PositionSizing:
    """Position sizing configuration"""
    type: PositionSizingType
    value: float  # Base value (amount, percentage, multiplier)
    max_position_size: Optional[float] = None  # Maximum position limit
    min_position_size: Optional[float] = None  # Minimum position limit
    scale_with_confidence: bool = False  # Scale based on signal strength
    risk_per_trade: Optional[float] = None  # Max risk per trade (for Kelly, etc.)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'type': self.type.value,
            'value': self.value,
            'max_position_size': self.max_position_size,
            'min_position_size': self.min_position_size,
            'scale_with_confidence': self.scale_with_confidence,
            'risk_per_trade': self.risk_per_trade
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'PositionSizing':
        """Create from dictionary"""
        return PositionSizing(
            type=PositionSizingType(data['type']),
            value=data['value'],
            max_position_size=data.get('max_position_size'),
            min_position_size=data.get('min_position_size'),
            scale_with_confidence=data.get('scale_with_confidence', False),
            risk_per_trade=data.get('risk_per_trade')
        )


@dataclass(frozen=True)
class RiskManagement:
    """Risk management configuration"""
    stop_loss_enabled: bool = True
    stop_loss_percentage: Optional[float] = None  # As percentage of entry
    stop_loss_atr_multiplier: Optional[float] = None  # ATR-based stop
    
    take_profit_enabled: bool = True
    take_profit_percentage: Optional[float] = None  # As percentage of entry
    take_profit_atr_multiplier: Optional[float] = None  # ATR-based target
    take_profit_risk_reward: Optional[float] = None  # Risk/reward ratio
    
    trailing_stop_enabled: bool = False
    trailing_stop_percentage: Optional[float] = None
    trailing_stop_activation: Optional[float] = None  # Profit % to activate
    
    max_daily_loss: Optional[float] = None  # Maximum daily loss limit
    max_daily_trades: Optional[int] = None  # Maximum trades per day
    max_open_positions: Optional[int] = None  # Maximum concurrent positions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'stop_loss_enabled': self.stop_loss_enabled,
            'stop_loss_percentage': self.stop_loss_percentage,
            'stop_loss_atr_multiplier': self.stop_loss_atr_multiplier,
            'take_profit_enabled': self.take_profit_enabled,
            'take_profit_percentage': self.take_profit_percentage,
            'take_profit_atr_multiplier': self.take_profit_atr_multiplier,
            'take_profit_risk_reward': self.take_profit_risk_reward,
            'trailing_stop_enabled': self.trailing_stop_enabled,
            'trailing_stop_percentage': self.trailing_stop_percentage,
            'trailing_stop_activation': self.trailing_stop_activation,
            'max_daily_loss': self.max_daily_loss,
            'max_daily_trades': self.max_daily_trades,
            'max_open_positions': self.max_open_positions
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'RiskManagement':
        """Create from dictionary"""
        return RiskManagement(**data)


@dataclass(frozen=True)
class StrategyID:
    """
    Unique identifier for a strategy configuration.
    Contains all metadata needed to identify and configure a strategy.
    """
    id: str  # Unique identifier (e.g., "momentum_macd_001")
    name: str  # Human-readable name
    version: str  # Version number (e.g., "1.0.0")
    category: StrategyCategory
    
    def __str__(self) -> str:
        return f"{self.id}@{self.version}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'category': self.category.value
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'StrategyID':
        """Create from dictionary"""
        return StrategyID(
            id=data['id'],
            name=data['name'],
            version=data['version'],
            category=StrategyCategory(data['category'])
        )


@dataclass
class StrategyConfiguration:
    """
    Complete configuration for a trading strategy.
    This encapsulates all parameters needed to run a backtest or live trading.
    """
    strategy_id: StrategyID
    class_name: str  # Python class name for the strategy
    interval: str  # Timeframe (1m, 5m, 1h, 4h, 1d, etc.)
    
    # Trading parameters
    trading_mode: TradingMode = TradingMode.SPOT
    order_type: OrderType = OrderType.MARKET
    leverage: float = 1.0  # For futures/margin trading
    
    # Position and risk management
    position_sizing: PositionSizing = field(default_factory=lambda: PositionSizing(
        type=PositionSizingType.PERCENTAGE,
        value=0.1
    ))
    risk_management: RiskManagement = field(default_factory=RiskManagement)
    
    # Strategy-specific parameters
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Commission rates
    market_commission: float = 0.0004  # 0.04% for market orders
    limit_commission: float = 0.0002  # 0.02% for limit orders
    
    # Filters and conditions
    min_volume: Optional[float] = None  # Minimum volume filter
    allowed_sessions: Optional[List[str]] = None  # Trading sessions (Asia, Europe, US)
    enabled: bool = True  # Whether strategy is active
    
    # Metadata
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'strategy_id': self.strategy_id.to_dict(),
            'class_name': self.class_name,
            'interval': self.interval,
            'trading_mode': self.trading_mode.value,
            'order_type': self.order_type.value,
            'leverage': self.leverage,
            'position_sizing': self.position_sizing.to_dict(),
            'risk_management': self.risk_management.to_dict(),
            'params': self.params,
            'market_commission': self.market_commission,
            'limit_commission': self.limit_commission,
            'min_volume': self.min_volume,
            'allowed_sessions': self.allowed_sessions,
            'enabled': self.enabled,
            'description': self.description,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'tags': self.tags
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'StrategyConfiguration':
        """Create from dictionary"""
        return StrategyConfiguration(
            strategy_id=StrategyID.from_dict(data['strategy_id']),
            class_name=data['class_name'],
            interval=data['interval'],
            trading_mode=TradingMode(data.get('trading_mode', 'spot')),
            order_type=OrderType(data.get('order_type', 'market')),
            leverage=data.get('leverage', 1.0),
            position_sizing=PositionSizing.from_dict(data['position_sizing']),
            risk_management=RiskManagement.from_dict(data['risk_management']),
            params=data.get('params', {}),
            market_commission=data.get('market_commission', 0.0004),
            limit_commission=data.get('limit_commission', 0.0002),
            min_volume=data.get('min_volume'),
            allowed_sessions=data.get('allowed_sessions'),
            enabled=data.get('enabled', True),
            description=data.get('description'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            tags=data.get('tags', [])
        )
    
    def get_commission_rate(self) -> float:
        """Get appropriate commission rate based on order type"""
        if self.order_type == OrderType.LIMIT:
            return self.limit_commission
        elif self.order_type == OrderType.MARKET:
            return self.market_commission
        else:
            # For mixed or other types, use average
            return (self.market_commission + self.limit_commission) / 2
    
    def is_futures_strategy(self) -> bool:
        """Check if this is a futures trading strategy"""
        return self.trading_mode in [TradingMode.FUTURES, TradingMode.MARGIN]
    
    def validate(self) -> List[str]:
        """
        Validate the configuration
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate leverage
        if self.leverage < 1 or self.leverage > 125:
            errors.append(f"Invalid leverage: {self.leverage}. Must be between 1 and 125.")
        
        # Validate commission rates
        if self.market_commission < 0 or self.market_commission > 0.01:
            errors.append(f"Invalid market commission: {self.market_commission}")
        if self.limit_commission < 0 or self.limit_commission > 0.01:
            errors.append(f"Invalid limit commission: {self.limit_commission}")
        
        # Validate position sizing
        if self.position_sizing.value <= 0:
            errors.append("Position sizing value must be positive")
        
        # Validate risk management
        if self.risk_management.stop_loss_enabled:
            if not any([
                self.risk_management.stop_loss_percentage,
                self.risk_management.stop_loss_atr_multiplier
            ]):
                errors.append("Stop loss enabled but no stop loss value specified")
        
        if self.risk_management.take_profit_enabled:
            if not any([
                self.risk_management.take_profit_percentage,
                self.risk_management.take_profit_atr_multiplier,
                self.risk_management.take_profit_risk_reward
            ]):
                errors.append("Take profit enabled but no take profit value specified")
        
        return errors