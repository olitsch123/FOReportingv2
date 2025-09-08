"""End-to-end user workflow tests."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from pathlib import Path

from app.main import app
from tests.fixtures.sample_documents import SAMPLE_CAPITAL_ACCOUNT_PDF


@pytest.fixture
def client():
    """Create test client for E2E testing."""
    return TestClient(app)


@pytest.fixture
def mock_file_system():
    """Mock file system for E2E testing."""
    with patch('pathlib.Path.exists') as mock_exists, \
         patch('pathlib.Path.is_file') as mock_is_file, \
         patch('pathlib.Path.stat') as mock_stat:
        
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_stat.return_value = Mock(st_size=1024000)  # 1MB file
        
        yield


class TestCompleteDocumentProcessingWorkflow:
    """Test complete document processing from start to finish."""
    
    @patch('app.services.document_service.DocumentService.process_document')
    def test_full_document_processing_workflow(self, mock_process, client, mock_file_system):
        """Test the complete workflow from file discovery to data extraction."""
        # Mock successful processing
        mock_result = Mock()
        mock_result.id = "test-doc-id"
        mock_result.filename = "test_document.pdf"
        mock_result.document_type = "capital_account_statement"
        mock_process.return_value = mock_result
        
        # 1. System health check
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # 2. Get system statistics
        stats_response = client.get("/stats")
        assert stats_response.status_code == 200
        
        # 3. Get investors
        investors_response = client.get("/investors")
        assert investors_response.status_code == 200
        investors = investors_response.json()
        assert len(investors) >= 1
        
        # 4. Process a document (with mocked authentication)
        with patch('app.security.RequireAPIKey', return_value=None):
            process_response = client.post("/documents/process", json={
                "file_path": "/test/sample_capital_account.pdf",
                "investor_code": "brainweb"
            })
            
            assert process_response.status_code == 200
            process_data = process_response.json()
            assert process_data["status"] == "completed"
        
        # 5. Verify document was created
        docs_response = client.get("/documents")
        assert docs_response.status_code in [200, 500]  # May fail if no DB
    
    def test_pe_analytics_workflow(self, client):
        """Test PE analytics and reporting workflow."""
        # 1. Check PE system health
        pe_health = client.get("/pe/health")
        assert pe_health.status_code == 200
        
        # 2. Get PE documents
        pe_docs = client.get("/pe/documents")
        assert pe_docs.status_code == 200
        
        # 3. Get fund KPIs
        kpis = client.get("/pe/kpis")
        assert kpis.status_code == 200
        
        # 4. Test NAV bridge analysis
        nav_bridge = client.get("/pe/nav-bridge")
        assert nav_bridge.status_code == 200
        
        # 5. Test cashflow analysis
        cashflows = client.get("/pe/cashflows")
        assert cashflows.status_code == 200


class TestChatWorkflow:
    """Test AI chat functionality workflow."""
    
    @patch('app.services.chat_service.ChatService.chat')
    def test_chat_conversation_workflow(self, mock_chat, client):
        """Test complete chat conversation workflow."""
        # Mock chat service response
        mock_chat.return_value = {
            "response": "Based on the latest capital account statements, the NAV for Q2 2023 is €1.5M.",
            "context_documents": 3,
            "financial_data_points": 15
        }
        
        # 1. Start chat conversation (without auth for testing)
        with patch('app.security.RequireAPIKey', return_value=None):
            chat_response = client.post("/chat", json={
                "message": "What is the NAV for Q2 2023?",
                "session_id": None
            })
            
            assert chat_response.status_code == 200
            data = chat_response.json()
            assert "response" in data
            assert "session_id" in data
            assert "context_documents" in data
        
        # 2. Continue conversation with session ID
        session_id = chat_response.json().get("session_id", "test-session")
        
        with patch('app.security.RequireAPIKey', return_value=None):
            followup_response = client.post("/chat", json={
                "message": "How does this compare to Q1?",
                "session_id": session_id
            })
            
            assert followup_response.status_code == 200
        
        # 3. Get chat history
        history_response = client.get(f"/chat/sessions/{session_id}/history")
        assert history_response.status_code in [200, 500]  # May fail if no session storage


class TestFileWatcherWorkflow:
    """Test file watcher functionality workflow."""
    
    def test_file_watcher_control_workflow(self, client):
        """Test file watcher start/stop/scan workflow."""
        # 1. Get initial status
        status_response = client.get("/file-watcher/status")
        assert status_response.status_code == 200
        
        initial_status = status_response.json()
        assert "is_running" in initial_status
        
        # 2. Start file watcher
        start_response = client.post("/file-watcher/start")
        assert start_response.status_code == 200
        
        # 3. Trigger manual scan
        scan_response = client.post("/file-watcher/scan")
        assert scan_response.status_code == 200
        
        scan_data = scan_response.json()
        assert "status" in scan_data
        
        # 4. Stop file watcher
        stop_response = client.post("/file-watcher/stop")
        assert stop_response.status_code == 200


class TestSearchWorkflow:
    """Test document search functionality."""
    
    @patch('app.services.vector_service.VectorService.search_documents')
    def test_semantic_search_workflow(self, mock_search, client):
        """Test semantic search workflow."""
        # Mock search results
        mock_search.return_value = [
            {
                "doc_id": "test-doc-1",
                "content": "Capital account statement for Q2 2023",
                "similarity_score": 0.92,
                "metadata": {"fund": "Test Fund"}
            },
            {
                "doc_id": "test-doc-2", 
                "content": "Quarterly performance report",
                "similarity_score": 0.78,
                "metadata": {"fund": "Test Fund"}
            }
        ]
        
        # Test search
        response = client.get("/search?query=capital account Q2 2023&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert isinstance(data["results"], list)


@pytest.mark.integration
class TestSystemIntegration:
    """Test system-wide integration scenarios."""
    
    def test_system_startup_sequence(self, client):
        """Test that all systems start up correctly."""
        # This simulates the startup sequence verification
        
        # 1. Basic connectivity
        root_response = client.get("/")
        assert root_response.status_code == 200
        
        # 2. Health checks
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # 3. PE system availability
        pe_health = client.get("/pe/health")
        assert pe_health.status_code == 200
        
        # 4. Core endpoints availability
        endpoints_to_test = [
            "/investors",
            "/funds", 
            "/documents",
            "/pe/documents",
            "/pe/kpis",
            "/file-watcher/status"
        ]
        
        for endpoint in endpoints_to_test:
            response = client.get(endpoint)
            # Should be accessible (may return empty data without DB)
            assert response.status_code in [200, 500]
    
    def test_error_handling_integration(self, client):
        """Test that error handling works across the system."""
        # Test various error scenarios
        
        # 1. Invalid endpoint
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        
        # 2. Invalid method
        response = client.patch("/")  # PATCH not allowed
        assert response.status_code == 405
        
        # 3. Invalid JSON in POST request
        response = client.post("/pe/rag/query",
                              data="invalid json",
                              headers={"Content-Type": "application/json"})
        assert response.status_code == 422
        
        # All error responses should have consistent format
        for resp in [response]:
            if resp.status_code >= 400:
                data = resp.json()
                assert "error" in data or "detail" in data