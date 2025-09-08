"""Performance benchmarks for FOReporting v2."""

import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from app.main import app


@pytest.fixture
def client():
    """Create test client for performance testing."""
    return TestClient(app)


class TestAPIPerformance:
    """Test API endpoint performance."""
    
    def test_root_endpoint_performance(self, client):
        """Test root endpoint response time."""
        start_time = time.time()
        response = client.get("/")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        
        # Should respond within 100ms for root endpoint
        assert response_time < 0.1, f"Root endpoint too slow: {response_time:.3f}s"
    
    def test_health_check_performance(self, client):
        """Test health check endpoint performance."""
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        
        # Health check should respond within 2 seconds
        assert response_time < 2.0, f"Health check too slow: {response_time:.3f}s"
    
    def test_stats_endpoint_performance(self, client):
        """Test stats endpoint performance."""
        start_time = time.time()
        response = client.get("/stats")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Stats endpoint should respond within 3 seconds
        assert response_time < 3.0, f"Stats endpoint too slow: {response_time:.3f}s"
    
    @pytest.mark.slow
    def test_concurrent_request_performance(self, client):
        """Test performance under concurrent load."""
        import threading
        import statistics
        
        response_times = []
        
        def make_request():
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            
            if response.status_code == 200:
                response_times.append(end_time - start_time)
        
        # Create 10 concurrent requests
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        total_time = time.time() - start_time
        
        # Analyze results
        if response_times:
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            
            # Performance assertions
            assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.3f}s"
            assert max_response_time < 3.0, f"Max response time too high: {max_response_time:.3f}s"
            assert total_time < 10.0, f"Total concurrent processing too slow: {total_time:.3f}s"


class TestDocumentProcessingPerformance:
    """Test document processing performance."""
    
    @patch('app.services.document_service.DocumentService.process_document')
    def test_document_processing_speed(self, mock_process, client):
        """Test document processing speed."""
        # Mock fast processing
        mock_result = Mock()
        mock_result.id = "test-doc-id"
        mock_process.return_value = mock_result
        
        # Simulate processing time
        def slow_process(*args, **kwargs):
            time.sleep(0.1)  # Simulate 100ms processing
            return mock_result
        
        mock_process.side_effect = slow_process
        
        with patch('app.security.RequireAPIKey', return_value=None):
            start_time = time.time()
            response = client.post("/documents/process", json={
                "file_path": "/test/sample.pdf",
                "investor_code": "test"
            })
            end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should complete within reasonable time (including mocked processing)
        assert processing_time < 5.0, f"Document processing too slow: {processing_time:.3f}s"


class TestDatabasePerformance:
    """Test database operation performance."""
    
    def test_document_query_performance(self, client):
        """Test document listing query performance."""
        start_time = time.time()
        response = client.get("/documents?limit=100")
        end_time = time.time()
        
        query_time = end_time - start_time
        
        # Database queries should be fast
        assert query_time < 2.0, f"Document query too slow: {query_time:.3f}s"
    
    def test_fund_query_performance(self, client):
        """Test fund listing query performance."""
        start_time = time.time()
        response = client.get("/funds")
        end_time = time.time()
        
        query_time = end_time - start_time
        
        # Fund queries should be fast
        assert query_time < 1.0, f"Fund query too slow: {query_time:.3f}s"


## Performance Baselines

### **Established Performance Targets**

**API Response Times:**
- Root endpoint: < 100ms
- Health check: < 2s
- Document listing: < 2s
- Stats endpoint: < 3s

**Document Processing:**
- Small files (< 1MB): < 30s
- Medium files (1-10MB): < 60s
- Large files (10-100MB): < 300s

**Concurrent Load:**
- 10 concurrent requests: < 10s total
- Average response time: < 1s
- Maximum response time: < 3s

**Database Operations:**
- Document queries: < 2s
- Fund queries: < 1s
- Complex analytics: < 5s

### **Performance Monitoring**

**Prometheus Metrics:**
- `http_request_duration_seconds` - API response times
- `document_processing_duration_seconds` - Processing speed
- `database_query_duration_seconds` - Database performance
- `concurrent_requests_active` - Load monitoring

**Grafana Dashboards:**
- Real-time performance monitoring
- Historical trend analysis
- Performance alerting thresholds
- Resource utilization tracking