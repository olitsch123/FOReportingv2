"""Streamlit dashboard for FOReporting v2."""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - Environment-driven API base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# API Client Functions (inline to avoid import issues)
def api_request(endpoint: str, method: str = "GET", params: dict = None, json_data: dict = None, timeout: int = 30) -> dict:
    """Make API request with error handling."""
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
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def show_api_status():
    """Show API connection status banner."""
    health = api_request("/health")
    pe_health = api_request("/pe/documents")  # Use existing PE endpoint
    
    if health["status"] == "success" and pe_health["status"] == "success":
        st.success(f"🟢 API Connected: {API_BASE_URL}")
    else:
        st.error(f"🔴 API Unavailable: {API_BASE_URL}")
        if health["status"] == "error":
            st.error(f"Main API: {health.get('error', 'Unknown error')}")
        if pe_health["status"] == "error":
            st.error(f"PE API: {pe_health.get('error', 'Unknown error')}")
        st.info("💡 Make sure the backend is running on the configured API_BASE_URL")

# Page configuration
st.set_page_config(
    page_title="FOReporting v2 - Financial Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .chat-message {
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
    }
    .user-message {
        background-color: #e3f2fd;
        margin-left: 2rem;
    }
    .assistant-message {
        background-color: #f5f5f5;
        margin-right: 2rem;
    }
    /* Enhanced chat interface styles */
    .stChatMessage {
        padding: 0.5rem;
        margin-bottom: 0.5rem;
    }
    div[data-testid="stChatMessageContent"] {
        padding: 0.5rem;
    }
    /* Style the chat input area */
    .stTextArea textarea {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 10px;
        font-size: 14px;
    }
    .stTextArea textarea:focus {
        border-color: #1f77b4;
        box-shadow: 0 0 0 1px #1f77b4;
    }
    /* Style the example prompt buttons */
    button[key^="prompt_"] {
        text-align: left;
        white-space: normal;
        height: auto;
        padding: 0.5rem;
        margin: 0.25rem 0;
    }
    /* Chat container styling */
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 1rem;
        background-color: #fafafa;
        border-radius: 10px;
    }
    /* Metric styling in context column */
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_data(endpoint: str, params: Dict = None) -> Dict:
    """Fetch data from API with caching."""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}


@st.cache_data(ttl=60)  # Cache for 1 minute
def fetch_stats() -> Dict:
    """Fetch system statistics."""
    return fetch_data("/stats")


