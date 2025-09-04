"""Enhanced API client with production-grade features."""

import os
import uuid
import time
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import streamlit as st
from structlog import get_logger

logger = get_logger()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))


class APIClient:
    """Production-grade API client with retry logic and error handling."""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=API_MAX_RETRIES,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Default headers
        session.headers.update({
            "User-Agent": "FOReporting-Frontend/2.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        return session
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling and logging."""
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        url = f"{self.base_url}{endpoint}"
        
        # Add request ID to headers
        headers = {"X-Client-Request-ID": request_id}
        
        # Log request
        logger.info(
            "api_request",
            request_id=request_id,
            method=method,
            url=url,
            params=params,
            has_body=json_data is not None
        )
        
        start_time = time.time()
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=timeout or API_TIMEOUT
            )
            
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "api_response",
                request_id=request_id,
                status_code=response.status_code,
                duration=round(duration, 3),
                server_request_id=response.headers.get("X-Request-ID")
            )
            
            # Handle different status codes
            if response.status_code == 204:
                return {"status": "success", "data": None}
            
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            return {
                "status": "success",
                "data": data,
                "request_id": request_id,
                "server_request_id": response.headers.get("X-Request-ID"),
                "duration": duration
            }
            
        except requests.exceptions.Timeout:
            logger.error(
                "api_timeout",
                request_id=request_id,
                url=url,
                timeout=timeout or API_TIMEOUT
            )
            return {
                "status": "error",
                "error": "Request timed out",
                "error_type": "timeout",
                "request_id": request_id
            }
            
        except requests.exceptions.ConnectionError:
            logger.error(
                "api_connection_error",
                request_id=request_id,
                url=url
            )
            return {
                "status": "error",
                "error": "Cannot connect to API server",
                "error_type": "connection",
                "request_id": request_id
            }
            
        except requests.exceptions.HTTPError as e:
            # Try to parse error response
            error_detail = "Unknown error"
            try:
                error_data = e.response.json()
                if "error" in error_data:
                    error_detail = error_data["error"].get("message", str(e))
                elif "detail" in error_data:
                    error_detail = error_data["detail"]
            except:
                error_detail = str(e)
            
            logger.error(
                "api_http_error",
                request_id=request_id,
                url=url,
                status_code=e.response.status_code,
                error=error_detail
            )
            
            return {
                "status": "error",
                "error": error_detail,
                "error_type": "http",
                "status_code": e.response.status_code,
                "request_id": request_id,
                "server_request_id": e.response.headers.get("X-Request-ID")
            }
            
        except Exception as e:
            logger.error(
                "api_unexpected_error",
                request_id=request_id,
                url=url,
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "status": "error",
                "error": f"Unexpected error: {str(e)}",
                "error_type": "unexpected",
                "request_id": request_id
            }
    
    # Health endpoints
    def get_health(self) -> Dict[str, Any]:
        """Get API health status."""
        return self._make_request("GET", "/health", timeout=5)
    
    def get_pe_health(self) -> Dict[str, Any]:
        """Get PE module health status."""
        return self._make_request("GET", "/pe/health", timeout=5)
    
    # Statistics
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        return self._make_request("GET", "/stats")
    
    # PE Document endpoints
    def get_pe_documents(
        self,
        doc_type: Optional[str] = None,
        fund_id: Optional[str] = None,
        investor_code: Optional[str] = None,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        limit: int = 200,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get PE documents with filtering."""
        params = {
            "limit": limit,
            "offset": offset
        }
        
        # Add optional filters
        if doc_type:
            params["doc_type"] = doc_type
        if fund_id:
            params["fund_id"] = fund_id
        if investor_code:
            params["investor_code"] = investor_code
        if period_start:
            params["period_start"] = period_start
        if period_end:
            params["period_end"] = period_end
            
        return self._make_request("GET", "/pe/documents", params=params)
    
    # KPI endpoints
    def get_pe_kpis(
        self,
        fund_id: str,
        as_of_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get PE KPIs for a fund."""
        params = {"fund_id": fund_id}
        if as_of_date:
            params["as_of_date"] = as_of_date
            
        return self._make_request("GET", "/pe/kpis", params=params)
    
    # NAV bridge endpoint
    def get_pe_nav_bridge(
        self,
        fund_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get NAV bridge data for a fund."""
        params = {"fund_id": fund_id}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        return self._make_request("GET", "/pe/nav-bridge", params=params)
    
    # Cashflow endpoints
    def get_pe_cashflows(
        self,
        fund_id: str,
        flow_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get cashflows for a fund."""
        params = {"fund_id": fund_id}
        if flow_type:
            params["flow_type"] = flow_type
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        return self._make_request("GET", "/pe/cashflows", params=params)
    
    # Job management
    def get_pe_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get PE processing jobs status."""
        params = {"limit": limit}
        if status:
            params["status"] = status
            
        return self._make_request("GET", "/pe/jobs", params=params)
    
    def retry_pe_job(self, job_id: str) -> Dict[str, Any]:
        """Retry a failed PE processing job."""
        return self._make_request("POST", f"/pe/retry-job/{job_id}")
    
    # RAG endpoints
    def query_pe_rag(
        self,
        query: str,
        top_k: int = 5,
        fund_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        investor_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute RAG query against PE documents."""
        payload = {
            "query": query,
            "top_k": top_k
        }
        
        if fund_id:
            payload["fund_id"] = fund_id
        if doc_type:
            payload["doc_type"] = doc_type
        if investor_code:
            payload["investor_code"] = investor_code
            
        return self._make_request("POST", "/pe/rag/query", json_data=payload)
    
    # File processing
    def scan_folders(self) -> Dict[str, Any]:
        """Scan configured folders for new files."""
        return self._make_request("GET", "/scan-folders")
    
    def process_file(
        self,
        file_path: str,
        investor_code: str
    ) -> Dict[str, Any]:
        """Process a specific file."""
        payload = {
            "file_path": file_path,
            "investor_code": investor_code
        }
        return self._make_request("POST", "/documents/process", json_data=payload)


# Singleton instance
_api_client = None

def get_api_client() -> APIClient:
    """Get or create API client singleton."""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client


# Streamlit UI helpers
def show_api_status():
    """Show API connection status banner in Streamlit."""
    client = get_api_client()
    
    health = client.get_health()
    pe_health = client.get_pe_health()
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        if health["status"] == "success" and pe_health["status"] == "success":
            st.success(f"🟢 API Connected: {client.base_url}")
        else:
            st.error(f"🔴 API Unavailable: {client.base_url}")
    
    with col2:
        if health["status"] == "success":
            db_status = health["data"]["services"].get("database", "unknown")
            if db_status == "connected":
                st.success("🗄️ DB OK")
            else:
                st.warning("🗄️ DB Down")
    
    with col3:
        if pe_health["status"] == "success":
            st.success("📄 PE OK")
        else:
            st.warning("📄 PE Down")
    
    # Show errors if any
    if health["status"] == "error":
        st.error(f"Main API Error: {health.get('error', 'Unknown error')}")
    if pe_health["status"] == "error":
        st.error(f"PE API Error: {pe_health.get('error', 'Unknown error')}")


def handle_api_response(response: Dict[str, Any], show_success: bool = True) -> Any:
    """Handle API response and show appropriate UI feedback."""
    if response["status"] == "success":
        if show_success:
            st.success("✅ Request successful")
        return response.get("data")
    else:
        error_msg = response.get("error", "Unknown error")
        error_type = response.get("error_type", "unknown")
        
        if error_type == "timeout":
            st.error(f"⏱️ Request timed out. Please try again.")
        elif error_type == "connection":
            st.error(f"🔌 Cannot connect to API server. Please check if the backend is running.")
        elif error_type == "http":
            status_code = response.get("status_code", 500)
            if status_code == 404:
                st.warning(f"🔍 Not found: {error_msg}")
            elif status_code == 409:
                st.warning(f"⚠️ Conflict: {error_msg}")
            elif status_code == 422:
                st.error(f"❌ Validation error: {error_msg}")
            else:
                st.error(f"❌ Error ({status_code}): {error_msg}")
        else:
            st.error(f"❌ Error: {error_msg}")
        
        # Show request ID for debugging
        if response.get("request_id"):
            st.caption(f"Request ID: {response['request_id']}")
        
        return None