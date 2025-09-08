"""Dashboard overview page."""

import logging
from typing import Dict, Any, Optional

import streamlit as st

from app.frontend.utils.api_client import fetch_data, handle_api_error
from app.frontend.utils.formatters import format_currency, format_processing_status
from app.frontend.utils.state import get_state, set_state

logger = logging.getLogger(__name__)


def render_dashboard():
    """Render the main dashboard overview page."""
    st.header("Dashboard Overview")
    
    # System metrics
    render_system_metrics()
    
    st.markdown("---")
    
    # Processing overview
    render_processing_overview()
    
    st.markdown("---")
    
    # Recent activity
    render_recent_activity()


def render_system_metrics():
    """Render system-wide metrics."""
    st.subheader("📊 System Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        # Get stats efficiently
        tracker_stats = fetch_data("/document-tracker/stats", timeout=10) or {}
        pe_docs = fetch_data("/pe/documents", timeout=10) or []
        
        # Calculate metrics
        total_discovered = tracker_stats.get("total", 0)
        pe_processed = len([doc for doc in pe_docs if doc.get("doc_id")])
        
        with col1:
            st.metric("📄 Files Discovered", total_discovered, help="Files found and tracked")
        with col2:
            st.metric("🤖 AI Processed", pe_processed, help="Documents processed with OpenAI extraction")
        with col3:
            st.metric("💰 Financial Data", pe_processed, help="Documents with extracted financial data")
        with col4:
            st.metric("⏳ Ready to Process", total_discovered - pe_processed, help="Files ready for OpenAI processing")
    
    except Exception as e:
        st.warning(f"Could not load system metrics: {str(e)}")
        logger.warning(f"System metrics loading error: {e}")


def render_processing_overview():
    """Render processing status overview."""
    st.subheader("🔄 Processing Overview")
    
    try:
        stats = fetch_data("/stats", timeout=10)
        if not stats:
            st.warning("Processing statistics unavailable")
            return
        
        # Database stats
        db_stats = stats.get("database", {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📊 Database Summary**")
            st.metric("Documents", db_stats.get("documents", 0))
            st.metric("Investors", db_stats.get("investors", 0))
            st.metric("Funds", db_stats.get("funds", 0))
            st.metric("Financial Data Points", db_stats.get("financial_data_points", 0))
        
        with col2:
            st.markdown("**📈 Processing Status**")
            status_counts = db_stats.get("processing_status", {})
            for status, count in status_counts.items():
                icon, display_status = format_processing_status(status)
                st.metric(f"{icon} {display_status}", count)
        
        # Vector store stats
        vector_stats = stats.get("vector_store", {})
        if vector_stats.get("status") == "connected":
            st.success(f"🔍 Vector Store: {vector_stats.get('total_chunks', 0)} chunks indexed")
        else:
            st.warning("🔍 Vector Store: Disconnected")
    
    except Exception as e:
        st.error(f"Could not load processing overview: {str(e)}")
        logger.error(f"Processing overview error: {e}")


def render_recent_activity():
    """Render recent activity feed."""
    st.subheader("📋 Recent Activity")
    
    try:
        # Get recent documents
        recent_docs = fetch_data("/documents", params={"limit": 10})
        
        if not recent_docs:
            st.info("No recent activity")
            return
        
        for doc in recent_docs:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**{doc.get('filename', 'Unknown')}**")
                    st.caption(f"Investor: {doc.get('investor_name', 'Unknown')}")
                
                with col2:
                    doc_type = doc.get('document_type', 'unknown')
                    st.write(f"Type: {doc_type.replace('_', ' ').title()}")
                    confidence = doc.get('confidence_score', 0)
                    if confidence > 0:
                        st.caption(f"Confidence: {confidence:.1%}")
                
                with col3:
                    status = doc.get('processing_status', 'unknown')
                    icon, display_status = format_processing_status(status)
                    st.write(f"{icon} {display_status}")
                
                st.markdown("---")
    
    except Exception as e:
        st.error(f"Could not load recent activity: {str(e)}")
        logger.error(f"Recent activity error: {e}")


def render_quick_actions():
    """Render quick action buttons."""
    st.subheader("⚡ Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 Scan Folders", help="Scan for new documents"):
            with st.spinner("Scanning folders..."):
                result = fetch_data("/file-watcher/scan", timeout=30)
                if result:
                    st.success("Scan completed!")
                    st.rerun()
                else:
                    st.error("Scan failed")
    
    with col2:
        if st.button("📊 Refresh Stats", help="Refresh dashboard statistics"):
            st.rerun()
    
    with col3:
        if st.button("🧹 Clear Cache", help="Clear session cache"):
            st.cache_data.clear()
            st.success("Cache cleared!")


def render_system_health():
    """Render system health indicators."""
    try:
        health = fetch_data("/health")
        if not health:
            st.error("Cannot check system health")
            return
        
        overall_status = health.get("status", "unknown")
        services = health.get("services", {})
        
        if overall_status == "healthy":
            st.success("🟢 All systems operational")
        else:
            st.warning(f"🟡 System status: {overall_status}")
        
        # Service details
        with st.expander("Service Details"):
            for service, status in services.items():
                if status == "connected":
                    st.success(f"✅ {service.title()}: Connected")
                elif status == "stopped":
                    st.info(f"⏸️ {service.title()}: Stopped")
                else:
                    st.error(f"❌ {service.title()}: {status}")
    
    except Exception as e:
        st.error(f"Health check failed: {str(e)}")
        logger.error(f"Health check error: {e}")


def render_dashboard_header():
    """Render the dashboard header with key information."""
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.title("📊 FOReporting v2")
        st.caption("Financial Document Intelligence System")
    
    with col2:
        # Current time
        st.metric("🕐 Current Time", datetime.now().strftime("%H:%M"))
    
    with col3:
        # Quick system status
        try:
            health = fetch_data("/health", timeout=5)
            if health and health.get("status") == "healthy":
                st.success("🟢 Online")
            else:
                st.error("🔴 Issues")
        except Exception:
            st.warning("🟡 Unknown")