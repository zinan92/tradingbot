#!/bin/bash
# Test Risk API Endpoints

echo "Testing Risk Management API Endpoints"
echo "======================================"

# Test risk summary endpoint
echo -e "\n1. Testing GET /api/risk/summary"
echo "--------------------------------"
curl -X GET "http://localhost:8000/api/risk/summary" \
     -H "Content-Type: application/json" \
     2>/dev/null | python3 -m json.tool

echo -e "\n2. Testing GET /api/risk/exposure"
echo "---------------------------------"
curl -X GET "http://localhost:8000/api/risk/exposure" \
     -H "Content-Type: application/json" \
     2>/dev/null | python3 -m json.tool

echo -e "\n3. Testing GET /api/risk/metrics"
echo "--------------------------------"
curl -X GET "http://localhost:8000/api/risk/metrics" \
     -H "Content-Type: application/json" \
     2>/dev/null | python3 -m json.tool

echo -e "\n✅ Risk API tests complete!"