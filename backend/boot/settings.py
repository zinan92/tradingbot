"""
Application Settings

Centralized configuration management for the backend application.
Loads settings from environment variables with sensible defaults.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DatabaseSettings:
    """Database configuration settings"""
    url: Optional[str] = None
    host: str = "localhost"
    port: int = 5432
    name: str = "tradingbot"
    user: str = "postgres"
    password: str = "postgres"
    
    @property
    def connection_url(self) -> str:
        """Generate database connection URL"""
        if self.url:
            return self.url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class RedisSettings:
    """Redis configuration settings"""
    url: Optional[str] = None
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    
    @property
    def connection_url(self) -> str:
        """Generate Redis connection URL"""
        if self.url:
            return self.url
        
        auth_part = f":{self.password}@" if self.password else ""
        return f"redis://{auth_part}{self.host}:{self.port}/{self.db}"


@dataclass
class BrokerSettings:
    """Broker configuration settings"""
    # Binance settings
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    binance_testnet: bool = True
    
    # Paper trading settings
    paper_trading: bool = True
    initial_balance: float = 10000.0


@dataclass
class SecuritySettings:
    """Security configuration settings"""
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: list = field(default_factory=lambda: ["*"])


@dataclass
class LoggingSettings:
    """Logging configuration settings"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class APISettings:
    """API configuration settings"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    reload: bool = False
    title: str = "Trading Bot API"
    description: str = "Backend API for the trading bot system"
    version: str = "1.0.0"


@dataclass
class AppSettings:
    """Main application settings"""
    # Environment
    environment: str = "development"
    debug: bool = False
    
    # Component settings
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)
    broker: BrokerSettings = field(default_factory=BrokerSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    api: APISettings = field(default_factory=APISettings)
    
    # Data paths
    data_dir: Path = field(default_factory=lambda: Path("data"))
    logs_dir: Path = field(default_factory=lambda: Path("logs"))
    config_dir: Path = field(default_factory=lambda: Path("config"))
    
    # Feature flags
    enable_live_trading: bool = False
    enable_backtesting: bool = True
    enable_risk_management: bool = True
    enable_monitoring: bool = True
    
    # Convenience properties
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() in ("development", "dev")
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing"""
        return self.environment.lower() in ("testing", "test")
    
    @property
    def database_url(self) -> str:
        """Get database connection URL"""
        return self.database.connection_url
    
    @property
    def redis_url(self) -> str:
        """Get Redis connection URL"""
        return self.redis.connection_url
    
    @property
    def log_level(self) -> str:
        """Get logging level"""
        return self.logging.level


def load_settings_from_env() -> AppSettings:
    """Load settings from environment variables"""
    
    # Environment
    environment = os.getenv("ENVIRONMENT", "development")
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    # Database settings
    database = DatabaseSettings(
        url=os.getenv("DATABASE_URL"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        name=os.getenv("DB_NAME", "tradingbot"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres")
    )
    
    # Redis settings
    redis = RedisSettings(
        url=os.getenv("REDIS_URL"),
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD")
    )
    
    # Broker settings
    broker = BrokerSettings(
        binance_api_key=os.getenv("BINANCE_API_KEY"),
        binance_api_secret=os.getenv("BINANCE_API_SECRET"),
        binance_testnet=os.getenv("BINANCE_TESTNET", "true").lower() == "true",
        paper_trading=os.getenv("PAPER_TRADING", "true").lower() == "true",
        initial_balance=float(os.getenv("INITIAL_BALANCE", "10000.0"))
    )
    
    # Security settings
    security = SecuritySettings(
        secret_key=os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        cors_origins=os.getenv("CORS_ORIGINS", "*").split(",")
    )
    
    # Logging settings
    logging_settings = LoggingSettings(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format=os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        file_path=os.getenv("LOG_FILE"),
        max_bytes=int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024))),
        backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5"))
    )
    
    # API settings
    api = APISettings(
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        debug=os.getenv("API_DEBUG", "false").lower() == "true",
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
        title=os.getenv("API_TITLE", "Trading Bot API"),
        description=os.getenv("API_DESCRIPTION", "Backend API for the trading bot system"),
        version=os.getenv("API_VERSION", "1.0.0")
    )
    
    # Data paths
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    logs_dir = Path(os.getenv("LOGS_DIR", "logs"))
    config_dir = Path(os.getenv("CONFIG_DIR", "config"))
    
    # Feature flags
    enable_live_trading = os.getenv("ENABLE_LIVE_TRADING", "false").lower() == "true"
    enable_backtesting = os.getenv("ENABLE_BACKTESTING", "true").lower() == "true"
    enable_risk_management = os.getenv("ENABLE_RISK_MANAGEMENT", "true").lower() == "true"
    enable_monitoring = os.getenv("ENABLE_MONITORING", "true").lower() == "true"
    
    return AppSettings(
        environment=environment,
        debug=debug,
        database=database,
        redis=redis,
        broker=broker,
        security=security,
        logging=logging_settings,
        api=api,
        data_dir=data_dir,
        logs_dir=logs_dir,
        config_dir=config_dir,
        enable_live_trading=enable_live_trading,
        enable_backtesting=enable_backtesting,
        enable_risk_management=enable_risk_management,
        enable_monitoring=enable_monitoring
    )


# Global settings instance
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Get the global settings instance"""
    global _settings
    
    if _settings is None:
        _settings = load_settings_from_env()
    
    return _settings


def set_settings(settings: AppSettings) -> None:
    """Set the global settings instance (for testing)"""
    global _settings
    _settings = settings


def reload_settings() -> AppSettings:
    """Reload settings from environment"""
    global _settings
    _settings = None
    return get_settings()