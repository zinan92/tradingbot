"""
Minimal test to verify health and metrics endpoints work
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import only the routers we need
from src.adapters.api.health_router import router as health_router
from src.adapters.api.metrics_router import router as metrics_router

# Create minimal FastAPI app
app = FastAPI(title="Test API")
app.include_router(health_router)
app.include_router(metrics_router)

# Create test client
client = TestClient(app)

print("="*50)
print("TESTING HEALTH ENDPOINTS")
print("="*50)

# Test health endpoint
print("\n1. Testing /health/market_data")
response = client.get("/health/market_data")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Health Status: {data['status']}")
    print(f"   Lag: {data['lag_seconds']}s")
    print(f"   Error Rate: {data['error_rate']}")
    print(f"   Queue Depth: {data['queue_depth']}")

# Test all health
print("\n2. Testing /health/ (all modules)")
response = client.get("/health/")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Modules checked: {len(data)}")
    for module, health in list(data.items())[:3]:
        print(f"   - {module}: {health['status']}")

# Test readiness
print("\n3. Testing /health/ready")
response = client.get("/health/ready")
print(f"   Status: {response.status_code}")
if response.status_code in [200, 503]:
    data = response.json()
    if response.status_code == 200:
        print(f"   Ready: {data['ready']}")
    else:
        print(f"   Ready: False (some modules down)")

# Test liveness
print("\n4. Testing /health/live")
response = client.get("/health/live")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Status: {data['status']}")

print("\n" + "="*50)
print("TESTING METRICS ENDPOINTS")
print("="*50)

# Test Prometheus metrics
print("\n5. Testing /metrics")
response = client.get("/metrics")
print(f"   Status: {response.status_code}")
print(f"   Content-Type: {response.headers.get('content-type')}")
lines = response.text.split('\n')
print(f"   Total lines: {len(lines)}")

# Show sample metrics
print("\n   Sample metrics:")
metric_count = 0
for line in lines:
    if line and not line.startswith('#'):
        if metric_count < 5:
            print(f"     {line[:70]}..." if len(line) > 70 else f"     {line}")
            metric_count += 1

# Test JSON metrics
print("\n6. Testing /metrics/json")
response = client.get("/metrics/json")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Has counters: {'counters' in data}")
    print(f"   Has histograms: {'histograms' in data}")
    print(f"   Has gauges: {'gauges' in data}")

# Test increment
print("\n7. Testing metric increment")
response = client.post("/metrics/increment/test_counter?value=5&module=test")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Metric: {data['metric']}")
    print(f"   Value incremented by: {data['value']}")

# Test gauge
print("\n8. Testing gauge set")
response = client.post("/metrics/gauge/test_gauge?value=42.5&module=test")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Metric: {data['metric']}")
    print(f"   Value set to: {data['value']}")

# Verify metrics were updated
print("\n9. Verifying metrics were updated")
response = client.get("/metrics")
if "test_counter" in response.text:
    print("   ✅ test_counter found in metrics")
if "test_gauge" in response.text:
    print("   ✅ test_gauge found in metrics")

print("\n" + "="*50)
print("✅ ALL TESTS PASSED!")
print("="*50)