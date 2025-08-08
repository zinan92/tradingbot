#!/bin/bash

# Live Trading Deployment Script
# This script helps deploy and manage the live trading system

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENV_FILE=".env"
LOG_DIR="logs"
STATE_DIR="trading_state"
PID_FILE="trading.pid"

# Functions
print_banner() {
    echo "=========================================="
    echo "    Live Trading System Deployment"
    echo "=========================================="
    echo ""
}

check_requirements() {
    echo -e "${YELLOW}Checking requirements...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Check PostgreSQL
    if ! command -v psql &> /dev/null; then
        echo -e "${YELLOW}Warning: PostgreSQL client not found${NC}"
        echo "Make sure PostgreSQL is running if USE_POSTGRES=true"
    fi
    
    # Check .env file
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}Error: .env file not found${NC}"
        echo "Please copy .env.example to .env and configure it"
        exit 1
    fi
    
    # Check API keys
    if grep -q "YOUR_BINANCE_API_KEY_HERE" "$ENV_FILE"; then
        echo -e "${RED}Error: Binance API keys not configured${NC}"
        echo "Please add your API keys to the .env file"
        exit 1
    fi
    
    echo -e "${GREEN}Requirements check passed${NC}"
}

setup_directories() {
    echo -e "${YELLOW}Setting up directories...${NC}"
    
    # Create necessary directories
    mkdir -p "$LOG_DIR"
    mkdir -p "$STATE_DIR"
    mkdir -p "data"
    
    echo -e "${GREEN}Directories created${NC}"
}

install_dependencies() {
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        echo -e "${YELLOW}No requirements.txt found, installing common packages...${NC}"
        pip install fastapi uvicorn pandas numpy python-dotenv \
                   asyncio aiohttp websockets sqlalchemy psycopg2-binary \
                   pydantic redis
    fi
    
    echo -e "${GREEN}Dependencies installed${NC}"
}

setup_database() {
    echo -e "${YELLOW}Setting up database...${NC}"
    
    # Get database configuration from .env
    DB_URL=$(grep DATABASE_URL "$ENV_FILE" | cut -d '=' -f2)
    
    if [ -z "$DB_URL" ]; then
        echo -e "${YELLOW}No database URL configured, skipping database setup${NC}"
        return
    fi
    
    # Extract database name
    DB_NAME=$(echo "$DB_URL" | sed 's/.*\///')
    
    # Create database if it doesn't exist
    echo "Creating database if not exists: $DB_NAME"
    
    # You might need to adjust this based on your PostgreSQL setup
    # psql -U postgres -c "CREATE DATABASE IF NOT EXISTS $DB_NAME;"
    
    echo -e "${GREEN}Database setup complete${NC}"
}

start_services() {
    echo -e "${YELLOW}Starting services...${NC}"
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Start Redis if configured
    if grep -q "REDIS_URL" "$ENV_FILE"; then
        if command -v redis-server &> /dev/null; then
            echo "Starting Redis..."
            redis-server --daemonize yes
        fi
    fi
    
    # Start FastAPI in background
    echo "Starting FastAPI server..."
    nohup python run_api.py > "$LOG_DIR/api.log" 2>&1 &
    echo $! > api.pid
    
    sleep 2
    
    # Start live trading
    echo "Starting live trading system..."
    nohup python run_live_trading.py > "$LOG_DIR/trading.log" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    # Check if services started
    if ps -p $(cat "$PID_FILE") > /dev/null; then
        echo -e "${GREEN}Live trading started with PID: $(cat $PID_FILE)${NC}"
    else
        echo -e "${RED}Failed to start live trading${NC}"
        exit 1
    fi
    
    if ps -p $(cat api.pid) > /dev/null; then
        echo -e "${GREEN}API server started with PID: $(cat api.pid)${NC}"
    else
        echo -e "${YELLOW}Warning: API server may not have started${NC}"
    fi
}

stop_services() {
    echo -e "${YELLOW}Stopping services...${NC}"
    
    # Stop live trading
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "Stopping live trading (PID: $PID)..."
            kill -TERM "$PID"
            sleep 2
            
            # Force kill if still running
            if ps -p "$PID" > /dev/null; then
                kill -9 "$PID"
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # Stop API server
    if [ -f "api.pid" ]; then
        PID=$(cat "api.pid")
        if ps -p "$PID" > /dev/null; then
            echo "Stopping API server (PID: $PID)..."
            kill -TERM "$PID"
        fi
        rm -f "api.pid"
    fi
    
    echo -e "${GREEN}Services stopped${NC}"
}

check_status() {
    echo -e "${YELLOW}Checking service status...${NC}"
    
    # Check live trading
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo -e "${GREEN}Live trading is running (PID: $PID)${NC}"
        else
            echo -e "${RED}Live trading is not running${NC}"
        fi
    else
        echo -e "${RED}Live trading is not running${NC}"
    fi
    
    # Check API server
    if [ -f "api.pid" ]; then
        PID=$(cat "api.pid")
        if ps -p "$PID" > /dev/null; then
            echo -e "${GREEN}API server is running (PID: $PID)${NC}"
            echo "API available at: http://localhost:8000"
            echo "API docs at: http://localhost:8000/docs"
        else
            echo -e "${RED}API server is not running${NC}"
        fi
    else
        echo -e "${RED}API server is not running${NC}"
    fi
    
    # Check recent logs
    if [ -f "$LOG_DIR/trading.log" ]; then
        echo ""
        echo "Recent trading logs:"
        tail -n 5 "$LOG_DIR/trading.log"
    fi
}

show_logs() {
    LOG_TYPE=${1:-trading}
    
    if [ "$LOG_TYPE" = "trading" ]; then
        if [ -f "$LOG_DIR/trading.log" ]; then
            tail -f "$LOG_DIR/trading.log"
        else
            echo -e "${RED}Trading log not found${NC}"
        fi
    elif [ "$LOG_TYPE" = "api" ]; then
        if [ -f "$LOG_DIR/api.log" ]; then
            tail -f "$LOG_DIR/api.log"
        else
            echo -e "${RED}API log not found${NC}"
        fi
    else
        echo "Usage: $0 logs [trading|api]"
    fi
}

# Main script
print_banner

case "$1" in
    start)
        check_requirements
        setup_directories
        install_dependencies
        setup_database
        start_services
        echo ""
        echo -e "${GREEN}Deployment complete!${NC}"
        echo ""
        echo "Monitor live trading:"
        echo "  - Logs: tail -f $LOG_DIR/trading.log"
        echo "  - API: http://localhost:8000/docs"
        echo "  - Status: $0 status"
        ;;
    
    stop)
        stop_services
        ;;
    
    restart)
        stop_services
        sleep 2
        check_requirements
        start_services
        ;;
    
    status)
        check_status
        ;;
    
    logs)
        show_logs "$2"
        ;;
    
    setup)
        check_requirements
        setup_directories
        install_dependencies
        setup_database
        echo -e "${GREEN}Setup complete! Run '$0 start' to begin trading${NC}"
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|setup}"
        echo ""
        echo "Commands:"
        echo "  start   - Start all services"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  status  - Check service status"
        echo "  logs    - Show logs (trading|api)"
        echo "  setup   - Install dependencies and setup environment"
        exit 1
        ;;
esac