def send_chat_message(message: str, session_id: str = None) -> Dict:
    """Send chat message to API."""
    try:
        payload = {"message": message}
        if session_id:
            payload["session_id"] = session_id
        
        response = requests.post(f"{API_BASE_URL}/chat", json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Chat Error: {str(e)}")
        return {}


def process_all_files():
    """Process all unprocessed files."""
    if "unprocessed_files" not in st.session_state:
        st.error("No files to process")
        return
    
    files = st.session_state["unprocessed_files"]
    process_batch_files(len(files))


def process_batch_files(batch_size: int):
    """Process a batch of files."""
    if "unprocessed_files" not in st.session_state:
        st.error("No files to process")
        return
    
    files = st.session_state["unprocessed_files"][:batch_size]
    
    # Create a progress container
    progress_container = st.container()
    
    with progress_container:
        st.info(f"🔄 Processing {len(files)} files...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        success_count = 0
        failed_count = 0
        
        for i, file_info in enumerate(files):
            status_text.text(f"Processing ({i+1}/{len(files)}): {file_info['filename']}")
            
            # Process file
            process_result = api_request(
                "/documents/process",
                method="POST",
                json_data={
                    "file_path": file_info["file_path"],
                    "investor_code": file_info["investor_code"]
                }
            )
            
            if process_result["status"] == "success":
                success_count += 1
            else:
                failed_count += 1
                st.error(f"Failed: {file_info['filename']}: {process_result.get('error', 'Unknown error')}")
            
            # Update progress
            progress_bar.progress((i + 1) / len(files))
        
        # Show summary
        st.success(f"✅ Processing complete! Success: {success_count}, Failed: {failed_count}")
        
        # Remove processed files from the list
        st.session_state["unprocessed_files"] = st.session_state["unprocessed_files"][batch_size:]
        
        # Refresh if all files are processed
        if len(st.session_state["unprocessed_files"]) == 0:
            del st.session_state["unprocessed_files"]
            time.sleep(2)
            st.rerun()


def process_selected_files(selected_indices):
    """Process selected files."""
    if "unprocessed_files" not in st.session_state:
        st.error("No files available")
        return
    
    files = st.session_state["unprocessed_files"]
    selected_files = [files[i] for i in selected_indices]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, file_info in enumerate(selected_files):
        status_text.text(f"Processing: {file_info['filename']}")
        
        # Process file
        process_result = api_request(
            "/documents/process",
            method="POST",
            json_data={
                "file_path": file_info["file_path"],
                "investor_code": file_info["investor_code"]
            }
        )
        
        if process_result["status"] == "success":
            st.success(f"✅ Processed: {file_info['filename']}")
        else:
            st.error(f"❌ Failed: {file_info['filename']} - {process_result.get('error', 'Unknown error')}")
        
        progress_bar.progress((i + 1) / len(selected_files))
    
    status_text.text("Processing complete!")
    # Remove processed files from the list
    remaining_files = [f for i, f in enumerate(files) if i not in selected_indices]
    st.session_state["unprocessed_files"] = remaining_files


def render_header():
    """Render the main header."""
    st.markdown('<h1 class="main-header">📊 FOReporting v2</h1>', unsafe_allow_html=True)
    st.markdown("**Financial Document Intelligence System**")
    st.markdown("---")


def render_sidebar():
    """Render the sidebar with navigation and filters."""
    st.sidebar.title("Navigation")
    
    page = st.sidebar.selectbox(
        "Select Page",
        ["Dashboard", "Chat Interface", "Documents", "Funds", "Analytics", "PE — Portfolio", "PE — Capital Accounts", "PE — Documents & RAG", "PE — Reconciliation"]
    )
    
    st.sidebar.markdown("---")
    
    # System status
    st.sidebar.subheader("System Status")
    try:
        health = fetch_data("/health")
        if health.get("status") == "healthy":
            st.sidebar.success("✅ System Healthy")
        else:
            st.sidebar.error("❌ System Issues")
        
        services = health.get("services", {})
        for service, status in services.items():
            # Special handling for file watcher status
            if service == "file_watcher":
                if status == "running":
                    icon = "✅"
                elif status == "stopped":
                    icon = "⏸️"
                else:
                    icon = "❌"
            else:
                # For other services (database, vector_store)
                icon = "✅" if status in ["connected", "running"] else "❌"
            st.sidebar.text(f"{icon} {service.title()}: {status}")
        
        # File Watcher Controls
        st.sidebar.markdown("---")
        st.sidebar.subheader("📁 File Watcher")
        
        # Get file watcher status
        fw_status = api_request("/file-watcher/status")
        if fw_status["status"] == "success":
            fw_data = fw_status["data"]
            is_running = fw_data.get("is_running", False)
            total_files = fw_data.get("total_files_found", 0)
            
            # Status display with better info
            if is_running:
                st.sidebar.success("✅ Active - Monitoring")
                if total_files > 0:
                    st.sidebar.info(f"📄 {total_files} files found")
            else:
                st.sidebar.warning("⏸️ Inactive")
            
            # Queue status
            queue_size = fw_data.get("queue_size", 0)
            if queue_size > 0:
                st.sidebar.warning(f"⏳ Processing: {queue_size} files")
            
            # Control buttons in columns
            col1, col2, col3 = st.sidebar.columns(3)
            with col1:
                if st.button("▶️", help="Start monitoring", disabled=is_running, key="fw_start"):
                    result = api_request("/file-watcher/start", method="POST")
                    if result["status"] == "success":
                        st.rerun()
            with col2:
                if st.button("⏹️", help="Stop monitoring", disabled=not is_running, key="fw_stop"):
                    result = api_request("/file-watcher/stop", method="POST")
                    if result["status"] == "success":
                        st.rerun()
            with col3:
                if st.button("🔍", help="Scan folders now", key="fw_scan"):
                    result = api_request("/file-watcher/scan", method="POST")
                    if result["status"] == "success":
                        st.sidebar.success(result["data"]["message"])
                        st.rerun()
            
            # Show errors if any
            if fw_data.get("scan_errors"):
                with st.sidebar.expander("⚠️ Issues", expanded=True):
                    for error in fw_data["scan_errors"]:
                        st.error(error)
        else:
            st.sidebar.error("Cannot get file watcher status")
    except (requests.exceptions.RequestException, ConnectionError, TimeoutError) as e:
        st.sidebar.error(f"❌ Cannot connect to API: {str(e)}")
        logger.error(f"API connection error in sidebar: {e}")
    
    return page


def render_dashboard():
    """Render the main dashboard."""
    st.header("Dashboard Overview")
    
    # Fetch statistics
    stats = fetch_stats()
    if not stats:
        st.error("Unable to load system statistics")
        return
    
    db_stats = stats.get("database", {})
    vector_stats = stats.get("vector_store", {})
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Documents",
            value=db_stats.get("documents", 0),
            delta=None
        )
    
    with col2:
        st.metric(
            label="Active Funds",
            value=db_stats.get("funds", 0),
            delta=None
        )
    
    with col3:
        st.metric(
            label="Data Points",
            value=db_stats.get("financial_data_points", 0),
            delta=None
        )
    
    with col4:
        st.metric(
            label="Vector Chunks",
            value=vector_stats.get("total_chunks", 0),
            delta=None
        )
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Document Processing Status")
        status_data = db_stats.get("processing_status", {})
        if status_data:
            fig = px.pie(
                values=list(status_data.values()),
                names=list(status_data.keys()),
                title="Processing Status Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Document Types")
        type_data = db_stats.get("document_types", {})
        if type_data:
            # Filter out zero values
            type_data = {k: v for k, v in type_data.items() if v > 0}
            if type_data:
                fig = px.bar(
                    x=list(type_data.keys()),
                    y=list(type_data.values()),
                    title="Document Types Distribution"
                )
                fig.update_xaxis(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
    
    # File Watcher Activity
    st.markdown("---")
    st.subheader("📁 File Watcher Monitor")
    
    fw_status = api_request("/file-watcher/status")
    if fw_status["status"] == "success":
        fw_data = fw_status["data"]
        
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if fw_data.get("is_running"):
                st.success("🟢 Active")
            else:
                st.warning("🔴 Inactive")
        
        with col2:
            total_files = fw_data.get("total_files_found", 0)
            st.metric("Files Discovered", total_files)
        
        with col3:
            st.metric("Folders Monitored", len(fw_data.get("watched_folders", [])))
        
        with col4:
            queue_size = fw_data.get("queue_size", 0)
            st.metric("Processing Queue", queue_size)
        
        # Detailed folder status
        if fw_data.get("watched_folders"):
            st.markdown("#### 📂 Monitored Folders")
            for folder in fw_data["watched_folders"]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    if folder.get("exists", False):
                        st.success(f"**{folder['name']}**")
                        st.caption(f"📍 {folder['path']}")
                    else:
                        st.error(f"**{folder['name']}** - Folder not found!")
                        st.caption(f"❌ {folder['path']}")
                with col2:
                    if folder.get("exists", False):
                        st.metric("Files", folder.get("file_count", 0))
        
        # Recent discoveries
        if fw_data.get("discovered_files"):
            st.markdown("#### 🆕 Recent Discoveries")
            discoveries_df = pd.DataFrame(fw_data["discovered_files"])
            st.dataframe(
                discoveries_df,
                use_container_width=True,
                hide_index=True
            )
        
        # Scan errors
        if fw_data.get("scan_errors"):
            st.markdown("#### ⚠️ Scan Issues")
            for error in fw_data["scan_errors"]:
                st.error(error)
        
        # Manual controls
        st.markdown("#### 🎮 Controls")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔍 Scan Now", help="Manually scan all folders"):
                scan_result = api_request("/file-watcher/scan", method="POST")
                if scan_result["status"] == "success":
                    st.success(scan_result["data"]["message"])
                    st.rerun()
        with col2:
            if fw_data.get("is_running"):
                if st.button("⏸️ Pause Monitoring"):
                    api_request("/file-watcher/stop", method="POST")
                    st.rerun()
            else:
                if st.button("▶️ Start Monitoring"):
                    api_request("/file-watcher/start", method="POST")
                    st.rerun()
        with col3:
            if st.button("🔄 Refresh Status"):
                st.rerun()
    else:
        st.error("Cannot retrieve file watcher status")
    
    # Document Tracker Section
    st.markdown("---")
    st.subheader("📊 Document Tracking")
    
    # Get tracker stats
    tracker_stats = api_request("/document-tracker/stats")
    if tracker_stats["status"] == "success":
        stats = tracker_stats["data"]
        
        # Display stats in columns
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Documents", stats.get("total", 0))
        with col2:
            st.metric("Completed", stats.get("completed", 0), delta_color="normal")
        with col3:
            st.metric("Processing", stats.get("processing", 0), delta_color="off")
        with col4:
            st.metric("Discovered", stats.get("discovered", 0), delta_color="off")
        with col5:
            st.metric("Failed", stats.get("failed", 0), delta_color="inverse")
        
        # Export controls
        st.markdown("#### 📥 Export Document Status")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "Status Filter",
                ["all", "completed", "processing", "discovered", "failed"],
                help="Filter documents by status"
            )
        
        with col2:
            format_type = st.selectbox(
                "Export Format",
                ["csv", "json"],
                help="Choose export format"
            )
        
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)  # Spacing
            if st.button("📥 Export", help="Download document tracking data"):
                # Create download URL
                status_param = f"&status={status_filter}" if status_filter != "all" else ""
                download_url = f"{API_BASE_URL}/document-tracker/export?format={format_type}{status_param}"
                
                # Create download link
                import requests
                response = requests.get(download_url)
                if response.status_code == 200:
                    if format_type == "csv":
                        st.download_button(
                            label="⬇️ Download CSV",
                            data=response.content,
                            file_name=f"document_tracker_{status_filter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.download_button(
                            label="⬇️ Download JSON",
                            data=response.content,
                            file_name=f"document_tracker_{status_filter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                else:
                    st.error("Export failed")
        
        # Show sample of tracked documents
        if stats.get("total", 0) > 0:
            with st.expander("📄 Recent Document Status", expanded=False):
                # Get sample documents
                export_response = api_request(f"/document-tracker/export?format=json&status={status_filter}")
                if export_response["status"] == "success":
                    documents = export_response["data"][:10]  # Show first 10
                    
                    if documents:
                        # Create dataframe for display
                        df_data = []
                        for doc in documents:
                            df_data.append({
                                "File Name": doc.get("file_name", "")[:50] + "...",
                                "Status": doc.get("status", ""),
                                "Fund": doc.get("fund_name", "") or "❌ Not Mapped",
                                "Type": doc.get("document_type", "") or "❌ Unknown",
                                "Investor": doc.get("investor_name", ""),
                                "Hash": doc.get("file_hash", "")[:8] + "...",
                            })
                        
                        df = pd.DataFrame(df_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Documents needing attention
            with st.expander("⚠️ Documents Needing Fund/Asset Mapping", expanded=True):
                # Get documents without fund mapping
                unmapped_response = api_request("/document-tracker/export?format=json&status=completed")
                if unmapped_response["status"] == "success":
                    all_docs = unmapped_response["data"]
                    unmapped_docs = [
                        doc for doc in all_docs 
                        if not doc.get("fund_name") or doc.get("fund_name") == "Unknown Fund"
                    ]
                    
                    if unmapped_docs:
                        st.warning(f"🔍 {len(unmapped_docs)} documents need fund/asset mapping")
                        
                        # Show first few unmapped documents
                        for doc in unmapped_docs[:5]:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.text(f"📄 {doc['file_name']}")
                                st.caption(f"Type: {doc.get('document_type', 'Unknown')} | Path: .../{'/'.join(doc['file_path'].split('\\')[-3:])}")
                            with col2:
                                if st.button("🔗 Map Fund", key=f"map_{doc['id']}"):
                                    st.info("Fund mapping UI coming soon!")
                        
                        if len(unmapped_docs) > 5:
                            st.info(f"... and {len(unmapped_docs) - 5} more documents")
                    else:
                        st.success("✅ All documents are properly mapped to funds!")
    
    # Recent activity
    st.subheader("Recent Documents")
    documents = fetch_data("/documents", {"limit": 10})
    if documents:
        df = pd.DataFrame(documents)
        if not df.empty:
            # Select relevant columns
            display_cols = ["filename", "document_type", "confidence_score", 
                          "processing_status", "investor_name", "created_at"]
            available_cols = [col for col in display_cols if col in df.columns]
            
            if available_cols:
                df_display = df[available_cols].copy()
                df_display["created_at"] = pd.to_datetime(df_display["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
                st.dataframe(df_display, use_container_width=True)


def render_chat_interface():
    """Render an enhanced chat interface for document intelligence."""
    st.header("🤖 Document Intelligence Chat")
    st.markdown("Ask questions about your PE fund documents, capital accounts, and financial data.")
    
    # Initialize session state
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = None
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_input_counter" not in st.session_state:
        st.session_state.chat_input_counter = 0
    
    # Create two columns for chat and context
    chat_col, context_col = st.columns([2, 1])
    
    with context_col:
        st.subheader("📊 Chat Context")
        
        # Session info
        if st.session_state.chat_session_id:
            st.info(f"🔗 Session: ...{st.session_state.chat_session_id[-8:]}")
        
        # Document stats
        stats_result = api_request("/stats")
        if stats_result["status"] == "success":
            stats = stats_result["data"]
            st.metric("Total Documents", stats.get("total_documents", 0))
            st.metric("Embedded Documents", stats.get("documents_with_embeddings", 0))
            
            pe_stats = stats.get("pe_documents", {})
            if pe_stats:
                st.metric("Capital Accounts", pe_stats.get("capital_accounts", 0))
        
        # Quick prompts
        st.subheader("💡 Example Questions")
        example_prompts = [
            "What are the latest capital account balances?",
            "Show me the fund performance metrics",
            "What distributions were made in Q3 2023?",
            "Summarize the investment portfolio",
            "What are the unfunded commitments?"
        ]
        
        for prompt in example_prompts:
            if st.button(f"📌 {prompt}", key=f"prompt_{prompt}"):
                st.session_state[f"chat_input_{st.session_state.chat_input_counter}"] = prompt
                st.session_state.chat_input_counter += 1
                st.rerun()
        
        # Clear chat button
        if st.button("🗑️ Clear Chat History", type="secondary"):
            st.session_state.chat_messages = []
            st.session_state.chat_session_id = None
            st.rerun()
    
    with chat_col:
        # Chat container with custom styling
        chat_container = st.container()
        
        # Display chat messages
        with chat_container:
            # Show welcome message if no messages
            if not st.session_state.chat_messages:
                st.markdown("""
                <div style='text-align: center; padding: 2rem; color: #666;'>
                    <h3>👋 Welcome to Document Intelligence</h3>
                    <p>Ask questions about your PE fund documents, capital accounts, and financial data.</p>
                    <p>I can help you analyze fund performance, track investments, and understand your portfolio.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Display chat history
                for i, msg in enumerate(st.session_state.chat_messages):
                    if msg["type"] == "user":
                        with st.chat_message("user", avatar="👤"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="🤖"):
                            st.markdown(msg["content"])
                            
                            # Show context info
                            if msg.get("context_docs", 0) > 0 or msg.get("data_points", 0) > 0:
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.caption(f"📄 {msg.get('context_docs', 0)} documents")
                                with col2:
                                    st.caption(f"📊 {msg.get('data_points', 0)} data points")
                                with col3:
                                    st.caption(f"🕐 {msg['timestamp'].strftime('%H:%M')}")
        
        # Input area at the bottom
        st.markdown("---")
        
        # Chat input form
        with st.form(key="chat_form", clear_on_submit=True):
            user_input = st.text_area(
                "Ask your question:",
                placeholder="Type your question here... (Press Ctrl+Enter to send)",
                key=f"chat_input_{st.session_state.chat_input_counter}",
                height=100
            )
            
            col1, col2, col3 = st.columns([1, 1, 3])
            with col1:
                submit_button = st.form_submit_button("🚀 Send", type="primary")
            with col2:
                search_depth = st.selectbox(
                    "Search Depth",
                    ["Normal", "Deep"],
                    help="Deep search looks through more documents"
                )
        
        # Process message
        if submit_button and user_input:
            # Add user message immediately
            st.session_state.chat_messages.append({
                "type": "user",
                "content": user_input,
                "timestamp": datetime.now()
            })
            
            # Show typing indicator
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Analyzing documents and preparing response..."):
                    # Determine context limit based on search depth
                    context_limit = 10 if search_depth == "Deep" else 5
                    
                    # Send message to API
                    response = send_chat_message(user_input, st.session_state.chat_session_id)
                    
                    if response:
                        # Update session ID
                        st.session_state.chat_session_id = response.get("session_id")
                        
                        # Add assistant response
                        assistant_msg = {
                            "type": "assistant",
                            "content": response.get("response", "I apologize, but I couldn't process your request. Please try again."),
                            "timestamp": datetime.now(),
                            "context_docs": response.get("context_documents", 0),
                            "data_points": response.get("financial_data_points", 0)
                        }
                        st.session_state.chat_messages.append(assistant_msg)
                        
                        # Increment counter to reset input
                        st.session_state.chat_input_counter += 1
                        st.rerun()
                    else:
                        st.error("Failed to get response. Please check if the backend is running.")
        
        # Show typing indicator for streaming (future enhancement)
        if st.session_state.get("is_typing", False):
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown("_Typing..._")


def render_documents():
    """Fast, functional document management interface."""
    st.header("📄 Document Processing")
    
    # Quick stats at the top
    col1, col2, col3, col4 = st.columns(4)
    
    try:
        # Get stats efficiently
        tracker_stats = fetch_data("/document-tracker/stats", timeout=10) or {}
        pe_docs = fetch_data("/pe/documents", timeout=10) or []
        
        # Correct metrics
        total_discovered = tracker_stats.get("total", 0)
        pe_processed = len([doc for doc in pe_docs if doc.get("doc_id")])  # Actual PE processing
        
        with col1:
            st.metric("📄 Files Discovered", total_discovered, help="Files found and tracked")
        with col2:
            st.metric("🤖 AI Processed", pe_processed, help="Documents processed with OpenAI extraction")
        with col3:
            st.metric("💰 Financial Data", pe_processed, help="Documents with extracted financial data")
        with col4:
            st.metric("⏳ Ready to Process", total_discovered - pe_processed, help="Files ready for OpenAI processing")
    
    except (requests.exceptions.RequestException, KeyError, ValueError, TypeError) as e:
        st.warning(f"Could not load statistics: {str(e)}")
        logger.warning(f"Statistics loading error: {e}")
    
    st.markdown("---")
    
    # Simple, fast processing interface
    st.subheader("🚀 Process Documents")
    
    # Investor selection
    col1, col2 = st.columns([3, 1])
    
    with col1:
        investor_filter = st.selectbox(
            "🏢 Select Investor:",
            ["All Investors", "BrainWeb Investment", "Pecunalta"],
            key="investor_selection"
        )
    
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    # Fast processing options
    st.markdown("### 🎯 Processing Options")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🚀 Process 100 Files", type="primary", use_container_width=True):
            start_fast_processing(100, investor_filter)
    
    with col2:
        if st.button("📦 Process 500 Files", use_container_width=True):
            start_fast_processing(500, investor_filter)
    
    with col3:
        if st.button("🌊 Process 1000 Files", use_container_width=True):
            start_fast_processing(1000, investor_filter)
    
    with col4:
        if st.button("🔥 Process All Files", use_container_width=True):
            start_fast_processing(99999, investor_filter)
    
    st.markdown("---")
    
    # File Watcher section
    render_file_watcher_simple()
    
    st.markdown("---")
    
    # Recent results
    render_recent_results()
    
    # Debug section (temporary)
    with st.expander("🔧 Debug Info", expanded=False):
        st.markdown("**API Endpoints Test:**")
        
        # Test scan-folders
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Test /scan-folders"):
                try:
                    result = fetch_data("/scan-folders", timeout=30)
                    if result:
                        if isinstance(result, dict) and "total_found" in result:
                            st.success(f"✅ Found {result['total_found']} files")
                        elif isinstance(result, dict) and "unprocessed_files" in result:
                            st.success(f"✅ Found {len(result['unprocessed_files'])} files")
                        else:
                            st.info(f"Data format: {type(result)}")
                            st.json(str(result)[:500])
                    else:
                        st.error("❌ No data returned")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        
        with col2:
            if st.button("Test /folder-tree"):
                try:
                    result = fetch_data("/folder-tree", timeout=30)
                    if result:
                        st.success(f"✅ Tree data received")
                        st.json(str(result)[:500])
                    else:
                        st.error("❌ No tree data")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
    
    # Simple file list (fallback)
    render_simple_file_list()


def render_simple_file_list():
    """Render a simple file list for debugging and basic functionality."""
    st.subheader("📄 Document List (Simple View)")
    
    try:
        # Get files directly from scan-folders
        with st.spinner("Loading documents..."):
            scan_result = api_request("/scan-folders", timeout=60)
            
            if scan_result:
                # Handle different response formats
                if isinstance(scan_result, dict):
                    if "status" in scan_result and scan_result.get("status") == "success":
                        files = scan_result.get("data", {}).get("unprocessed_files", [])
                    elif "unprocessed_files" in scan_result:
                        files = scan_result["unprocessed_files"]
                    else:
                        files = []
                else:
                    files = []
                
                if files:
                    st.success(f"📁 Found {len(files)} documents ready for processing")
                    
                    # Show first 20 files in a table
                    import pandas as pd
                    
                    table_data = []
                    for file_info in files[:20]:
                        # Extract fund name from path
                        path = file_info.get("file_path", "")
                        fund_name = "Unknown"
                        subfolder = "Unknown"
                        
                        if "\\09 Funds\\" in path:
                            parts = path.split("\\")
                            funds_idx = -1
                            for i, part in enumerate(parts):
                                if "09 Funds" in part:
                                    funds_idx = i
                                    break
                            
                            if funds_idx >= 0:
                                if funds_idx + 1 < len(parts):
                                    fund_name = parts[funds_idx + 1]
                                if funds_idx + 2 < len(parts):
                                    subfolder = parts[funds_idx + 2]
                        
                        table_data.append({
                            "Fund": fund_name,
                            "Subfolder": subfolder,
                            "Filename": file_info.get("filename", "Unknown"),
                            "Type": file_info.get("file_type", "Unknown"),
                            "Size (KB)": round(file_info.get("file_size", 0) / 1024, 1),
                            "Investor": file_info.get("investor_code", "Unknown").title()
                        })
                    
                    if table_data:
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True, height=400)
                        
                        st.info(f"Showing first 20 of {len(files)} total documents")
                        
                        # Quick process button
                        if st.button("🚀 Process These 20 Files", type="primary"):
                            process_file_list(files[:20])
                    else:
                        st.warning("No file data to display")
                else:
                    st.warning("No unprocessed files found")
            else:
                st.error("Could not load file list from scan-folders endpoint")
                
    except Exception as e:
        st.error(f"Error loading file list: {e}")


def process_file_list(files):
    """Process a list of files with progress tracking."""
    if not files:
        st.error("No files to process")
        return
    
    st.info(f"🚀 Starting processing of {len(files)} files...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed = 0
    failed = 0
    
    for i, file_info in enumerate(files):
        try:
            # Update progress
            progress = (i + 1) / len(files)
            progress_bar.progress(progress)
            status_text.text(f"Processing: {file_info['filename'][:50]}...")
            
            # Process file
            result = api_request("/documents/process", method="POST", json_data={
                "file_path": file_info["file_path"],
                "investor_code": file_info["investor_code"]
            }, timeout=60)
            
            if result.get("status") == "success":
                processed += 1
            else:
                failed += 1
                
        except Exception as e:
            failed += 1
            st.error(f"Error: {str(e)}")
    
    # Final status
    progress_bar.progress(1.0)
    status_text.text("Processing complete!")
    
    if processed > 0:
        st.success(f"✅ Success: {processed} files processed, {failed} failed")
        st.balloons()
    else:
        st.error(f"❌ Processing failed: {failed} files failed")


def start_fast_processing(batch_size, investor_filter):
    """Start processing with progress feedback."""
    with st.spinner(f"Starting processing of {batch_size} documents..."):
        try:
            # Get files to process
            scan_result = fetch_data("/scan-folders", timeout=30)
            
            if not scan_result:
                st.error("Could not scan folders")
                return
            
            # Handle response format
            if isinstance(scan_result, dict):
                if "status" in scan_result and scan_result.get("status") == "success":
                    all_files = scan_result.get("data", {}).get("unprocessed_files", [])
                elif "unprocessed_files" in scan_result:
                    all_files = scan_result["unprocessed_files"]
                else:
                    st.error("Invalid scan result format")
                    return
            else:
                st.error("Invalid scan result format")
                return
            
            # Filter by investor if needed
            if investor_filter != "All Investors":
                investor_code = "brainweb" if investor_filter == "BrainWeb Investment" else "pecunalta"
                all_files = [f for f in all_files if f.get("investor_code") == investor_code]
            
            # Limit batch size
            files_to_process = all_files[:batch_size] if batch_size < 99999 else all_files
            
            if not files_to_process:
                st.warning(f"No files found to process for {investor_filter}")
                return
            
            st.success(f"🚀 Starting processing of {len(files_to_process)} documents")
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Process files
            processed = 0
            failed = 0
            
            for i, file_info in enumerate(files_to_process):
                try:
                    # Update progress
                    progress = (i + 1) / len(files_to_process)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing: {file_info['filename'][:50]}...")
                    
                    # Process file
                    result = api_request("/documents/process", method="POST", json_data={
                        "file_path": file_info["file_path"],
                        "investor_code": file_info["investor_code"]
                    }, timeout=60)
                    
                    if result.get("status") == "success":
                        processed += 1
                    else:
                        failed += 1
                
                except Exception as e:
                    failed += 1
                    st.error(f"Error processing {file_info['filename']}: {str(e)}")
            
            # Final status
            progress_bar.progress(1.0)
            status_text.text("Processing complete!")
            
            st.success(f"✅ Processing complete: {processed} successful, {failed} failed")
            
            if processed > 0:
                st.balloons()
                
        except Exception as e:
            st.error(f"Processing failed: {str(e)}")


def render_file_watcher_simple():
    """Simple file watcher controls."""
    st.subheader("👁️ File Watcher")
    
    # Get watcher status
    watcher_status = fetch_data("/file-watcher/status", timeout=5)
    is_running = watcher_status.get("status") == "running" if watcher_status else False
    
    col1, col2 = st.columns(2)
    
    with col1:
        if is_running:
            st.success("🟢 **Active** - Monitoring folders for new documents")
            if st.button("⏸️ Stop File Watcher", type="secondary"):
                result = api_request("/file-watcher/stop", method="POST", json_data={})
                if result.get("status") == "success":
                    st.success("File watcher stopped")
                    st.rerun()
        else:
            st.warning("🔴 **Inactive** - No automatic monitoring")
            if st.button("▶️ Start File Watcher", type="primary"):
                result = api_request("/file-watcher/start", method="POST", json_data={})
                if result.get("status") == "success":
                    st.success("File watcher started!")
                    st.rerun()
                else:
                    st.error("Failed to start file watcher")
    
    with col2:
        # Show folder paths being monitored
        if watcher_status and "folders" in watcher_status:
            st.markdown("**Monitored Paths:**")
            for folder in watcher_status["folders"]:
                if folder.get("exists", False):
                    st.caption(f"✅ {folder.get('name', 'Unknown')}")
                else:
                    st.caption(f"❌ {folder.get('name', 'Unknown')}")


def render_recent_results():
    """Show recent processing results."""
    st.subheader("📊 Recent Results")
    
    # Get recent PE documents
    recent_docs = fetch_data("/pe/documents", {"limit": 10}, timeout=10) or []
    
    if recent_docs and len(recent_docs) > 0:
        st.success(f"📈 {len(recent_docs)} documents with extracted financial data")
        
        # Show in a simple table
        import pandas as pd
        
        table_data = []
        for doc in recent_docs[:10]:
            # Extract fund name from path
            fund_name = "Unknown"
            if doc.get("path"):
                path_parts = doc["path"].split("\\")
                for part in path_parts:
                    if "_" in part and any(char.isdigit() for char in part):
                        fund_name = part.split("_")[0]
                        break
            
            table_data.append({
                "Fund": fund_name,
                "Document Type": doc.get("doc_type", "Unknown").replace("_", " ").title(),
                "File": doc.get("file_name", "Unknown")[:40] + "..." if len(doc.get("file_name", "")) > 40 else doc.get("file_name", "Unknown"),
                "Status": "✅ Extracted"
            })
        
        if table_data:
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No financial data extracted yet. Start processing documents to see results here.")
        
        # Show processing suggestion
        st.markdown("**💡 Suggestion:** Start with 'Process 100 Files' to see the OpenAI extraction in action!")


def fetch_data(endpoint: str, params: dict = None, timeout: int = 30) -> dict:
    """Fast data fetching with error handling."""
    try:
        return api_request(endpoint, params=params, timeout=timeout).get("data")
    except (requests.exceptions.RequestException, KeyError, AttributeError) as e:
        logger.debug(f"Data fetch failed for {endpoint}: {e}")
        return None


def render_browse_and_select(selected_investor):
    """Render browse and select interface with proper folder tree."""
    st.subheader("📁 Browse & Select Documents")
    
    # Get directory tree
    tree_data = fetch_data("/folder-tree")
    
    if not tree_data or "investors" not in tree_data:
        st.error("Could not load folder structure. Check if investor paths are configured.")
        return
    
    # Filter by selected investor
    investor_trees = tree_data["investors"]
    if selected_investor != "All Investors":
        investor_trees = [inv for inv in investor_trees if inv["name"] == selected_investor]
    
    if not investor_trees:
        st.warning(f"No data found for {selected_investor}")
        return
    
    # Selection state
    if "selected_paths" not in st.session_state:
        st.session_state.selected_paths = set()
    
    # Quick action buttons
    col1, col2, col3 = st.columns(3)
    
    selected_count = len(st.session_state.selected_paths)
    
    with col1:
        if st.button(f"🚀 Process Selected ({selected_count})", 
                    disabled=selected_count == 0, 
                    type="primary" if selected_count > 0 else "secondary"):
            process_selected_paths()
    
    with col2:
        if st.button("📋 Clear Selection", disabled=selected_count == 0):
            st.session_state.selected_paths.clear()
            st.rerun()
    
    with col3:
        if st.button("📊 Show Selection Details", disabled=selected_count == 0):
            show_selection_details()
    
    st.markdown("---")
    
    # Render directory tree
    for investor in investor_trees:
        render_investor_tree(investor)


def render_investor_tree(investor):
    """Render a single investor's directory tree with Windows-like interface."""
    investor_name = investor["name"]
    
    if "error" in investor:
        st.error(f"❌ {investor_name}: {investor['error']}")
        return
    
    # Calculate total files for investor
    total_files = sum(fund.get("file_count", 0) for fund in investor.get("children", []))
    
    # Investor header with Windows-style icon
    st.markdown(f"""
    <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
        <h4 style="margin: 0; color: #1e3a8a;">
            🏢 {investor_name}
        </h4>
        <small style="color: #6b7280;">
            📊 {len(investor.get('children', []))} funds • {total_files} documents
        </small>
    </div>
    """, unsafe_allow_html=True)
    
    # Show funds in Windows Explorer style
    for fund in investor.get("children", []):
        fund_name = fund["name"]
        fund_files = fund.get("file_count", 0)
        fund_path = fund["path"]
        
        # Keep full fund name with ID (e.g., "Ananda III_5112")
        display_name = fund_name
        
        # Check if fund is expanded
        expand_key = f"expand_{investor_name}_{fund_name}"
        is_expanded = st.session_state.get(expand_key, False)
        
        # Fund row with Windows-style layout
        fund_col1, fund_col2, fund_col3 = st.columns([0.5, 4, 1])
        
        with fund_col1:
            # Expand/collapse triangle (Windows style)
            if st.button(
                "▼" if is_expanded else "▶", 
                key=f"expand_btn_{investor_name}_{fund_name}",
                help="Expand/Collapse"
            ):
                st.session_state[expand_key] = not is_expanded
                st.rerun()
        
        with fund_col2:
            # Fund selection with proper name
            fund_selected = st.checkbox(
                f"📁 **{display_name}** ({fund_files} files)",
                key=f"fund_select_{investor_name}_{fund_name}",
                help=f"Select entire fund: {fund_path}"
            )
            
            if fund_selected:
                st.session_state.selected_paths.add(fund_path)
            else:
                st.session_state.selected_paths.discard(fund_path)
        
        with fund_col3:
            # Status indicator
            if fund_files > 0:
                st.caption("📊 Ready")
            else:
                st.caption("🔍 Empty")
        
        # Show subfolders if expanded (with indentation)
        if is_expanded:
            for subfolder in fund.get("children", []):
                subfolder_name = subfolder["name"]
                subfolder_files = subfolder.get("file_count", 0)
                subfolder_path = subfolder["path"]
                file_types = subfolder.get("file_types", {})
                
                # Keep original subfolder name with prefix (e.g., "02_Quarterly Reports")
                display_subfolder = subfolder_name
                
                # Get processing status from API data
                processing_status = subfolder.get("processing_status", "ready")
                processed_count = subfolder.get("processed_count", 0)
                status_icon = get_status_icon(processing_status)
                
                # File type summary
                type_summary = " • ".join([f"{ext.upper()}: {count}" for ext, count in file_types.items()])
                
                # Subfolder row with indentation
                sub_col1, sub_col2, sub_col3 = st.columns([1, 4, 1])
                
                with sub_col1:
                    st.markdown("　")  # Indentation
                
                with sub_col2:
                    # Show processing progress
                    progress_text = f"({processed_count}/{subfolder_files})" if processed_count > 0 else f"({subfolder_files} files)"
                    
                    subfolder_selected = st.checkbox(
                        f"📂 {display_subfolder} {progress_text}",
                        key=f"subfolder_select_{investor_name}_{fund_name}_{subfolder_name}",
                        help=f"Path: {subfolder_path}\nFiles: {type_summary}\nProcessed: {processed_count}/{subfolder_files}"
                    )
                    
                    if subfolder_selected:
                        st.session_state.selected_paths.add(subfolder_path)
                    else:
                        st.session_state.selected_paths.discard(subfolder_path)
                
                with sub_col3:
                    st.markdown(f"{status_icon}")
                
                # Show file type breakdown
                if file_types:
                    st.caption(f"　　{type_summary}")
        
        st.markdown("<hr style='margin: 5px 0;'>", unsafe_allow_html=True)


def get_subfolder_processing_status(subfolder_path):
    """Get processing status for a subfolder."""
    # This would check the document tracker for files in this path
    # For now, return a placeholder status
    return "ready"  # Could be: ready, processing, completed, mixed


def get_status_icon(status):
    """Get status icon for processing state."""
    status_icons = {
        "ready": "🔵",      # Ready to process
        "processing": "🟡",  # Currently processing
        "completed": "🟢",   # All processed
        "mixed": "🟠",       # Some processed, some not
        "error": "🔴"        # Processing errors
    }
    return status_icons.get(status, "⚪")


def render_batch_processing(selected_investor):
    """Render batch processing interface."""
    st.subheader("📦 Batch Processing")
    
    # Get document stats
    tracker_stats = fetch_data("/document-tracker/stats")
    
    if tracker_stats:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📄 Total Documents", tracker_stats.get("total", 0))
        with col2:
            st.metric("✅ Processed", tracker_stats.get("completed", 0))
        with col3:
            st.metric("⏳ Pending", tracker_stats.get("total", 0) - tracker_stats.get("completed", 0))
    
    st.markdown("---")
    
    # Batch processing options
    st.markdown("### 🎯 Batch Processing Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        batch_size = st.selectbox(
            "📊 Batch Size:",
            [50, 100, 250, 500, 1000, "All"],
            index=1,  # Default to 100
            key="batch_size_selection"
        )
    
    with col2:
        priority_mode = st.selectbox(
            "⚡ Priority:",
            ["Newest First", "Capital Accounts First", "Quarterly Reports First", "Random"],
            key="priority_mode"
        )
    
    # Processing controls
    col1, col2, col3 = st.columns(3)
    
    actual_batch_size = 99999 if batch_size == "All" else batch_size
    
    with col1:
        if st.button(f"🚀 Start Processing ({batch_size})", type="primary", use_container_width=True):
            start_batch_processing(actual_batch_size, priority_mode, selected_investor)
    
    with col2:
        if st.button("📊 Preview Batch", use_container_width=True):
            preview_batch(actual_batch_size, selected_investor)
    
    with col3:
        if st.button("📈 View Progress", use_container_width=True):
            show_processing_progress()


def render_file_watcher_mode(selected_investor):
    """Render file watcher interface."""
    st.subheader("👁️ Real-time File Monitoring")
    
    # File watcher status
    watcher_status = fetch_data("/file-watcher/status")
    is_running = watcher_status.get("status") == "running" if watcher_status else False
    
    # Status display
    if is_running:
        st.success("🟢 **File Watcher Active** - Monitoring investor folders for new documents")
        
        # Show monitoring info
        if watcher_status and "folders" in watcher_status:
            st.markdown("**📁 Monitored Folders:**")
            for folder in watcher_status["folders"]:
                if folder.get("exists", False):
                    st.markdown(f"✅ {folder.get('name', 'Unknown')}")
                    st.caption(folder.get('path', 'Unknown path'))
                else:
                    st.markdown(f"❌ {folder.get('name', 'Unknown')} (not found)")
        
        # Control buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("⏸️ Stop Monitoring", type="secondary", use_container_width=True):
                result = api_request("/file-watcher/stop", method="POST", json_data={})
                if result.get("status") == "success":
                    st.success("File watcher stopped")
                    st.rerun()
                else:
                    st.error("Failed to stop file watcher")
        
        with col2:
            if st.button("📊 View Recent Activity", use_container_width=True):
                show_recent_activity()
    
    else:
        st.warning("🔴 **File Watcher Inactive** - No automatic monitoring")
        
        # Start button
        if st.button("▶️ Start Real-time Monitoring", type="primary", use_container_width=True):
            result = api_request("/file-watcher/start", method="POST", json_data={})
            if result.get("status") == "success":
                st.success("File watcher started successfully!")
                st.rerun()
            else:
                st.error(f"Failed to start file watcher: {result.get('error', 'Unknown error')}")
    
    st.markdown("---")
    
    # Recent processing activity
    st.markdown("### 📈 Recent Activity")
    
    # Get recent documents
    recent_docs = fetch_data("/pe/documents", {"limit": 10})
    
    if recent_docs and len(recent_docs) > 0:
        st.markdown("**🆕 Recently Processed Documents:**")
        
        for doc in recent_docs[:5]:
            doc_name = doc.get("file_name", "Unknown")[:60]
            doc_type = doc.get("doc_type", "Unknown")
            
            st.markdown(f"📄 **{doc_name}**")
            st.caption(f"Type: {doc_type.replace('_', ' ').title()}")
            st.markdown("")
    else:
        st.info("No recent processing activity. Start processing documents to see activity here.")


def start_batch_processing(batch_size, priority_mode, selected_investor):
    """Start batch processing with selected parameters."""
    with st.spinner(f"Starting batch processing of {batch_size} documents..."):
        # This would implement the actual batch processing
        st.success(f"Batch processing started: {batch_size} documents with {priority_mode} priority")


def preview_batch(batch_size, selected_investor):
    """Preview what would be processed in the batch."""
    st.markdown("### 📋 Batch Preview")
    st.info(f"Would process {batch_size} documents for {selected_investor}")


def show_processing_progress():
    """Show current processing progress."""
    st.markdown("### 📈 Processing Progress")
    
    # Get current stats
    stats = fetch_data("/document-tracker/stats")
    
    if stats:
        total = stats.get("total", 0)
        completed = stats.get("completed", 0)
        processing = stats.get("processing", 0)
        failed = stats.get("failed", 0)
        
        # Progress bar
        if total > 0:
            progress = completed / total
            st.progress(progress, text=f"Progress: {completed}/{total} documents ({progress:.1%})")
        
        # Status breakdown
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📄 Total", total)
        with col2:
            st.metric("✅ Completed", completed)
        with col3:
            st.metric("⚙️ Processing", processing)
        with col4:
            st.metric("❌ Failed", failed)


def show_recent_activity():
    """Show recent file watcher activity."""
    st.markdown("### 📈 Recent File Watcher Activity")
    st.info("Recent activity tracking would be shown here")


def show_selection_details():
    """Show details of selected paths."""
    st.markdown("### 📋 Selection Details")
    
    if st.session_state.selected_paths:
        st.markdown("**Selected folders/files:**")
        for path in sorted(st.session_state.selected_paths):
            st.code(path, language=None)
    else:
        st.info("No folders selected")


def process_selected_paths():
    """Process files from selected paths."""
    if not st.session_state.selected_paths:
        st.error("No paths selected for processing")
        return
    
    with st.spinner(f"Processing files from {len(st.session_state.selected_paths)} selected paths..."):
        # This would implement processing of selected paths
        st.success(f"Processing started for {len(st.session_state.selected_paths)} paths")
        st.session_state.selected_paths.clear()


def render_folder_structure_view():
    """Render folder structure view matching your directory organization."""
    st.subheader("📁 Investor Folder Structure")
    
    # Get proper directory tree structure
    tree_data = fetch_data("/folder-tree")
    
    if not tree_data or "investors" not in tree_data:
        st.error("Could not load folder structure. Please check if paths are configured correctly.")
        return
    
    investor_trees = tree_data["investors"]
    
    # Selection state
    if "selected_folders" not in st.session_state:
        st.session_state.selected_folders = set()
    
    # Calculate total files across all investors
    total_files = sum(
        sum(fund.get("file_count", 0) for fund in investor.get("children", []))
        for investor in investor_trees
    )
    
    # Processing controls at top
    st.markdown("### 🎯 Processing Controls")
    
    col1, col2, col3, col4 = st.columns(4)
    
    selected_count = len(st.session_state.selected_folders)
    
    with col1:
        if st.button(f"📦 Process Selected ({selected_count})", disabled=selected_count == 0, key="process_selected"):
            process_selected_folders()
    
    with col2:
        if st.button("📦 Process First 100", key="process_100"):
            process_batch_from_tree(100)
    
    with col3:
        if st.button("📦 Process First 500", key="process_500"):
            process_batch_from_tree(500)
    
    with col4:
        if st.button("📦 Process All", key="process_all"):
            process_batch_from_tree(total_files)
    
    st.markdown("---")
    
    # Render proper directory tree
    st.markdown("### 📁 Directory Structure")
    
    for investor in investor_trees:
        investor_name = investor["name"]
        investor_files = sum(fund.get("file_count", 0) for fund in investor.get("children", []))
        
        # Investor header
        st.markdown(f"#### 👤 {investor_name} ({investor_files} files)")
        
        if "error" in investor:
            st.error(f"❌ {investor['error']}")
            continue
        
        # Show funds
        for fund in investor.get("children", []):
            fund_name = fund["name"]
            fund_files = fund.get("file_count", 0)
            fund_path = fund["path"]
            
            # Fund checkbox
            fund_key = f"fund_{investor_name}_{fund_name}"
            fund_selected = st.checkbox(
                f"🏢 **{fund_name}** ({fund_files} files)",
                key=fund_key,
                help=f"Path: {fund_path}"
            )
            
            if fund_selected:
                st.session_state.selected_folders.add(fund_path)
            else:
                st.session_state.selected_folders.discard(fund_path)
            
            # Show subfolders if fund is expanded
            if fund_selected or st.session_state.get(f"expand_{fund_key}", False):
                with st.container():
                    for subfolder in fund.get("children", []):
                        subfolder_name = subfolder["name"]
                        subfolder_files = subfolder.get("file_count", 0)
                        subfolder_path = subfolder["path"]
                        file_types = subfolder.get("file_types", {})
                        
                        # Create file type summary
                        type_summary = ", ".join([f"{ext}: {count}" for ext, count in file_types.items()])
                        
                        # Subfolder checkbox
                        subfolder_key = f"subfolder_{investor_name}_{fund_name}_{subfolder_name}"
                        subfolder_selected = st.checkbox(
                            f"📂 {subfolder_name} ({subfolder_files} files) - {type_summary}",
                            key=subfolder_key,
                            help=f"Path: {subfolder_path}"
                        )
                        
                        if subfolder_selected:
                            st.session_state.selected_folders.add(subfolder_path)
                        else:
                            st.session_state.selected_folders.discard(subfolder_path)
        
        st.markdown("---")
    
    # Summary
    st.markdown(f"### 📊 Summary")
    st.info(f"Total files available: {total_files} | Selected folders: {selected_count}")


def process_selected_folders():
    """Process files from selected folders."""
    if not st.session_state.selected_folders:
        st.error("No folders selected for processing")
        return
    
    with st.spinner(f"Processing files from {len(st.session_state.selected_folders)} selected folders..."):
        # This would trigger processing of all files in selected folders
        # For now, show what would be processed
        st.success(f"Would process files from {len(st.session_state.selected_folders)} folders")
        st.session_state.selected_folders.clear()


def process_batch_from_tree(max_files):
    """Process documents in batches using the tree structure."""
    # Get files from scan-folders for actual processing
    scan_data = fetch_data("/scan-folders")
    
    if not scan_data:
        st.error("Could not get file list for processing")
        return
    
    # Handle response format
    if isinstance(scan_data, dict) and "unprocessed_files" in scan_data:
        unprocessed_files = scan_data["unprocessed_files"]
    elif isinstance(scan_data, dict) and "data" in scan_data:
        unprocessed_files = scan_data["data"].get("unprocessed_files", [])
    else:
        st.error("Invalid scan data format")
        return
    
    files_to_process = unprocessed_files[:max_files]
    
    if not files_to_process:
        st.info("No documents available for processing")
        return
    
    with st.spinner(f"Processing {len(files_to_process)} documents..."):
        processed = 0
        failed = 0
        
        for file_info in files_to_process:
            try:
                result = api_request("/documents/process", method="POST", json_data={
                    "file_path": file_info["file_path"],
                    "investor_code": file_info["investor_code"]
                })
                if result.get("status") == "success":
                    processed += 1
                else:
                    failed += 1
            except:
                failed += 1
        
        st.success(f"Batch processing complete: {processed} successful, {failed} failed")
        st.rerun()


def toggle_investor_selection(investor_name, files_structure):
    """Toggle selection for all files under an investor."""
    investor_key = f"investor_{investor_name}"
    is_selected = st.session_state.get(investor_key, False)
    
    for fund_name, subfolders in files_structure.get(investor_name, {}).items():
        for subfolder_name, files in subfolders.items():
            for file_info in files:
                if is_selected:
                    st.session_state.selected_files.add(file_info["file_path"])
                else:
                    st.session_state.selected_files.discard(file_info["file_path"])


def toggle_fund_selection(investor_name, fund_name, files_structure):
    """Toggle selection for all files under a fund."""
    fund_key = f"fund_{investor_name}_{fund_name}"
    is_selected = st.session_state.get(fund_key, False)
    
    subfolders = files_structure.get(investor_name, {}).get(fund_name, {})
    for subfolder_name, files in subfolders.items():
        for file_info in files:
            if is_selected:
                st.session_state.selected_files.add(file_info["file_path"])
            else:
                st.session_state.selected_files.discard(file_info["file_path"])


def toggle_subfolder_selection(investor_name, fund_name, subfolder_name, files_structure):
    """Toggle selection for all files under a subfolder."""
    subfolder_key = f"subfolder_{investor_name}_{fund_name}_{subfolder_name}"
    is_selected = st.session_state.get(subfolder_key, False)
    
    files = files_structure.get(investor_name, {}).get(fund_name, {}).get(subfolder_name, [])
    for file_info in files:
        if is_selected:
            st.session_state.selected_files.add(file_info["file_path"])
        else:
            st.session_state.selected_files.discard(file_info["file_path"])


def process_selected_documents():
    """Process selected documents."""
    if not st.session_state.selected_files:
        st.error("No documents selected for processing")
        return
    
    with st.spinner(f"Processing {len(st.session_state.selected_files)} selected documents..."):
        processed = 0
        failed = 0
        
        for file_path in list(st.session_state.selected_files):
            try:
                result = api_request("/documents/process", method="POST", json_data={
                    "file_path": file_path,
                    "investor_code": "auto_detect"
                })
                if result.get("status") == "success":
                    processed += 1
                else:
                    failed += 1
            except:
                failed += 1
        
        st.success(f"Processing complete: {processed} successful, {failed} failed")
        st.session_state.selected_files.clear()
        st.rerun()


def process_batch_documents(max_files):
    """Process documents in batches."""
    scan_data = fetch_data("/scan-folders")
    if not scan_data or scan_data.get("status") != "success":
        st.error("Could not get document list for batch processing")
        return
    
    unprocessed_files = scan_data.get("data", {}).get("unprocessed_files", [])
    files_to_process = unprocessed_files[:max_files]
    
    if not files_to_process:
        st.info("No documents available for processing")
        return
    
    with st.spinner(f"Processing {len(files_to_process)} documents..."):
        processed = 0
        failed = 0
        
        for file_info in files_to_process:
            try:
                result = api_request("/documents/process", method="POST", json_data={
                    "file_path": file_info["file_path"],
                    "investor_code": file_info["investor_code"]
                })
                if result.get("status") == "success":
                    processed += 1
                else:
                    failed += 1
            except:
                failed += 1
        
        st.success(f"Batch processing complete: {processed} successful, {failed} failed")
        st.rerun()


def render_processing_status_view():
    """Render processing status and results."""
    st.subheader("📊 Processing Status & Results")
    
    # Get document tracker stats
    tracker_stats = fetch_data("/document-tracker/stats")
    
    if tracker_stats:
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("📄 Total Tracked", tracker_stats.get("total", 0))
        with col2:
            st.metric("🔍 Discovered", tracker_stats.get("discovered", 0))
        with col3:
            st.metric("⚙️ Processing", tracker_stats.get("processing", 0))
        with col4:
            st.metric("✅ Completed", tracker_stats.get("completed", 0))
        with col5:
            st.metric("❌ Failed", tracker_stats.get("failed", 0))
    
    st.markdown("---")
    
    # Show PE extraction results
    st.subheader("💰 Financial Data Extracted")
    
    pe_docs = fetch_data("/pe/documents") or []
    
    # Get actual PE document count from database
    pe_count = len([doc for doc in pe_docs if doc.get("doc_id")])
    
    if pe_count > 0:
        st.success(f"📊 {pe_count} documents with extracted financial data")
        
        # Show sample extracted data
        df_data = []
        for doc in pe_docs[:20]:  # Show first 20
            df_data.append({
                "Document": doc.get("file_name", "Unknown")[:50],
                "Type": doc.get("doc_type", "Unknown"),
                "Fund": doc.get("fund_id", "Unknown")[:20] if doc.get("fund_id") else "Unknown",
                "Investor": doc.get("investor_id", "Unknown")[:20] if doc.get("investor_id") else "Unknown",
                "Status": doc.get("processing_status", "Unknown")
            })
        
        if df_data:
            import pandas as pd
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True)
    else:
        st.info("No financial data extracted yet. Start processing documents to see results here.")


def render_system_controls_view():
    """Render system controls and file watcher."""
    st.subheader("⚙️ System Controls")
    
    # File Watcher Controls
    file_watcher_status = fetch_data("/file-watcher/status")
    is_running = file_watcher_status.get("status") == "running" if file_watcher_status else False
    
    st.markdown("#### 👁️ File Watcher")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if is_running:
            st.success("🟢 File Watcher Active - Monitoring investor folders")
            if st.button("⏸️ Stop File Watcher", type="secondary"):
                result = api_request("/file-watcher/stop", method="POST")
                if result.get("status") == "success":
                    st.success("File watcher stopped")
                    st.rerun()
        else:
            st.warning("🔴 File Watcher Inactive")
            if st.button("▶️ Start File Watcher", type="primary"):
                result = api_request("/file-watcher/start", method="POST", json_data={})
                if result.get("status") == "success":
                    st.success("File watcher started")
                    st.rerun()
                else:
                    st.error(f"Failed to start file watcher: {result.get('error', 'Unknown error')}")
    
    with col2:
        if st.button("🔄 Refresh File Scan", use_container_width=True):
            st.rerun()
    
    # System Information
    st.markdown("---")
    st.markdown("#### 📊 System Information")
    
    # Show folder paths and file counts
    if file_watcher_status:
        folders = file_watcher_status.get("folders", [])
        
        for folder_info in folders:
            name = folder_info.get("name", "Unknown")
            path = folder_info.get("path", "Unknown")
            exists = folder_info.get("exists", False)
            
            status_icon = "✅" if exists else "❌"
            st.markdown(f"**{status_icon} {name}**")
            st.code(path, language=None)
            
            if exists:
                file_counts = folder_info.get("file_counts", {})
                if file_counts:
                    count_text = ", ".join([f"{ext}: {count}" for ext, count in file_counts.items()])
                    st.caption(f"Files: {count_text}")
            
            st.markdown("")


def render_funds():
    """Render the funds page."""
    st.header("🏦 Fund Management")
    
    # Fetch funds
    funds = fetch_data("/funds")
    
    if funds:
        df = pd.DataFrame(funds)
        
        st.subheader(f"Funds ({len(funds)})")
        
        # Fund overview
        if not df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Asset class distribution
                if "asset_class" in df.columns:
                    asset_class_counts = df["asset_class"].value_counts()
                    fig = px.pie(
                        values=asset_class_counts.values,
                        names=asset_class_counts.index,
                        title="Asset Class Distribution"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Vintage year distribution
                if "vintage_year" in df.columns:
                    vintage_counts = df["vintage_year"].value_counts().sort_index()
                    fig = px.bar(
                        x=vintage_counts.index,
                        y=vintage_counts.values,
                        title="Funds by Vintage Year"
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        # Fund table
        st.subheader("Fund Details")
        display_cols = [
            "name", "code", "asset_class", "vintage_year", 
            "fund_size", "currency", "investor_name", "document_count"
        ]
        available_cols = [col for col in display_cols if col in df.columns]
        
        if available_cols:
            st.dataframe(
                df[available_cols],
                use_container_width=True,
                hide_index=True
            )
        
        # Fund selection for detailed view
        st.subheader("Fund Performance")
        fund_options = df["name"].tolist() if not df.empty else []
        
        if fund_options:
            selected_fund = st.selectbox("Select Fund for Details", fund_options)
            
            if selected_fund:
                fund_info = df[df["name"] == selected_fund].iloc[0]
                fund_id = fund_info["id"]
                
                # Fetch financial data
                financial_data = fetch_data(f"/financial-data/{fund_id}")
                
                if financial_data:
                    fin_df = pd.DataFrame(financial_data)
                    
                    if not fin_df.empty:
                        # Convert date column
                        fin_df["reporting_date"] = pd.to_datetime(fin_df["reporting_date"])
                        fin_df = fin_df.sort_values("reporting_date")
                        
                        # Performance charts
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # NAV trend
                            if "nav" in fin_df.columns and fin_df["nav"].notna().any():
                                fig = px.line(
                                    fin_df,
                                    x="reporting_date",
                                    y="nav",
                                    title="NAV Trend",
                                    labels={"nav": "NAV (€)", "reporting_date": "Date"}
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            # IRR trend
                            if "irr" in fin_df.columns and fin_df["irr"].notna().any():
                                fig = px.line(
                                    fin_df,
                                    x="reporting_date",
                                    y="irr",
                                    title="IRR Trend",
                                    labels={"irr": "IRR (%)", "reporting_date": "Date"}
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        
                        # Data table
                        st.subheader("Financial Data")
                        display_cols = [
                            "reporting_date", "period_type", "nav", "total_value",
                            "irr", "moic", "committed_capital", "drawn_capital"
                        ]
                        available_cols = [col for col in display_cols if col in fin_df.columns]
                        
                        if available_cols:
                            display_fin_df = fin_df[available_cols].copy()
                            display_fin_df["reporting_date"] = display_fin_df["reporting_date"].dt.strftime("%Y-%m-%d")
                            st.dataframe(display_fin_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No financial data available for this fund.")
    else:
        st.info("No funds found.")


def render_analytics():
    """Render the analytics page."""
    st.header("📈 Analytics & Insights")
    
    # Fetch all funds and financial data for analysis
    funds = fetch_data("/funds")
    
    if not funds:
        st.info("No data available for analytics.")
        return
    
    st.subheader("Portfolio Overview")
    
    # Aggregate analytics across all funds
    all_financial_data = []
    
    for fund in funds:
        fund_id = fund["id"]
        financial_data = fetch_data(f"/financial-data/{fund_id}")
        
        if financial_data:
            for record in financial_data:
                record["fund_name"] = fund["name"]
                record["fund_code"] = fund["code"]
                record["asset_class"] = fund["asset_class"]
                record["investor_code"] = fund["investor_code"]
                all_financial_data.append(record)
    
    if all_financial_data:
        df = pd.DataFrame(all_financial_data)
        df["reporting_date"] = pd.to_datetime(df["reporting_date"])
        
        # Portfolio performance over time
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Total Portfolio Value")
            if "total_value" in df.columns:
                portfolio_value = df.groupby("reporting_date")["total_value"].sum().reset_index()
                fig = px.line(
                    portfolio_value,
                    x="reporting_date",
                    y="total_value",
                    title="Total Portfolio Value Over Time"
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Average IRR by Asset Class")
            if "irr" in df.columns and "asset_class" in df.columns:
                avg_irr = df.groupby("asset_class")["irr"].mean().reset_index()
                fig = px.bar(
                    avg_irr,
                    x="asset_class",
                    y="irr",
                    title="Average IRR by Asset Class"
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Performance comparison
        st.subheader("Fund Performance Comparison")
        
        if "irr" in df.columns and "moic" in df.columns:
            # Get latest data for each fund
            latest_data = df.loc[df.groupby("fund_code")["reporting_date"].idxmax()]
            
            fig = px.scatter(
                latest_data,
                x="irr",
                y="moic",
                color="asset_class",
                size="total_value",
                hover_data=["fund_name"],
                title="IRR vs MOIC (Latest Data)",
                labels={"irr": "IRR (%)", "moic": "MOIC (x)"}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Top performers
        st.subheader("Top Performing Funds")
        
        if "irr" in df.columns:
            top_funds = df.loc[df.groupby("fund_code")["reporting_date"].idxmax()]
            top_funds = top_funds.sort_values("irr", ascending=False).head(10)
            
            display_cols = ["fund_name", "asset_class", "irr", "moic", "total_value", "reporting_date"]
            available_cols = [col for col in display_cols if col in top_funds.columns]
            
            if available_cols:
                display_df = top_funds[available_cols].copy()
                display_df["reporting_date"] = display_df["reporting_date"].dt.strftime("%Y-%m-%d")
                st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No financial data available for analytics.")


def main():
    """Main application function."""
    render_header()
    
    # Show API connection status
    show_api_status()
    
    # Render sidebar and get selected page
    page = render_sidebar()
    
    # Render selected page
    if page == "Dashboard":
        render_dashboard()
    elif page == "Chat Interface":
        render_chat_interface()
    elif page == "Documents":
        render_documents()
    elif page == "Funds":
        render_funds()
    elif page == "Analytics":
        render_analytics()
    elif page == "PE — Portfolio":
        render_pe_portfolio()
    elif page == "PE — Capital Accounts":
        render_pe_capital_accounts()
    elif page == "PE — Documents & RAG":
        render_pe_documents_rag()
    elif page == "PE — Reconciliation":
        render_pe_reconciliation()


def render_pe_capital_accounts():
    """Render PE Capital Accounts page with time series and extraction review."""
    st.header("💰 PE — Capital Accounts")
    
    # Tabs for different features
    tab1, tab2, tab3, tab4 = st.tabs(["Time Series", "Extraction Review", "Reconciliation", "Manual Override"])
    
    with tab1:
        st.subheader("Capital Account Time Series")
        
        # Fund selection
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Get available funds
            funds_response = api_request("/funds")
            if funds_response["status"] == "success":
                funds = funds_response["data"]
                fund_options = {f["name"]: f["id"] for f in funds}
                selected_fund_name = st.selectbox("Select Fund", list(fund_options.keys()))
                fund_id = fund_options.get(selected_fund_name)
            else:
                st.error("Could not load funds")
                fund_id = st.text_input("Enter Fund ID")
        
        with col2:
            investor_id = st.text_input("Investor ID (optional)")
        
        with col3:
            include_forecast = st.checkbox("Include Forecast", value=False)
        
        if fund_id and st.button("Load Capital Account Data"):
            # Fetch capital account series
            params = {"include_forecast": include_forecast}
            if investor_id:
                params["investor_id"] = investor_id
            
            ca_response = api_request(f"/pe/capital-account-series/{fund_id}", params=params)
            
            if ca_response["status"] == "success":
                data = ca_response["data"]
                series = data.get("series", [])
                
                if series:
                    # Convert to DataFrame
                    df = pd.DataFrame(series)
                    df['as_of_date'] = pd.to_datetime(df['as_of_date'])
                    
                    # Display key metrics
                    latest = series[-1]
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Latest NAV", f"${latest['ending_balance']:,.0f}")
                    with col2:
                        st.metric("NAV Change", f"${latest['nav_change']:,.0f}", 
                                f"{latest['nav_change_pct']:.1f}%")
                    with col3:
                        st.metric("Unfunded", f"${latest['unfunded_commitment']:,.0f}")
                    with col4:
                        st.metric("Contribution Pace", f"{latest['contribution_pace']:.1f}%")
                    
                    # NAV Chart
                    fig_nav = go.Figure()
                    
                    # Add NAV line
                    fig_nav.add_trace(go.Scatter(
                        x=df['as_of_date'],
                        y=df['ending_balance'],
                        mode='lines+markers',
                        name='NAV',
                        line=dict(color='blue', width=2)
                    ))
                    
                    # Add forecast line if present
                    forecast_df = df[df.get('is_forecast', False) == True]
                    if not forecast_df.empty:
                        fig_nav.add_trace(go.Scatter(
                            x=forecast_df['as_of_date'],
                            y=forecast_df['ending_balance'],
                            mode='lines+markers',
                            name='Forecast',
                            line=dict(color='lightblue', width=2, dash='dash')
                        ))
                    
                    fig_nav.update_layout(
                        title="NAV Over Time",
                        xaxis_title="Date",
                        yaxis_title="NAV ($)",
                        height=400
                    )
                    
                    st.plotly_chart(fig_nav, use_container_width=True)
                    
                    # Activity Chart
                    fig_activity = go.Figure()
                    
                    fig_activity.add_trace(go.Bar(
                        x=df['as_of_date'],
                        y=df['contributions_period'],
                        name='Contributions',
                        marker_color='green'
                    ))
                    
                    fig_activity.add_trace(go.Bar(
                        x=df['as_of_date'],
                        y=-df['distributions_period'],
                        name='Distributions',
                        marker_color='red'
                    ))
                    
                    fig_activity.update_layout(
                        title="Capital Activity",
                        xaxis_title="Date",
                        yaxis_title="Amount ($)",
                        barmode='relative',
                        height=400
                    )
                    
                    st.plotly_chart(fig_activity, use_container_width=True)
                    
                    # Data table
                    st.subheader("Detailed Data")
                    display_df = df[['as_of_date', 'period_label', 'beginning_balance', 
                                   'contributions_period', 'distributions_period', 
                                   'ending_balance', 'unfunded_commitment']]
                    st.dataframe(display_df, use_container_width=True)
                    
                else:
                    st.warning("No capital account data found for this fund")
            else:
                st.error(f"Error: {ca_response.get('error', 'Unknown error')}")
    
    with tab2:
        st.subheader("Extraction Review")
        
        # Document selection
        doc_id = st.text_input("Document ID")
        
        if doc_id and st.button("Load Extraction Audit"):
            audit_response = api_request(f"/pe/extraction-audit/{doc_id}")
            
            if audit_response["status"] == "success":
                data = audit_response["data"]
                audits = data.get("audits", [])
                
                st.write(f"**Document ID:** {doc_id}")
                st.write(f"**Audit Entries:** {data.get('audit_count', 0)}")
                
                if audits:
                    # Group by confidence
                    high_conf = [a for a in audits if a['confidence_score'] >= 0.8]
                    med_conf = [a for a in audits if 0.5 <= a['confidence_score'] < 0.8]
                    low_conf = [a for a in audits if a['confidence_score'] < 0.5]
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("High Confidence", len(high_conf), "≥ 80%")
                    with col2:
                        st.metric("Medium Confidence", len(med_conf), "50-80%")
                    with col3:
                        st.metric("Low Confidence", len(low_conf), "< 50%")
                    
                    # Display audit details
                    for audit in audits:
                        confidence = audit['confidence_score']
                        if confidence >= 0.8:
                            conf_color = "🟢"
                        elif confidence >= 0.5:
                            conf_color = "🟡"
                        else:
                            conf_color = "🔴"
                        
                        with st.expander(f"{conf_color} {audit['field_name']} - {confidence:.0%}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Value:** {audit['extracted_value']}")
                                st.write(f"**Method:** {audit['extraction_method']}")
                            with col2:
                                st.write(f"**Status:** {audit['validation_status']}")
                                if audit.get('manual_override'):
                                    st.write(f"**Override:** {audit['manual_override']}")
                                    st.write(f"**Reason:** {audit['override_reason']}")
                else:
                    st.info("No extraction audit found for this document")
            else:
                st.error(f"Error: {audit_response.get('error', 'Unknown error')}")
    
    with tab3:
        st.subheader("Reconciliation Status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fund_id = st.text_input("Fund ID", key="recon_fund")
        
        with col2:
            as_of_date = st.date_input("As of Date")
        
        recon_types = st.multiselect(
            "Reconciliation Types",
            ["nav", "cashflow", "performance", "commitment"],
            default=["nav", "cashflow", "performance", "commitment"]
        )
        
        if fund_id and st.button("Run Reconciliation"):
            recon_data = {
                "as_of_date": as_of_date.isoformat(),
                "reconciliation_types": recon_types
            }
            
            recon_response = api_request(f"/pe/reconcile/{fund_id}", method="POST", json_data=recon_data)
            
            if recon_response["status"] == "success":
                result = recon_response["data"]
                
                st.success(f"Reconciliation scheduled! Task ID: {result['task_id']}")
                st.json(result)
            else:
                st.error(f"Error: {recon_response.get('error', 'Unknown error')}")
    
    with tab4:
        st.subheader("Manual Override")
        
        doc_id = st.text_input("Document ID", key="override_doc")
        
        st.write("Enter field overrides:")
        
        # Common fields
        col1, col2 = st.columns(2)
        
        with col1:
            ending_balance = st.number_input("Ending Balance", value=0.0, key="override_ending")
            contributions = st.number_input("Contributions", value=0.0, key="override_contrib")
            distributions = st.number_input("Distributions", value=0.0, key="override_dist")
        
        with col2:
            beginning_balance = st.number_input("Beginning Balance", value=0.0, key="override_begin")
            total_commitment = st.number_input("Total Commitment", value=0.0, key="override_commit")
            unfunded = st.number_input("Unfunded Commitment", value=0.0, key="override_unfunded")
        
        reviewer_id = st.text_input("Reviewer Email")
        override_reason = st.text_area("Override Reason")
        
        if doc_id and reviewer_id and override_reason and st.button("Apply Overrides"):
            # Build overrides dict (only non-zero values)
            overrides = {}
            if ending_balance > 0:
                overrides["ending_balance"] = ending_balance
            if beginning_balance > 0:
                overrides["beginning_balance"] = beginning_balance
            if contributions > 0:
                overrides["contributions_period"] = contributions
            if distributions > 0:
                overrides["distributions_period"] = distributions
            if total_commitment > 0:
                overrides["total_commitment"] = total_commitment
            if unfunded > 0:
                overrides["unfunded_commitment"] = unfunded
            
            if overrides:
                override_data = {
                    "field_overrides": overrides,
                    "reviewer_id": reviewer_id,
                    "override_reason": override_reason
                }
                
                override_response = api_request(
                    f"/pe/manual-override/{doc_id}", 
                    method="POST", 
                    json_data=override_data
                )
                
                if override_response["status"] == "success":
                    st.success("Overrides applied successfully!")
                    st.json(override_response["data"])
                else:
                    st.error(f"Error: {override_response.get('error', 'Unknown error')}")
            else:
                st.warning("Please enter at least one override value")


def render_pe_portfolio():
    """Render PE Portfolio page with NAV bridge, flows, and KPIs."""
    st.header("🏛️ PE — Portfolio")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        org_code = st.selectbox("Organization", ["brainweb", "pecunalta", "all"], index=2)
    
    with col2:
        investor_code = st.selectbox("Investor", ["brainweb", "pecunalta", "all"], index=2)
    
    with col3:
        # Get available funds
        try:
            funds_response = requests.get(f"{API_BASE_URL}/pe/documents")
            funds_data = funds_response.json() if funds_response.status_code == 200 else []
            fund_ids = list(set([doc.get('fund_id') for doc in funds_data if doc.get('fund_id')]))
            fund_ids.insert(0, "all")
            selected_fund = st.selectbox("Fund", fund_ids)
        except Exception:
            selected_fund = st.selectbox("Fund", ["all"])
    
    with col4:
        currency = st.selectbox("Currency", ["EUR", "USD", "GBP"])
    
    # Date range
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now().date().replace(month=1, day=1))
    with col2:
        end_date = st.date_input("End Date", value=datetime.now().date())
    
    if selected_fund and selected_fund != "all":
        # KPI Tiles
        st.subheader("📈 Key Performance Indicators")
        
        try:
            kpi_response = requests.get(f"{API_BASE_URL}/pe/kpis", params={
                "fund_id": selected_fund,
                "as_of_date": end_date.isoformat()
            })
            
            if kpi_response.status_code == 200:
                kpis = kpi_response.json()
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("TVPI", f"{kpis.get('tvpi', 0):.2f}x", 
                             help="Total Value to Paid-in Capital")
                
                with col2:
                    st.metric("DPI", f"{kpis.get('dpi', 0):.2f}x",
                             help="Distributions to Paid-in Capital")
                
                with col3:
                    st.metric("RVPI", f"{kpis.get('rvpi', 0):.2f}x",
                             help="Residual Value to Paid-in Capital")
                
                with col4:
                    current_nav = kpis.get('current_nav', 0)
                    st.metric("Current NAV", f"€{current_nav:,.0f}")
        
        except Exception as e:
            st.error(f"Error loading KPIs: {e}")
        
        # NAV Bridge
        st.subheader("💰 Monthly NAV Bridge")
        
        try:
            bridge_response = requests.get(f"{API_BASE_URL}/pe/nav-bridge", params={
                "fund_id": selected_fund,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            })
            
            if bridge_response.status_code == 200:
                bridge_data = bridge_response.json()
                periods = bridge_data.get('periods', [])
                
                if periods:
                    df = pd.DataFrame(periods)
                    df['period_end'] = pd.to_datetime(df['period_end'])
                    
                    # Display table
                    st.dataframe(df, use_container_width=True)
                    
                    # Chart
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df['period_end'],
                        y=df['nav_end'],
                        mode='lines+markers',
                        name='NAV',
                        line=dict(color='#1f77b4', width=3)
                    ))
                    
                    fig.update_layout(
                        title="NAV Progression",
                        xaxis_title="Period",
                        yaxis_title="NAV (€)",
                        height=400
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No NAV bridge data available")
            else:
                st.error("Error loading NAV bridge data")
        
        except Exception as e:
            st.error(f"Error loading NAV bridge: {e}")
        
        # Cashflows
        st.subheader("💸 Cashflows")
        
        try:
            cf_response = requests.get(f"{API_BASE_URL}/pe/cashflows", params={
                "fund_id": selected_fund,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            })
            
            if cf_response.status_code == 200:
                cashflows = cf_response.json()
                
                if cashflows:
                    df_cf = pd.DataFrame(cashflows)
                    df_cf['flow_date'] = pd.to_datetime(df_cf['flow_date'])
                    
                    # Summary by type
                    col1, col2, col3 = st.columns(3)
                    
                    calls = df_cf[df_cf['flow_type'] == 'CALL']['amount'].sum()
                    dists = df_cf[df_cf['flow_type'] == 'DIST']['amount'].sum() 
                    fees = df_cf[df_cf['flow_type'] == 'FEE']['amount'].sum()
                    
                    with col1:
                        st.metric("Total Calls", f"€{calls:,.0f}")
                    with col2:
                        st.metric("Total Distributions", f"€{dists:,.0f}")
                    with col3:
                        st.metric("Total Fees", f"€{fees:,.0f}")
                    
                    # Detailed table
                    display_cf = df_cf[['flow_date', 'flow_type', 'amount', 'currency']].copy()
                    display_cf['flow_date'] = display_cf['flow_date'].dt.strftime('%Y-%m-%d')
                    st.dataframe(display_cf, use_container_width=True)
                else:
                    st.info("No cashflow data available")
        
        except Exception as e:
            st.error(f"Error loading cashflows: {e}")
    
    else:
        st.info("Please select a specific fund to view portfolio details")

def render_pe_documents_rag():
    """Render PE Documents & RAG page."""
    st.header("📄 PE — Documents & RAG")
    
    # Document list
    st.subheader("📋 Document Library")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        doc_type_filter = st.selectbox("Document Type", 
                                      ["all", "QR", "CAS", "CALL", "DIST", "LPA", "PPM", "SUBSCRIPTION"])
    
    with col2:
        # Get available funds for filter
        try:
            funds_response = requests.get(f"{API_BASE_URL}/pe/documents")
            funds_data = funds_response.json() if funds_response.status_code == 200 else []
            fund_ids = list(set([doc.get('fund_id') for doc in funds_data if doc.get('fund_id')]))
            fund_ids.insert(0, "all")
            fund_filter = st.selectbox("Fund", fund_ids)
        except Exception:
            fund_filter = st.selectbox("Fund", ["all"])
    
    with col3:
        investor_filter = st.selectbox("Investor", ["all", "brainweb", "pecunalta"])
    
    # Load documents
    try:
        params = {}
        if doc_type_filter != "all":
            params["doc_type"] = doc_type_filter
        if fund_filter != "all":
            params["fund_id"] = fund_filter
        if investor_filter != "all":
            params["investor_code"] = investor_filter
        
        docs_response = requests.get(f"{API_BASE_URL}/pe/documents", params=params)
        
        if docs_response.status_code == 200:
            documents = docs_response.json()
            
            if documents:
                # Convert to DataFrame for display
                df_docs = pd.DataFrame(documents)
                
                # Format dates
                if 'created_at' in df_docs.columns:
                    df_docs['created_at'] = pd.to_datetime(df_docs['created_at']).dt.strftime('%Y-%m-%d %H:%M')
                
                # Display columns
                display_cols = ['file_name', 'doc_type', 'investor_code', 'created_at']
                available_cols = [col for col in display_cols if col in df_docs.columns]
                
                if available_cols:
                    st.dataframe(df_docs[available_cols], use_container_width=True)
            else:
                st.info("No documents found matching filters")
        else:
            st.error("Error loading documents")
    
    except Exception as e:
        st.error(f"Error loading documents: {e}")
    
    st.markdown("---")
    
    # RAG Interface
    st.subheader("🤖 Document Search & Chat")
    
    # RAG query interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input("Ask a question about your PE documents:", 
                             placeholder="e.g., What was the NAV for Fund ABC as of December 2023?")
    
    with col2:
        search_button = st.button("Search", type="primary")
    
    # Advanced filters for RAG
    with st.expander("Advanced Search Filters"):
        rag_col1, rag_col2, rag_col3 = st.columns(3)
        
        with rag_col1:
            rag_fund_filter = st.selectbox("Limit to Fund", fund_ids if 'fund_ids' in locals() else ["all"], key="rag_fund")
        
        with rag_col2:
            rag_doc_type = st.selectbox("Document Type", 
                                       ["all", "QR", "CAS", "CALL", "DIST", "LPA", "PPM"], key="rag_doc_type")
        
        with rag_col3:
            top_k = st.slider("Max Results", 1, 20, 5)
    
    # Execute RAG query
    if search_button and query:
        with st.spinner("Searching documents..."):
            try:
                rag_payload = {
                    "query": query,
                    "top_k": top_k
                }
                
                if rag_fund_filter != "all":
                    rag_payload["fund_id"] = rag_fund_filter
                
                if rag_doc_type != "all":
                    rag_payload["doc_type"] = rag_doc_type
                
                rag_response = requests.post(f"{API_BASE_URL}/pe/rag/query", json=rag_payload)
                
                if rag_response.status_code == 200:
                    rag_result = rag_response.json()
                    
                    # Display answer
                    st.markdown("### 💡 Answer")
                    st.markdown(rag_result.get('answer', 'No answer generated'))
                    
                    # Display citations
                    citations = rag_result.get('citations', [])
                    if citations:
                        st.markdown("### 📚 Sources")
                        
                        for i, citation in enumerate(citations, 1):
                            with st.expander(f"Source {i}: {citation.get('doc_id', 'Unknown')} (Page {citation.get('page_no', 1)})"):
                                st.markdown(f"**Document Type:** {citation.get('doc_type', 'Unknown')}")
                                st.markdown(f"**Relevance Score:** {citation.get('relevance_score', 0):.2f}")
                                st.markdown(f"**Snippet:**")
                                st.text(citation.get('snippet', 'No snippet available'))
                else:
                    st.error("Error executing search query")
            
            except Exception as e:
                st.error(f"Error during search: {e}")
    
    # Processing status
    st.markdown("---")
    st.subheader("⚙️ Processing Status")
    
    try:
        jobs_response = requests.get(f"{API_BASE_URL}/pe/jobs")
        
        if jobs_response.status_code == 200:
            jobs_data = jobs_response.json()
            stats = jobs_data.get('stats', {})
            pending_jobs = jobs_data.get('pending_jobs', [])
            
            # Stats
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Files", stats.get('total_files', 0))
            with col2:
                st.metric("Processed", stats.get('processed', 0))
            with col3:
                st.metric("Queued", stats.get('queued', 0))
            with col4:
                st.metric("Errors", stats.get('errors', 0))
            
            # Pending jobs
            if pending_jobs:
                st.markdown("**Pending Jobs:**")
                for job in pending_jobs:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.text(f"{job['file_name']} ({job['status']})")
                    
                    with col2:
                        if job['status'] == 'ERROR':
                            if st.button("Retry", key=f"retry_{job['job_id']}"):
                                try:
                                    retry_response = requests.post(f"{API_BASE_URL}/pe/retry-job/{job['job_id']}")
                                    if retry_response.status_code == 200:
                                        st.success("Job queued for retry")
                                        st.rerun()
                                    else:
                                        st.error("Error retrying job")
                                except Exception as e:
                                    st.error(f"Error: {e}")
                    
                    with col3:
                        if job['status'] == 'QUEUED':
                            st.text("⏳ Queued")
                        elif job['status'] == 'ERROR':
                            st.text("❌ Error")
            else:
                st.success("✅ All jobs completed successfully")
    
    except Exception as e:
        st.error(f"Error loading job status: {e}")


def render_pe_reconciliation():
    """Render PE Reconciliation page using OpenAI Agents."""
    st.header("🔍 PE — Financial Reconciliation")
    
    st.markdown("""
    This advanced reconciliation system uses OpenAI's agents to perform comprehensive financial analysis,
    ensuring data accuracy, completeness, and consistency across all sources.
    """)
    
    # Fund selection
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Get available funds
        try:
            funds_response = requests.get(f"{API_BASE_URL}/funds")
            if funds_response.status_code == 200:
                funds = funds_response.json()
                fund_options = {f"{f['name']} ({f['identifier']})": f['id'] for f in funds}
                
                selected_fund_display = st.selectbox(
                    "Select Fund for Reconciliation",
                    options=list(fund_options.keys()),
                    help="Select a fund to perform comprehensive reconciliation"
                )
                
                selected_fund_id = fund_options.get(selected_fund_display)
            else:
                st.error("Unable to fetch funds")
                return
        except Exception as e:
            st.error(f"Error fetching funds: {e}")
            return
    
    with col2:
        as_of_date = st.date_input(
            "As of Date",
            value=datetime.now().date(),
            help="Reconciliation date"
        )
    
    # Reconciliation scope
    st.subheader("🎯 Reconciliation Scope")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        check_nav = st.checkbox("NAV Reconciliation", value=True)
    with col2:
        check_cashflows = st.checkbox("Cashflow Analysis", value=True)
    with col3:
        check_performance = st.checkbox("Performance Metrics", value=True)
    with col4:
        check_capital = st.checkbox("Capital Accounts", value=True)
    
    # Build scope list
    reconciliation_scope = []
    if check_nav:
        reconciliation_scope.append("nav")
    if check_cashflows:
        reconciliation_scope.append("cashflows")
    if check_performance:
        reconciliation_scope.append("performance")
    if check_capital:
        reconciliation_scope.append("capital_accounts")
    
    # Run reconciliation button
    if st.button("🚀 Run Reconciliation", type="primary", use_container_width=True):
        if not selected_fund_id:
            st.error("Please select a fund")
            return
        
        if not reconciliation_scope:
            st.error("Please select at least one reconciliation type")
            return
        
        with st.spinner("🤖 AI Agent analyzing data across all sources..."):
            try:
                # Call reconciliation API
                reconciliation_payload = {
                    "fund_id": selected_fund_id,
                    "as_of_date": as_of_date.isoformat(),
                    "reconciliation_scope": reconciliation_scope
                }
                
                response = requests.post(
                    f"{API_BASE_URL}/pe/reconcile",
                    json=reconciliation_payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Store result in session state
                    st.session_state['latest_reconciliation'] = result
                    
                    # Display results
                    st.success(f"✅ Reconciliation completed with status: {result['status']}")
                    
                    # Summary metrics
                    summary = result.get('summary', {})
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total Findings", summary.get('total_findings', 0))
                    with col2:
                        st.metric("Critical Issues", summary.get('critical_issues', 0))
                    with col3:
                        st.metric("High Priority", summary.get('high_priority', 0))
                    with col4:
                        st.metric("Overall Status", result['status'])
                    
                    # Findings by severity
                    findings = result.get('findings', {})
                    
                    if findings.get('critical'):
                        st.error("### 🚨 Critical Issues")
                        for finding in findings['critical']:
                            with st.expander(f"❌ {finding.get('type', 'Issue')} - {finding.get('description', '')}", expanded=True):
                                st.write(f"**Severity:** {finding.get('severity', 'CRITICAL')}")
                                st.write(f"**Description:** {finding.get('description', '')}")
                                
                                if finding.get('values'):
                                    st.write("**Values:**")
                                    st.json(finding['values'])
                                
                                if finding.get('recommendations'):
                                    st.write("**Recommendations:**")
                                    for rec in finding['recommendations']:
                                        st.write(f"• {rec}")
                    
                    if findings.get('high'):
                        st.warning("### ⚠️ High Priority Issues")
                        for finding in findings['high']:
                            with st.expander(f"⚠️ {finding.get('type', 'Issue')} - {finding.get('description', '')}"):
                                st.write(f"**Severity:** {finding.get('severity', 'HIGH')}")
                                st.write(f"**Description:** {finding.get('description', '')}")
                                
                                if finding.get('values'):
                                    st.write("**Values:**")
                                    st.json(finding['values'])
                                
                                if finding.get('recommendations'):
                                    st.write("**Recommendations:**")
                                    for rec in finding['recommendations']:
                                        st.write(f"• {rec}")
                    
                    # Recommendations
                    if result.get('recommendations'):
                        st.info("### 💡 Key Recommendations")
                        for i, rec in enumerate(result['recommendations'], 1):
                            st.write(f"{i}. {rec}")
                    
                else:
                    st.error(f"Reconciliation failed: {response.text}")
                    
            except Exception as e:
                st.error(f"Error running reconciliation: {e}")
    
    # Reconciliation History
    st.markdown("---")
    st.subheader("📊 Reconciliation History")
    
    # Filter options
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        history_fund_filter = st.selectbox(
            "Filter by Fund",
            options=["All"] + list(fund_options.keys()),
            key="history_fund_filter"
        )
    
    with col2:
        history_status_filter = st.selectbox(
            "Filter by Status",
            options=["All", "PASS", "WARNING", "FAIL", "ERROR"],
            key="history_status_filter"
        )
    
    with col3:
        history_limit = st.number_input(
            "Records",
            min_value=5,
            max_value=100,
            value=20,
            step=5
        )
    
    # Fetch history
    try:
        params = {"limit": history_limit}
        
        if history_fund_filter != "All":
            params["fund_id"] = fund_options.get(history_fund_filter)
        
        if history_status_filter != "All":
            params["status"] = history_status_filter
        
        history_response = requests.get(
            f"{API_BASE_URL}/pe/reconciliation-history",
            params=params
        )
        
        if history_response.status_code == 200:
            history = history_response.json()
            
            if history:
                # Create DataFrame for display
                history_df = pd.DataFrame(history)
                
                # Format dates
                history_df['as_of_date'] = pd.to_datetime(history_df['as_of_date']).dt.strftime('%Y-%m-%d')
                history_df['created_at'] = pd.to_datetime(history_df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
                
                # Display table
                st.dataframe(
                    history_df[['fund_id', 'as_of_date', 'status', 'findings_count', 'critical_count', 'created_at']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # View details button for each row
                for idx, row in history_df.iterrows():
                    if st.button(f"View Details", key=f"view_details_{row['reconciliation_id']}"):
                        # Fetch detailed results
                        detail_response = requests.get(
                            f"{API_BASE_URL}/pe/reconciliation/{row['reconciliation_id']}"
                        )
                        
                        if detail_response.status_code == 200:
                            details = detail_response.json()
                            
                            with st.expander("Reconciliation Details", expanded=True):
                                st.json(details['full_results'])
                        else:
                            st.error("Unable to fetch details")
            else:
                st.info("No reconciliation history found")
                
    except Exception as e:
        st.error(f"Error fetching history: {e}")
    
    # Export functionality
    if st.session_state.get('latest_reconciliation'):
        st.markdown("---")
        st.subheader("📥 Export Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Export as JSON
            json_str = json.dumps(st.session_state['latest_reconciliation'], indent=2)
            st.download_button(
                label="Download JSON Report",
                data=json_str,
                file_name=f"reconciliation_{selected_fund_id}_{as_of_date}.json",
                mime="application/json"
            )
        
        with col2:
            # Export as CSV (summary)
            summary_data = []
            findings = st.session_state['latest_reconciliation'].get('findings', {})
            
            for severity, items in findings.items():
                for item in items:
                    summary_data.append({
                        'Severity': severity.upper(),
                        'Type': item.get('type', ''),
                        'Description': item.get('description', ''),
                        'Recommendation': '; '.join(item.get('recommendations', []))
                    })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                csv = summary_df.to_csv(index=False)
                
                st.download_button(
                    label="Download CSV Summary",
                    data=csv,
                    file_name=f"reconciliation_summary_{selected_fund_id}_{as_of_date}.csv",
                    mime="text/csv"
                )


if __name__ == "__main__":
    main()