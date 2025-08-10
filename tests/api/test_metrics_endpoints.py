"""
Smoke tests for metrics endpoints
"""
import pytest
from fastapi.testclient import TestClient
import re


@pytest.fixture
def client():
    """Create test client"""
    from fastapi import FastAPI
    from src.adapters.api.metrics_router import router as metrics_router
    
    app = FastAPI(title="Test API")
    app.include_router(metrics_router)
    return TestClient(app)


class TestMetricsEndpoints:
    """Test metrics endpoints"""
    
    def test_metrics_endpoint_returns_200(self, client):
        """Test that metrics endpoint returns 200"""
        response = client.get("/metrics")
        assert response.status_code == 200
    
    def test_metrics_content_type(self, client):
        """Test that metrics are returned in Prometheus format"""
        response = client.get("/metrics")
        assert response.status_code == 200
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type
    
    def test_metrics_not_empty(self, client):
        """Test that metrics response is not empty"""
        response = client.get("/metrics")
        assert response.status_code == 200
        
        content = response.text
        assert len(content) > 0
        assert content.strip() != ""
    
    def test_prometheus_format(self, client):
        """Test that metrics follow Prometheus format"""
        response = client.get("/metrics")
        assert response.status_code == 200
        
        content = response.text
        lines = content.split("\n")
        
        # Check for HELP and TYPE lines
        help_lines = [l for l in lines if l.startswith("# HELP")]
        type_lines = [l for l in lines if l.startswith("# TYPE")]
        
        assert len(help_lines) > 0, "Should have HELP lines"
        assert len(type_lines) > 0, "Should have TYPE lines"
        
        # Check for metric lines (not comments)
        metric_lines = [l for l in lines if l and not l.startswith("#")]
        assert len(metric_lines) > 0, "Should have actual metrics"
    
    def test_required_metrics_present(self, client):
        """Test that all required metrics are present"""
        response = client.get("/metrics")
        assert response.status_code == 200
        
        content = response.text
        
        # Check for required metric types
        required_metrics = [
            "request_count",
            "request_latency_seconds",
            "error_count",
            "queue_depth",
            "data_freshness_seconds"
        ]
        
        for metric in required_metrics:
            assert metric in content, f"Metric {metric} should be present"
    
    def test_counter_metrics(self, client):
        """Test counter metrics format"""
        response = client.get("/metrics")
        content = response.text
        
        # Find request_count lines
        request_count_lines = [
            l for l in content.split("\n") 
            if l.startswith("request_count{")
        ]
        
        assert len(request_count_lines) > 0, "Should have request_count metrics"
        
        # Verify format: metric_name{labels} value
        for line in request_count_lines:
            match = re.match(r'request_count\{([^}]+)\}\s+(\d+)', line)
            assert match is not None, f"Invalid format: {line}"
            
            labels = match.group(1)
            value = int(match.group(2))
            
            # Check labels contain expected keys
            assert "endpoint=" in labels or "method=" in labels
            assert value >= 0
    
    def test_histogram_metrics(self, client):
        """Test histogram metrics format"""
        response = client.get("/metrics")
        content = response.text
        
        # Check for histogram buckets
        bucket_lines = [
            l for l in content.split("\n")
            if "request_latency_seconds_bucket" in l
        ]
        
        assert len(bucket_lines) > 0, "Should have histogram buckets"
        
        # Check for histogram sum and count
        assert "request_latency_seconds_sum" in content
        assert "request_latency_seconds_count" in content
        
        # Verify bucket format
        for line in bucket_lines:
            if line and not line.startswith("#"):
                assert 'le=' in line, "Histogram buckets should have 'le' label"
    
    def test_gauge_metrics(self, client):
        """Test gauge metrics format"""
        response = client.get("/metrics")
        content = response.text
        
        # Find gauge metrics
        gauge_lines = [
            l for l in content.split("\n")
            if "queue_depth{" in l or "data_freshness_seconds{" in l
        ]
        
        for line in gauge_lines:
            # Verify format
            match = re.match(r'(\w+)\{([^}]*)\}\s+([\d.]+)', line)
            assert match is not None, f"Invalid gauge format: {line}"
            
            metric_name = match.group(1)
            labels = match.group(2)
            value = float(match.group(3))
            
            assert value >= 0, f"Gauge value should be non-negative: {line}"
    
    def test_metrics_json_endpoint(self, client):
        """Test JSON metrics endpoint for debugging"""
        response = client.get("/metrics/json")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check structure
        assert "counters" in data
        assert "histograms" in data
        assert "gauges" in data
        
        # Check counters
        assert "request_count" in data["counters"]
        assert "error_count" in data["counters"]
        
        # Check histograms
        assert "request_latency" in data["histograms"]
        assert "buckets" in data["histograms"]["request_latency"]
        assert "sum" in data["histograms"]["request_latency"]
        assert "count" in data["histograms"]["request_latency"]
        
        # Check gauges
        assert "queue_depth" in data["gauges"]
        assert "data_freshness_seconds" in data["gauges"]
    
    def test_increment_metric_endpoint(self, client):
        """Test metric increment endpoint"""
        # Get initial metrics
        response1 = client.get("/metrics/json")
        initial_data = response1.json()
        
        # Increment a test metric
        response = client.post(
            "/metrics/increment/test_counter",
            params={"value": 5, "module": "test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "incremented"
        assert data["metric"] == "test_counter"
        assert data["value"] == "5"
        
        # Verify metric was incremented
        response2 = client.get("/metrics/json")
        updated_data = response2.json()
        
        # Check custom metrics
        assert "custom" in updated_data
        assert any(
            "test_counter" in key 
            for key in updated_data["custom"].keys()
        )
    
    def test_set_gauge_endpoint(self, client):
        """Test gauge setting endpoint"""
        response = client.post(
            "/metrics/gauge/test_gauge",
            params={"value": 42.5, "module": "test"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "set"
        assert data["metric"] == "test_gauge"
        assert data["value"] == "42.5"
        
        # Verify in metrics output
        metrics_response = client.get("/metrics")
        assert "test_gauge" in metrics_response.text
    
    def test_metrics_cache_headers(self, client):
        """Test that metrics have proper cache headers"""
        response = client.get("/metrics")
        assert response.status_code == 200
        
        # Should have no-cache headers for real-time metrics
        assert response.headers.get("Cache-Control") == "no-cache, no-store, must-revalidate"
        assert response.headers.get("Pragma") == "no-cache"
        assert response.headers.get("Expires") == "0"
    
    def test_concurrent_metric_updates(self, client):
        """Test concurrent metric updates"""
        import concurrent.futures
        
        def increment_metric(i):
            response = client.post(
                f"/metrics/increment/concurrent_test",
                params={"value": 1, "module": f"thread_{i}"}
            )
            return response.status_code
        
        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(increment_metric, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(status == 200 for status in results)
    
    def test_metric_values_increment(self, client):
        """Test that metric values actually increment"""
        # Get initial state
        response1 = client.get("/metrics")
        content1 = response1.text
        
        # Make some requests to generate metrics
        client.get("/health/market_data")
        client.get("/health/execution")
        
        # Increment a counter
        client.post("/metrics/increment/test_increment", params={"value": 10})
        
        # Get updated state
        response2 = client.get("/metrics")
        content2 = response2.text
        
        # Content should be different (metrics updated)
        assert content1 != content2
        
        # Test increment should be present
        assert "test_increment" in content2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])