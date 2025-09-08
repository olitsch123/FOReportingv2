"""API client for frontend to backend communication."""

import os
from typing import Any, Dict, Optional

import requests
import streamlit as st

# Get API base URL from environment
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def get_health() -> Dict[str, Any]:
    """Get API health status."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        response.raise_for_status()
        return {"status": "healthy", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def get_pe_health() -> Dict[str, Any]:
    """Get PE module health status."""
    try:
        response = requests.get(f"{API_BASE_URL}/pe/health", timeout=5)
        response.raise_for_status()
        return {"status": "healthy", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def get_stats() -> Dict[str, Any]:
    """Get system statistics."""
    try:
        response = requests.get(f"{API_BASE_URL}/stats", timeout=5)
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def get_pe_documents(doc_type: Optional[str] = None, fund_id: Optional[str] = None, 
                    investor_code: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    """Get PE documents with filtering."""
    try:
        params = {"limit": limit}
        if doc_type:
            params["doc_type"] = doc_type
        if fund_id:
            params["fund_id"] = fund_id
        if investor_code:
            params["investor_code"] = investor_code
            
        response = requests.get(f"{API_BASE_URL}/pe/documents", params=params, timeout=10)
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def get_pe_kpis(fund_id: str, as_of_date: Optional[str] = None) -> Dict[str, Any]:
    """Get PE KPIs for a fund."""
    try:
        params = {"fund_id": fund_id}
        if as_of_date:
            params["as_of_date"] = as_of_date
            
        response = requests.get(f"{API_BASE_URL}/pe/kpis", params=params, timeout=5)
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def get_pe_nav_bridge(fund_id: str, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get NAV bridge data for a fund."""
    try:
        params = {"fund_id": fund_id}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        response = requests.get(f"{API_BASE_URL}/pe/nav-bridge", params=params, timeout=5)
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def get_pe_cashflows(fund_id: str, start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get cashflows for a fund."""
    try:
        params = {"fund_id": fund_id}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        response = requests.get(f"{API_BASE_URL}/pe/cashflows", params=params, timeout=5)
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def get_pe_jobs() -> Dict[str, Any]:
    """Get PE processing jobs status."""
    try:
        response = requests.get(f"{API_BASE_URL}/pe/jobs", timeout=5)
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def post_pe_rag_query(query: str, top_k: int = 5, fund_id: Optional[str] = None, 
                     doc_type: Optional[str] = None) -> Dict[str, Any]:
    """Execute RAG query against PE documents."""
    try:
        payload = {"query": query, "top_k": top_k}
        if fund_id:
            payload["fund_id"] = fund_id
        if doc_type:
            payload["doc_type"] = doc_type
            
        response = requests.post(f"{API_BASE_URL}/pe/rag/query", json=payload, timeout=10)
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def retry_pe_job(job_id: str) -> Dict[str, Any]:
    """Retry a failed PE processing job."""
    try:
        response = requests.post(f"{API_BASE_URL}/pe/retry-job/{job_id}", timeout=5)
        response.raise_for_status()
        return {"status": "success", "data": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def show_api_status():
    """Show API connection status banner in Streamlit."""
    health = get_health()
    pe_health = get_pe_health()
    
    if health["status"] == "healthy" and pe_health["status"] == "healthy":
        st.success(f"🟢 API Connected: {API_BASE_URL}")
    else:
        st.error(f"🔴 API Unavailable: {API_BASE_URL}")
        st.error(f"Main API: {health.get('error', 'Unknown error')}")
        st.error(f"PE API: {pe_health.get('error', 'Unknown error')}")
        st.info("💡 Make sure the backend is running on the configured API_BASE_URL")