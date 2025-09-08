"""Main Streamlit dashboard entry point - modular version."""

import streamlit as st
import logging

from app.frontend.utils.api_client import show_api_status
from app.frontend.utils.state import init_session_state
from app.frontend.pages.overview import render_dashboard, render_dashboard_header
from app.frontend.pages.pe_analysis import render_pe_capital_accounts, render_pe_portfolio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    .stMetric > div {
        background-color: white;
        border: 1px solid #e0e0e0;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)


def render_sidebar():
    """Render the navigation sidebar."""
    st.sidebar.title("📊 FOReporting v2")
    
    # Initialize session state
    init_session_state()
    
    # API status
    show_api_status()
    
    # Main navigation
    page = st.sidebar.selectbox(
        "Select Page",
        [
            "Dashboard", 
            "Chat Interface", 
            "Documents", 
            "Funds", 
            "Analytics", 
            "PE — Portfolio", 
            "PE — Capital Accounts", 
            "PE — Documents & RAG", 
            "PE — Reconciliation"
        ]
    )
    
    st.sidebar.markdown("---")
    
    # System status
    st.sidebar.subheader("System Status")
    render_system_status()
    
    return page


def render_system_status():
    """Render system status in sidebar."""
    try:
        from app.frontend.utils.api_client import fetch_data
        
        health = fetch_data("/health")
        if health and health.get("status") == "healthy":
            st.sidebar.success("✅ System Healthy")
        else:
            st.sidebar.error("❌ System Issues")
        
        services = health.get("services", {}) if health else {}
        for service, status in services.items():
            if service == "file_watcher":
                if status == "running":
                    icon = "✅"
                elif status == "stopped":
                    icon = "⏸️"
                else:
                    icon = "❌"
                st.sidebar.write(f"{icon} File Watcher: {status}")
            else:
                status_icon = "✅" if status == "connected" else "❌"
                st.sidebar.write(f"{status_icon} {service.title()}: {status}")
                
    except Exception as e:
        st.sidebar.error("❌ Cannot connect to API")
        logger.error(f"System status error: {e}")


def main():
    """Main application entry point."""
    # Initialize session state
    init_session_state()
    
    # Render header
    render_dashboard_header()
    
    # Render sidebar and get selected page
    page = render_sidebar()
    
    # Route to appropriate page
    try:
        if page == "Dashboard":
            render_dashboard()
        elif page == "PE — Capital Accounts":
            render_pe_capital_accounts()
        elif page == "PE — Portfolio":
            render_pe_portfolio()
        elif page == "Chat Interface":
            st.header("💬 Chat Interface")
            st.info("Chat interface will be implemented in next module")
        elif page == "Documents":
            st.header("📄 Documents")
            st.info("Document management will be implemented in next module")
        elif page == "Funds":
            st.header("🏦 Funds")
            st.info("Fund management will be implemented in next module")
        elif page == "Analytics":
            st.header("📊 Analytics")
            st.info("Advanced analytics will be implemented in next module")
        elif page == "PE — Documents & RAG":
            st.header("📄 PE Documents & RAG")
            st.info("PE Documents & RAG will be implemented in next module")
        elif page == "PE — Reconciliation":
            st.header("🔄 PE Reconciliation")
            st.info("PE Reconciliation will be implemented in next module")
        else:
            st.error(f"Unknown page: {page}")
            
    except Exception as e:
        st.error(f"Error rendering page '{page}': {str(e)}")
        logger.error(f"Page rendering error for {page}: {e}")


if __name__ == "__main__":
    main()