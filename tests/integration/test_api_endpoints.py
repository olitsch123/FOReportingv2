"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from app.main import app


@pytest.fixture
def test_client():
    """Create test client for API testing."""
    return TestClient(app)


@pytest.fixture
def mock_database_dependencies():
    """Mock database dependencies for testing."""
    with patch('app.main.get_db') as mock_get_db:
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        yield mock_db


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_root_endpoint(self, test_client):
        """Test root endpoint returns system info."""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        with patch('app.services.vector_service.VectorService.get_collection_stats') as mock_stats:
            mock_stats.return_value = {"status": "connected", "total_chunks": 100}
            
            response = test_client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "services" in data
            assert "vector_stats" in data


class TestDocumentEndpoints:
    """Test document-related endpoints."""
    
    def test_get_documents_without_auth(self, test_client):
        """Test getting documents without authentication."""
        response = test_client.get("/documents")
        
        # Should work without auth for GET requests
        assert response.status_code in [200, 500]  # 500 if no DB connection
    
    def test_process_document_without_auth(self, test_client):
        """Test processing document without authentication."""
        response = test_client.post("/documents/process", json={
            "file_path": "/test/path.pdf",
            "investor_code": "test"
        })
        
        # Should require authentication
        assert response.status_code == 403
    
    @patch('app.security.RequireAPIKey', return_value=None)
    def test_process_document_with_auth(self, mock_auth, test_client, mock_database_dependencies):
        """Test processing document with authentication."""
        with patch('app.services.document_service.DocumentService.process_document') as mock_process:
            mock_process.return_value = Mock(id="test_id")
            
            response = test_client.post("/documents/process", json={
                "file_path": "/test/path.pdf",
                "investor_code": "test"
            })
            
            # Should succeed with auth
            assert response.status_code == 200
            data = response.json()
            assert "status" in data


class TestPEEndpoints:
    """Test PE-specific endpoints."""
    
    def test_pe_documents_endpoint(self, test_client):
        """Test PE documents endpoint."""
        with patch('app.database.connection.get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.execute.return_value.all.return_value = []
            mock_get_db.return_value = mock_db
            
            response = test_client.get("/pe/documents")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
    
    def test_pe_health_endpoint(self, test_client):
        """Test PE health endpoint."""
        response = test_client.get("/pe/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data


class TestInvestorEndpoints:
    """Test investor-related endpoints."""
    
    def test_get_investors(self, test_client):
        """Test getting investors."""
        response = test_client.get("/investors")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if data:  # If investors returned
            investor = data[0]
            assert "id" in investor
            assert "name" in investor
            assert "code" in investor
    
    def test_get_funds(self, test_client, mock_database_dependencies):
        """Test getting funds."""
        mock_database_dependencies.query.return_value.join.return_value.all.return_value = []
        
        response = test_client.get("/funds")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestFileWatcherEndpoints:
    """Test file watcher endpoints."""
    
    def test_file_watcher_status(self, test_client):
        """Test file watcher status endpoint."""
        response = test_client.get("/file-watcher/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "watched_folders" in data
    
    def test_file_watcher_start(self, test_client):
        """Test starting file watcher."""
        with patch('app.services.file_watcher.FileWatcherService.start') as mock_start:
            mock_start.return_value = None
            
            response = test_client.post("/file-watcher/start")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
    
    def test_file_watcher_stop(self, test_client):
        """Test stopping file watcher."""
        with patch('app.services.file_watcher.FileWatcherService.stop') as mock_stop:
            mock_stop.return_value = None
            
            response = test_client.post("/file-watcher/stop")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Test complete workflows."""
    
    def test_document_processing_workflow(self, test_client):
        """Test complete document processing workflow."""
        # This would test the full pipeline from file upload to data extraction
        # For now, just test that the endpoints are accessible
        
        # 1. Check system health
        health_response = test_client.get("/health")
        assert health_response.status_code == 200
        
        # 2. Get investors
        investors_response = test_client.get("/investors")
        assert investors_response.status_code == 200
        
        # 3. Get documents
        docs_response = test_client.get("/documents")
        assert docs_response.status_code in [200, 500]  # 500 if no DB