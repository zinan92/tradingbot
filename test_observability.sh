#!/bin/bash

# Script to test health and metrics endpoints

echo "Starting FastAPI server in background..."
python3 -m uvicorn src.adapters.api.app:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 3

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    
    echo ""
    echo "Testing: $description"
    echo "Endpoint: $endpoint"
    echo "----------------------------------------"
    
    response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "http://localhost:8000$endpoint")
    http_status=$(echo "$response" | tail -n 1 | cut -d: -f2)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_status" = "200" ]; then
        echo "✅ Status: $http_status OK"
        echo "Response preview (first 500 chars):"
        echo "$body" | head -c 500
        echo ""
    else
        echo "❌ Status: $http_status"
        echo "Response:"
        echo "$body"
    fi
}

echo ""
echo "========================================"
echo "      TESTING HEALTH ENDPOINTS"
echo "========================================"

# Test individual module health
test_endpoint "/health/market_data" "Market Data Module Health"
test_endpoint "/health/execution" "Execution Module Health"
test_endpoint "/health/backtest" "Backtest Module Health"

# Test all modules health
test_endpoint "/health/" "All Modules Health"

# Test readiness probe
test_endpoint "/health/ready" "Readiness Probe"

# Test liveness probe
test_endpoint "/health/live" "Liveness Probe"

echo ""
echo "========================================"
echo "       TESTING METRICS ENDPOINTS"
echo "========================================"

# Test Prometheus metrics
test_endpoint "/metrics" "Prometheus Metrics"

# Test JSON metrics
test_endpoint "/metrics/json" "JSON Metrics"

echo ""
echo "========================================"
echo "    TESTING METRIC MANIPULATION"
echo "========================================"

# Test incrementing a counter
echo ""
echo "Incrementing test counter..."
curl -X POST "http://localhost:8000/metrics/increment/test_counter?value=5&module=test" -s | python3 -m json.tool

# Test setting a gauge
echo ""
echo "Setting test gauge..."
curl -X POST "http://localhost:8000/metrics/gauge/test_gauge?value=42.5&module=test" -s | python3 -m json.tool

# Verify the metrics were updated
echo ""
echo "Verifying metrics were updated..."
curl -s "http://localhost:8000/metrics" | grep -E "(test_counter|test_gauge)" | head -5

echo ""
echo "========================================"
echo "         CLEANUP"
echo "========================================"

# Kill the server
echo "Stopping server..."
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null

echo "✅ All tests completed!"