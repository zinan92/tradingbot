#!/bin/bash

# Trading Bot Dashboard Launcher
# This script starts the Streamlit dashboard for monitoring your trading bot

echo "🚀 Starting Trading Bot Dashboard..."
echo "=================================="

# Navigate to project directory
cd "$(dirname "$0")"

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit is not installed!"
    echo "Installing dashboard requirements..."
    pip install -r dashboard/requirements.txt
fi

# Check PostgreSQL connection
echo "Checking database connection..."
if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "✅ Database is accessible"
else
    echo "⚠️  Warning: Database may not be accessible"
    echo "   Dashboard will work with limited functionality"
fi

# Launch dashboard
echo ""
echo "📊 Launching dashboard..."
echo "   URL: http://localhost:8501"
echo "   Press Ctrl+C to stop"
echo ""

# Start Streamlit
streamlit run dashboard/app.py \
    --server.port 8501 \
    --server.address localhost \
    --browser.gatherUsageStats false