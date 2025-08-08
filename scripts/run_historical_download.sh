#!/bin/bash

# Script to run the historical data download
# Usage: ./run_historical_download.sh

echo "=================================================="
echo "Binance Futures Historical Data Download"
echo "=================================================="

# Set environment variables (update these with your actual values)
export DATABASE_URL="postgresql://user:password@localhost/tradingbot"
# export BINANCE_API_KEY="your_api_key_here"  # Optional for public data
# export BINANCE_API_SECRET="your_api_secret_here"  # Optional for public data

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "Python version: $PYTHON_VERSION"

# Install requirements if needed
echo "Checking dependencies..."
pip3 install -q -r requirements.txt

# Create necessary directories
mkdir -p logs
mkdir -p data/backups

# Run the download script
echo ""
echo "Starting download..."
echo "This will download 3 years of data for the top 30 Binance Futures symbols."
echo "Estimated time: 6-10 hours"
echo "Estimated storage: 3-5 GB"
echo ""

# Run with different options based on arguments
if [ "$1" = "--test" ]; then
    echo "Running in test mode (1 symbol, 7 days)..."
    python3 -m src.infrastructure.market_data.download_historical_data \
        --symbols BTCUSDT \
        --years 0 \
        --intervals 5m 15m 1h \
        --config test_config.json \
        2>&1 | tee logs/download_test_$(date +%Y%m%d_%H%M%S).log
        
elif [ "$1" = "--resume" ]; then
    echo "Resuming previous download..."
    python3 -m src.infrastructure.market_data.download_historical_data \
        2>&1 | tee -a logs/download_$(date +%Y%m%d_%H%M%S).log
        
elif [ "$1" = "--custom" ]; then
    echo "Running with custom configuration..."
    shift  # Remove --custom from arguments
    python3 -m src.infrastructure.market_data.download_historical_data "$@" \
        2>&1 | tee logs/download_custom_$(date +%Y%m%d_%H%M%S).log
        
else
    echo "Running full download..."
    python3 -m src.infrastructure.market_data.download_historical_data \
        --non-interactive \
        2>&1 | tee logs/download_full_$(date +%Y%m%d_%H%M%S).log
fi

echo ""
echo "=================================================="
echo "Download script finished"
echo "Check logs directory for detailed output"
echo "==================================================">