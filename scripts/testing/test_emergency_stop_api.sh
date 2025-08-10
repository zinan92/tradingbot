#!/bin/bash
# Test Emergency Stop API Endpoint

echo "Emergency Stop API Test"
echo "======================="
echo ""
echo "This script demonstrates the emergency stop API endpoint."
echo "Note: Requires the API server to be running with proper dependency injection."
echo ""

# Base URL
BASE_URL="http://localhost:8000"

echo "1. Check session status"
echo "-----------------------"
curl -X GET "$BASE_URL/api/live/status" \
     -H "Content-Type: application/json" \
     2>/dev/null | python3 -m json.tool || echo "API not running or no session"

echo ""
echo "2. Trigger emergency stop"
echo "-------------------------"
echo "Request: POST /api/live/emergency-stop"
echo "Body: {\"reason\": \"System critical failure detected\", \"close_positions\": true}"
echo ""
curl -X POST "$BASE_URL/api/live/emergency-stop" \
     -H "Content-Type: application/json" \
     -d '{
       "reason": "System critical failure detected",
       "close_positions": true
     }' \
     2>/dev/null | python3 -m json.tool || echo "Emergency stop endpoint would return session locked status"

echo ""
echo "3. Attempt to place order (should fail)"
echo "---------------------------------------"
echo "Expected: 409 Conflict - Trading is locked"
echo ""
curl -X POST "$BASE_URL/api/orders" \
     -H "Content-Type: application/json" \
     -d '{
       "portfolio_id": "00000000-0000-0000-0000-000000000000",
       "symbol": "BTCUSDT",
       "side": "buy",
       "order_type": "limit",
       "quantity": "0.1",
       "price": "45000"
     }' \
     -w "\nHTTP Status: %{http_code}\n" \
     2>/dev/null || echo "Order would be rejected with 409 status"

echo ""
echo "4. Unlock session"
echo "-----------------"
curl -X POST "$BASE_URL/api/live/unlock" \
     -H "Content-Type: application/json" \
     2>/dev/null | python3 -m json.tool || echo "Session would be unlocked"

echo ""
echo "✅ Emergency Stop API test complete!"
echo ""
echo "Expected behavior when server is running:"
echo "• Emergency stop locks the session immediately"
echo "• All orders are cancelled"
echo "• Positions are closed if requested"
echo "• New orders return 409 Conflict"
echo "• Manual unlock required to resume trading"