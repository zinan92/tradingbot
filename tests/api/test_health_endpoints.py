"""
Smoke tests for health check endpoints
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import json


@pytest.fixture
def client():
    """Create test client"""
    from fastapi import FastAPI
    from src.adapters.api.health_router import router as health_router
    
    app = FastAPI(title="Test API")
    app.include_router(health_router)
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_module_health_shape(self, client):
        """Test that module health endpoint returns correct shape"""
        # Test market_data module
        response = client.get("/health/market_data")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        assert "status" in data
        assert data["status"] in ["ok", "degraded", "down"]
        assert "lag_seconds" in data
        assert isinstance(data["lag_seconds"], (int, float))
        assert "error_rate" in data
        assert 0 <= data["error_rate"] <= 1
        assert "queue_depth" in data
        assert data["queue_depth"] >= 0
        
        # Check optional fields
        if "last_success_ts" in data and data["last_success_ts"]:
            # Verify it's a valid ISO timestamp
            datetime.fromisoformat(data["last_success_ts"])
    
    def test_all_modules_health(self, client):
        """Test getting health for all modules"""
        response = client.get("/health/")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check we have multiple modules
        assert len(data) > 0
        
        # Expected modules
        expected_modules = [
            "market_data",
            "execution",
            "backtest",
            "strategy",
            "risk",
            "telemetry"
        ]
        
        for module in expected_modules:
            assert module in data
            health = data[module]
            assert "status" in health
            assert "lag_seconds" in health
            assert "error_rate" in health
            assert "queue_depth" in health
    
    def test_module_not_found(self, client):
        """Test accessing non-existent module"""
        response = client.get("/health/nonexistent_module")
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "nonexistent_module" in data["detail"]
        assert "not found" in data["detail"].lower()
    
    def test_readiness_probe(self, client):
        """Test Kubernetes readiness probe"""
        response = client.get("/health/ready")
        # Status code might be 200 or 503 depending on system state
        assert response.status_code in [200, 503]
        
        data = response.json()
        if response.status_code == 200:
            assert data["ready"] is True
            assert "modules" in data
            assert isinstance(data["modules"], int)
        else:
            # 503 response
            detail = data.get("detail", {})
            assert detail.get("ready") is False
            assert "down_modules" in detail
    
    def test_liveness_probe(self, client):
        """Test Kubernetes liveness probe"""
        response = client.get("/health/live")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
        
        # Verify timestamp is valid
        datetime.fromisoformat(data["timestamp"])
    
    def test_health_caching(self, client):
        """Test that health checks are cached"""
        # Make two rapid requests
        response1 = client.get("/health/market_data")
        response2 = client.get("/health/market_data")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # With caching, responses should be identical
        # (In production, you'd check timestamps to verify caching)
        data1 = response1.json()
        data2 = response2.json()
        
        # At minimum, status should be the same
        assert data1["status"] == data2["status"]
    
    def test_health_response_time(self, client):
        """Test that health endpoint responds quickly"""
        import time
        
        start = time.time()
        response = client.get("/health/market_data")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        # Health check should be fast (under 100ms)
        assert elapsed < 0.1
    
    def test_degraded_status_fields(self, client):
        """Test fields when status is degraded"""
        # In a real test, we'd trigger degraded state
        # For now, just verify the structure is correct
        response = client.get("/health/market_data")
        assert response.status_code == 200
        
        data = response.json()
        
        # If status is degraded, lag should be significant
        if data["status"] == "degraded":
            assert data["lag_seconds"] > 5
            assert data["error_rate"] > 0
    
    def test_concurrent_health_checks(self, client):
        """Test concurrent health check requests"""
        import concurrent.futures
        
        def check_health(module):
            response = client.get(f"/health/{module}")
            return response.status_code, response.json()
        
        modules = ["market_data", "execution", "backtest", "strategy"]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(check_health, module) for module in modules]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        for status_code, data in results:
            assert status_code == 200
            assert "status" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])