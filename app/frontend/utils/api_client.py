"""Centralized API client for frontend."""

import logging
import os
from typing import Any, Dict, Optional

import requests
import streamlit as st

logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def api_request(
    endpoint: str, 
    method: str = "GET", 
    params: Optional[Dict] = None, 
    json_data: Optional[Dict] = None, 
    timeout: int = 30
) -> Dict[str, Any]:
    """Make API request with comprehensive error handling."""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        
        if method == "GET":
            response = requests.get(url, params=params, timeout=timeout)
        elif method == "POST":
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=json_data, headers=headers, timeout=timeout)
        else:
            return {"status": "error", "error": f"Unsupported method: {method}"}
        
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
        
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Cannot connect to API at {API_BASE_URL}"
        logger.error(f"API connection error: {e}")
        return {"status": "error", "error": error_msg}
        
    except requests.exceptions.Timeout as e:
        error_msg = f"API request timed out after {timeout}s"
        logger.error(f"API timeout: {e}")
        return {"status": "error", "error": error_msg}
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"API returned error: {e.response.status_code}"
        logger.error(f"API HTTP error: {e}")
        return {"status": "error", "error": error_msg}
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        logger.error(f"API request error: {e}")
        return {"status": "error", "error": error_msg}


def fetch_data(endpoint: str, params: Optional[Dict] = None, timeout: int = 30) -> Optional[Dict]:
    """Fast data fetching with error handling."""
    try:
        result = api_request(endpoint, params=params, timeout=timeout)
        return result.get("data") if result["status"] == "success" else None
    except Exception as e:
        logger.debug(f"Data fetch failed for {endpoint}: {e}")
        return None


def show_api_status():
    """Show API connection status banner."""
    health = api_request("/health")
    pe_health = api_request("/pe/documents")
    
    if health["status"] == "success" and pe_health["status"] == "success":
        st.success(f"🟢 API Connected: {API_BASE_URL}")
        return True
    else:
        st.error(f"🔴 API Unavailable: {API_BASE_URL}")
        if health["status"] == "error":
            st.error(f"Main API: {health.get('error', 'Unknown error')}")
        if pe_health["status"] == "error":
            st.error(f"PE API: {pe_health.get('error', 'Unknown error')}")
        st.info("💡 Make sure the backend is running on the configured API_BASE_URL")
        return False


def handle_api_error(error_info: Dict[str, Any], context: str = ""):
    """Handle and display API errors consistently."""
    if error_info["status"] == "error":
        error_msg = error_info.get("error", "Unknown error")
        if context:
            st.error(f"{context}: {error_msg}")
        else:
            st.error(error_msg)
        logger.error(f"API error in {context}: {error_msg}")
        return False
    return True