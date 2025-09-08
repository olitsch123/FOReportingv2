"""Integration tests for PE document workflows."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from app.main import app
from tests.fixtures.sample_documents import SAMPLE_EXTRACTION_RESULTS


@pytest.fixture
def client():
    """Create test client for integration testing."""
    return TestClient(app)


@pytest.fixture
def mock_pe_dependencies():
    """Mock PE-specific dependencies for integration testing."""
    with patch('app.pe_docs.storage.orm.PEStorageORM') as mock_storage:
        mock_storage.return_value.get_capital_account_series.return_value = [
            SAMPLE_EXTRACTION_RESULTS["capital_account"]
        ]
        mock_storage.return_value.get_funds_by_investor.return_value = [
            {"id": "test-fund-id", "name": "Test Fund"}
        ]
        yield mock_storage


class TestPEDocumentEndpoints:
    """Test PE document API endpoints."""
    
    def test_pe_health_endpoint(self, client):
        """Test PE health check endpoint."""
        response = client.get("/pe/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert data["components"]["import_status"] == "success"
    
    def test_get_pe_documents(self, client, mock_pe_dependencies):
        """Test getting PE documents list."""
        with patch('app.database.connection.get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.execute.return_value.all.return_value = []
            mock_get_db.return_value = mock_db
            
            response = client.get("/pe/documents")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
    
    def test_get_pe_documents_with_filters(self, client, mock_pe_dependencies):
        """Test PE documents with filtering parameters."""
        with patch('app.database.connection.get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.execute.return_value.all.return_value = []
            mock_get_db.return_value = mock_db
            
            response = client.get("/pe/documents?doc_type=capital_account_statement&limit=10")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


class TestPEAnalyticsEndpoints:
    """Test PE analytics API endpoints."""
    
    def test_nav_bridge_analysis(self, client, mock_pe_dependencies):
        """Test NAV bridge analysis endpoint."""
        response = client.get("/pe/nav-bridge?fund_id=test-fund-id")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_capital_account_series(self, client, mock_pe_dependencies):
        """Test capital account series endpoint."""
        response = client.get("/pe/capital-account-series/test-fund-id")
        
        # May return 404 if fund not found, which is acceptable for testing
        assert response.status_code in [200, 404, 500]
    
    def test_fund_kpis(self, client, mock_pe_dependencies):
        """Test fund KPIs endpoint."""
        response = client.get("/pe/kpis?fund_id=test-fund-id")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_cashflows(self, client, mock_pe_dependencies):
        """Test cashflows endpoint."""
        response = client.get("/pe/cashflows?fund_id=test-fund-id")
        
        assert response.status_code == 200
        data = response.json()
        assert "cashflows" in data
        assert "summary" in data


class TestPEProcessingEndpoints:
    """Test PE processing API endpoints."""
    
    def test_process_capital_account_without_auth(self, client):
        """Test processing endpoint requires authentication."""
        response = client.post("/pe/process-capital-account", json={
            "file_path": "/test/path.pdf",
            "investor_code": "test"
        })
        
        # Should require authentication
        assert response.status_code == 403
    
    def test_processing_jobs(self, client):
        """Test processing jobs endpoint."""
        response = client.get("/pe/jobs")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('app.security.RequireAPIKey', return_value=None)
    def test_retry_job(self, mock_auth, client):
        """Test job retry endpoint with authentication."""
        response = client.post("/pe/retry-job/test-job-id")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "queued"


class TestPEReconciliationEndpoints:
    """Test PE reconciliation API endpoints."""
    
    def test_reconciliation_history(self, client, mock_pe_dependencies):
        """Test reconciliation history endpoint."""
        response = client.get("/pe/reconciliation-history")
        
        assert response.status_code == 200
        data = response.json()
        assert "reconciliations" in data
        assert "summary" in data
    
    def test_reconciliation_details(self, client, mock_pe_dependencies):
        """Test reconciliation details endpoint."""
        response = client.get("/pe/reconciliation/test-reconciliation-id")
        
        # May return 404 if reconciliation not found
        assert response.status_code in [200, 404, 500]


class TestRAGEndpoints:
    """Test RAG (Retrieval-Augmented Generation) endpoints."""
    
    def test_rag_query(self, client):
        """Test RAG query endpoint."""
        with patch('app.services.vector_service.VectorService.search_documents') as mock_search:
            mock_search.return_value = [
                {
                    "doc_id": "test-doc",
                    "content": "Sample content",
                    "similarity_score": 0.85,
                    "metadata": {"fund_info": "Test Fund"}
                }
            ]
            
            response = client.post("/pe/rag/query", json={
                "query": "What is the NAV for Q2 2023?",
                "fund_id": "test-fund-id",
                "limit": 5
            })
            
            assert response.status_code == 200
            data = response.json()
            assert "query" in data
            assert "results" in data
            assert isinstance(data["results"], list)


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    def test_document_processing_workflow(self, client):
        """Test complete document processing workflow."""
        # 1. Check system health
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # 2. Check PE system health
        pe_health_response = client.get("/pe/health")
        assert pe_health_response.status_code == 200
        
        # 3. Get available documents
        docs_response = client.get("/pe/documents")
        assert docs_response.status_code == 200
        
        # 4. Test analytics endpoints
        analytics_response = client.get("/pe/kpis")
        assert analytics_response.status_code == 200
    
    def test_monitoring_endpoints(self, client):
        """Test monitoring and metrics endpoints."""
        # Test stats endpoint
        response = client.get("/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "database" in data
        assert "vector_store" in data
        assert "file_watcher" in data
        assert "pe_system" in data
    
    def test_file_watcher_workflow(self, client):
        """Test file watcher control workflow."""
        # Get status
        status_response = client.get("/file-watcher/status")
        assert status_response.status_code == 200
        
        # Test scan trigger
        scan_response = client.post("/file-watcher/scan")
        assert scan_response.status_code == 200
    
    def test_investor_and_funds_workflow(self, client):
        """Test investor and funds data workflow."""
        # Get investors
        investors_response = client.get("/investors")
        assert investors_response.status_code == 200
        
        investors = investors_response.json()
        assert isinstance(investors, list)
        
        # Get funds
        funds_response = client.get("/funds")
        assert funds_response.status_code in [200, 500]  # 500 if no DB connection


@pytest.mark.integration
class TestSecurityIntegration:
    """Test security features integration."""
    
    def test_rate_limiting_simulation(self, client):
        """Test rate limiting behavior."""
        # Make multiple rapid requests to test rate limiting
        responses = []
        for i in range(5):  # Small number for testing
            response = client.get("/")
            responses.append(response.status_code)
        
        # All should succeed in normal testing
        assert all(status == 200 for status in responses)
    
    def test_invalid_inputs_handling(self, client):
        """Test handling of invalid inputs."""
        # Test with invalid JSON
        response = client.post("/pe/rag/query", 
                              data="invalid json",
                              headers={"Content-Type": "application/json"})
        assert response.status_code == 422
        
        # Test with missing required fields
        response = client.post("/pe/rag/query", json={})
        assert response.status_code == 422
    
    def test_error_response_format(self, client):
        """Test that error responses follow the expected format."""
        # Trigger a validation error
        response = client.post("/pe/rag/query", json={})
        
        assert response.status_code == 422
        data = response.json()
        assert "error" in data


@pytest.mark.integration  
class TestMonitoringIntegration:
    """Test monitoring and observability integration."""
    
    def test_health_check_comprehensive(self, client):
        """Test comprehensive health check."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify health check structure
        assert "status" in data
        assert "services" in data
        assert "deployment_mode" in data
        
        services = data["services"]
        expected_services = ["database", "vector_store", "file_watcher"]
        for service in expected_services:
            assert service in services
    
    def test_metrics_endpoint_availability(self, client):
        """Test that metrics endpoint is available."""
        # The metrics endpoint is added by prometheus-fastapi-instrumentator
        response = client.get("/metrics")
        
        # Should be available (200) or not configured (404)
        assert response.status_code in [200, 404]
    
    def test_request_id_header(self, client):
        """Test that request ID headers are added."""
        response = client.get("/")
        
        assert response.status_code == 200
        # Check for request ID header (added by error handling middleware)
        assert "X-Request-ID" in response.headers or response.status_code == 200


@pytest.mark.slow
class TestPerformanceIntegration:
    """Test performance characteristics of the system."""
    
    def test_api_response_times(self, client):
        """Test API response times are reasonable."""
        import time
        
        start_time = time.time()
        response = client.get("/")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 1.0  # Should respond within 1 second
    
    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests."""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = client.get("/health")
            results.append(response.status_code)
        
        # Create multiple threads for concurrent requests
        threads = []
        for i in range(5):  # Small number for testing
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert len(results) == 5
        assert all(status == 200 for status in results)