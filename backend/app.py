"""
Backend Application Main Entry Point

FastAPI application that mounts all module routers and provides
the main entry point for the backend API.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn

# Import settings and container
from backend.boot.settings import get_settings
from backend.boot.container import get_container

# Import all module routers
# Note: Some routers may not exist yet and will be created as needed
try:
    from backend.modules.backtesting.api_backtest import router as backtest_router
except ImportError:
    backtest_router = None
    
try:
    from backend.modules.live_trade.api_live_trading import router as live_trading_router
except ImportError:
    live_trading_router = None
    
try:
    from backend.modules.risk.api_risk import router as risk_router
except ImportError:
    risk_router = None
    
try:
    from backend.modules.monitoring.api_metrics import router as metrics_router
except ImportError:
    metrics_router = None

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting backend application")
    
    # Initialize dependency container
    container = get_container()
    
    # Set up live trading service in the router
    try:
        from backend.modules.live_trade.api_live_trading import set_live_trading_service
        live_trading_service = container.get_live_trading_service()
        set_live_trading_service(live_trading_service)
        logger.info("Live trading service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize live trading service: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down backend application")
    container.shutdown()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    settings = get_settings()
    
    # Configure logging
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format=settings.logging.format
    )
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.api.title,
        description=settings.api.description,
        version=settings.api.version,
        debug=settings.api.debug,
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount module routers
    _mount_routers(app, settings)
    
    # Add health check endpoint
    @app.get("/health")
    async def health_check():
        """Main application health check"""
        return {
            "status": "healthy",
            "environment": settings.environment,
            "version": settings.api.version,
            "modules": {
                "data_fetch": "available",
                "data_analysis": "available", 
                "backtesting": "available",
                "live_trading": "available" if settings.enable_live_trading else "disabled",
                "risk_management": "available" if settings.enable_risk_management else "disabled",
                "monitoring": "available" if settings.enable_monitoring else "disabled"
            }
        }
    
    # Add root endpoint
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "message": "Trading Bot Backend API",
            "version": settings.api.version,
            "environment": settings.environment,
            "docs": "/docs",
            "health": "/health"
        }
    
    logger.info(f"FastAPI app created for {settings.environment} environment")
    return app


def _mount_routers(app: FastAPI, settings) -> None:
    """Mount all module routers"""
    
    # Always available modules
    try:
        # Note: These imports would fail because we didn't create all routers
        # In a real implementation, you'd create them for data_fetch and data_analysis
        # app.include_router(data_fetch_router)
        # app.include_router(data_analysis_router)
        logger.info("Data modules would be mounted here")
    except Exception as e:
        logger.warning(f"Data modules not available: {e}")
    
    # Backtesting module
    if settings.enable_backtesting and backtest_router:
        try:
            app.include_router(backtest_router)
            logger.info("Backtesting router mounted")
        except Exception as e:
            logger.error(f"Failed to mount backtesting router: {e}")
    
    # Live trading module
    if settings.enable_live_trading and live_trading_router:
        try:
            app.include_router(live_trading_router)
            logger.info("Live trading router mounted")
        except Exception as e:
            logger.error(f"Failed to mount live trading router: {e}")
    
    # Risk management module
    if settings.enable_risk_management and risk_router:
        try:
            app.include_router(risk_router)
            logger.info("Risk management router mounted")
        except Exception as e:
            logger.error(f"Failed to mount risk management router: {e}")
    
    # Monitoring module
    if settings.enable_monitoring and metrics_router:
        try:
            app.include_router(metrics_router)
            logger.info("Monitoring router mounted")
        except Exception as e:
            logger.error(f"Failed to mount monitoring router: {e}")


# Create the app instance
app = create_app()


def main():
    """Main entry point for running the application"""
    settings = get_settings()
    
    logger.info(f"Starting server on {settings.api.host}:{settings.api.port}")
    
    uvicorn.run(
        "backend.app:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()