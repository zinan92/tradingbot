"""
Trading Configuration Module

Centralized configuration for live trading with environment variable support.
"""
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TradingMode(Enum):
    """Trading environment mode"""
    TESTNET = "TESTNET"
    MAINNET = "MAINNET"
    PAPER = "PAPER"  # Local simulation


class OrderType(Enum):
    """Default order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"


@dataclass
class BinanceConfig:
    """Binance API configuration"""
    api_key: str
    api_secret: str
    testnet: bool = True
    
    @classmethod
    def from_env(cls, mode: TradingMode) -> "BinanceConfig":
        """Create config from environment variables"""
        if mode == TradingMode.TESTNET:
            return cls(
                api_key=os.getenv("BINANCE_TESTNET_API_KEY", ""),
                api_secret=os.getenv("BINANCE_TESTNET_API_SECRET", ""),
                testnet=True
            )
        elif mode == TradingMode.MAINNET:
            return cls(
                api_key=os.getenv("BINANCE_API_KEY", ""),
                api_secret=os.getenv("BINANCE_API_SECRET", ""),
                testnet=False
            )
        else:
            # Paper trading doesn't need real credentials
            return cls(
                api_key="paper_trading",
                api_secret="paper_trading",
                testnet=True
            )


@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_leverage: int
    max_position_size_usdt: Decimal
    max_positions: int
    daily_loss_limit_usdt: Decimal
    max_drawdown_percent: Decimal
    
    @classmethod
    def from_env(cls) -> "RiskConfig":
        """Create config from environment variables"""
        return cls(
            max_leverage=int(os.getenv("MAX_LEVERAGE", "10")),
            max_position_size_usdt=Decimal(os.getenv("MAX_POSITION_SIZE_USDT", "10000")),
            max_positions=int(os.getenv("MAX_POSITIONS", "5")),
            daily_loss_limit_usdt=Decimal(os.getenv("DAILY_LOSS_LIMIT_USDT", "500")),
            max_drawdown_percent=Decimal(os.getenv("MAX_DRAWDOWN_PERCENT", "10"))
        )


@dataclass
class PositionSizingConfig:
    """Position sizing configuration"""
    default_position_size_percent: Decimal
    use_kelly_criterion: bool
    kelly_fraction: Decimal
    
    @classmethod
    def from_env(cls) -> "PositionSizingConfig":
        """Create config from environment variables"""
        return cls(
            default_position_size_percent=Decimal(os.getenv("DEFAULT_POSITION_SIZE_PERCENT", "2")),
            use_kelly_criterion=os.getenv("USE_KELLY_CRITERION", "false").lower() == "true",
            kelly_fraction=Decimal(os.getenv("KELLY_FRACTION", "0.25"))
        )


@dataclass
class OrderConfig:
    """Order execution configuration"""
    default_order_type: OrderType
    limit_order_offset_percent: Decimal
    stop_loss_percent: Decimal
    take_profit_percent: Decimal
    
    @classmethod
    def from_env(cls) -> "OrderConfig":
        """Create config from environment variables"""
        return cls(
            default_order_type=OrderType[os.getenv("DEFAULT_ORDER_TYPE", "MARKET")],
            limit_order_offset_percent=Decimal(os.getenv("LIMIT_ORDER_OFFSET_PERCENT", "0.1")),
            stop_loss_percent=Decimal(os.getenv("STOP_LOSS_PERCENT", "2.0")),
            take_profit_percent=Decimal(os.getenv("TAKE_PROFIT_PERCENT", "5.0"))
        )


@dataclass
class WebSocketConfig:
    """WebSocket configuration"""
    reconnect_delay: int
    max_reconnect_delay: int
    heartbeat_interval: int
    
    @classmethod
    def from_env(cls) -> "WebSocketConfig":
        """Create config from environment variables"""
        return cls(
            reconnect_delay=int(os.getenv("WS_RECONNECT_DELAY", "5")),
            max_reconnect_delay=int(os.getenv("WS_MAX_RECONNECT_DELAY", "60")),
            heartbeat_interval=int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
        )


@dataclass
class SignalConfig:
    """Signal processing configuration"""
    auto_execute: bool
    confidence_threshold: Decimal
    strength_threshold: Decimal
    
    # Signal type to order mapping
    signal_mappings: Dict[str, Dict[str, Any]] = None
    
    @classmethod
    def from_env(cls) -> "SignalConfig":
        """Create config from environment variables"""
        return cls(
            auto_execute=os.getenv("AUTO_EXECUTE_SIGNALS", "false").lower() == "true",
            confidence_threshold=Decimal(os.getenv("SIGNAL_CONFIDENCE_THRESHOLD", "0.7")),
            strength_threshold=Decimal(os.getenv("SIGNAL_STRENGTH_THRESHOLD", "0.5")),
            signal_mappings=cls._default_signal_mappings()
        )
    
    @staticmethod
    def _default_signal_mappings() -> Dict[str, Dict[str, Any]]:
        """Default signal to order mappings"""
        return {
            "STRONG_BUY": {
                "order_type": "MARKET",
                "size_multiplier": 1.0,
                "position_side": "LONG"
            },
            "BUY": {
                "order_type": "LIMIT",
                "size_multiplier": 0.7,
                "position_side": "LONG"
            },
            "WEAK_BUY": {
                "order_type": "LIMIT",
                "size_multiplier": 0.3,
                "position_side": "LONG"
            },
            "STRONG_SELL": {
                "order_type": "MARKET",
                "size_multiplier": 1.0,
                "position_side": "SHORT"
            },
            "SELL": {
                "order_type": "LIMIT",
                "size_multiplier": 0.7,
                "position_side": "SHORT"
            },
            "WEAK_SELL": {
                "order_type": "LIMIT",
                "size_multiplier": 0.3,
                "position_side": "SHORT"
            },
            "CLOSE_LONG": {
                "order_type": "MARKET",
                "reduce_only": True,
                "position_side": "LONG"
            },
            "CLOSE_SHORT": {
                "order_type": "MARKET",
                "reduce_only": True,
                "position_side": "SHORT"
            },
            "HOLD": {
                "action": "none"
            }
        }


@dataclass
class TradingConfig:
    """Main trading configuration"""
    mode: TradingMode
    enabled: bool
    binance: BinanceConfig
    risk: RiskConfig
    position_sizing: PositionSizingConfig
    order: OrderConfig
    websocket: WebSocketConfig
    signal: SignalConfig
    
    @classmethod
    def from_env(cls) -> "TradingConfig":
        """Create complete config from environment variables"""
        mode = TradingMode[os.getenv("TRADING_MODE", "TESTNET")]
        
        return cls(
            mode=mode,
            enabled=os.getenv("TRADING_ENABLED", "false").lower() == "true",
            binance=BinanceConfig.from_env(mode),
            risk=RiskConfig.from_env(),
            position_sizing=PositionSizingConfig.from_env(),
            order=OrderConfig.from_env(),
            websocket=WebSocketConfig.from_env(),
            signal=SignalConfig.from_env()
        )
    
    def validate(self) -> bool:
        """Validate configuration"""
        errors = []
        
        # Check API credentials
        if self.mode != TradingMode.PAPER:
            if not self.binance.api_key or not self.binance.api_secret:
                errors.append("Binance API credentials not configured")
        
        # Check risk limits
        if self.risk.max_leverage > 125:
            errors.append("Max leverage exceeds Binance limit (125x)")
        
        if self.risk.max_position_size_usdt <= 0:
            errors.append("Max position size must be positive")
        
        if self.risk.daily_loss_limit_usdt <= 0:
            errors.append("Daily loss limit must be positive")
        
        # Check position sizing
        if self.position_sizing.default_position_size_percent <= 0:
            errors.append("Default position size must be positive")
        
        if self.position_sizing.default_position_size_percent > 100:
            errors.append("Position size cannot exceed 100% of portfolio")
        
        if errors:
            for error in errors:
                print(f"Config Error: {error}")
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "mode": self.mode.value,
            "enabled": self.enabled,
            "risk": {
                "max_leverage": self.risk.max_leverage,
                "max_position_size_usdt": str(self.risk.max_position_size_usdt),
                "max_positions": self.risk.max_positions,
                "daily_loss_limit_usdt": str(self.risk.daily_loss_limit_usdt),
                "max_drawdown_percent": str(self.risk.max_drawdown_percent)
            },
            "position_sizing": {
                "default_size_percent": str(self.position_sizing.default_position_size_percent),
                "use_kelly": self.position_sizing.use_kelly_criterion,
                "kelly_fraction": str(self.position_sizing.kelly_fraction)
            },
            "order": {
                "default_type": self.order.default_order_type.value,
                "stop_loss_percent": str(self.order.stop_loss_percent),
                "take_profit_percent": str(self.order.take_profit_percent)
            },
            "signal": {
                "auto_execute": self.signal.auto_execute,
                "confidence_threshold": str(self.signal.confidence_threshold),
                "strength_threshold": str(self.signal.strength_threshold)
            }
        }


# Global config instance
_config: Optional[TradingConfig] = None


def get_config() -> TradingConfig:
    """Get or create trading configuration"""
    global _config
    if _config is None:
        _config = TradingConfig.from_env()
        if not _config.validate():
            raise ValueError("Invalid trading configuration")
    return _config


def reload_config() -> TradingConfig:
    """Reload configuration from environment"""
    global _config
    _config = TradingConfig.from_env()
    if not _config.validate():
        raise ValueError("Invalid trading configuration")
    return _config