"""Streamlit dashboard for FOReporting v2."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:8000"

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
        ["Dashboard", "Chat Interface", "Documents", "Funds", "Analytics"]
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
            icon = "✅" if status in ["connected", "running"] else "❌"
            st.sidebar.text(f"{icon} {service.title()}: {status}")
    except:
        st.sidebar.error("❌ Cannot connect to API")
    
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
    """Render the chat interface."""
    st.header("💬 Financial AI Assistant")
    st.markdown("Ask questions about your financial data and documents.")
    
    # Initialize session state
    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = None
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # Chat input
    user_input = st.text_input(
        "Ask a question:",
        placeholder="e.g., What was the NAV performance for BrainWeb funds in Q3 2023?",
        key="chat_input"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        send_button = st.button("Send", type="primary")
    with col2:
        if st.button("Clear Chat"):
            st.session_state.chat_messages = []
            st.session_state.chat_session_id = None
            st.rerun()
    
    # Send message
    if send_button and user_input:
        with st.spinner("Thinking..."):
            response = send_chat_message(user_input, st.session_state.chat_session_id)
            
            if response:
                # Update session ID
                st.session_state.chat_session_id = response.get("session_id")
                
                # Add messages to history
                st.session_state.chat_messages.append({
                    "type": "user",
                    "content": user_input,
                    "timestamp": datetime.now()
                })
                
                st.session_state.chat_messages.append({
                    "type": "assistant",
                    "content": response.get("response", "Sorry, I couldn't process that."),
                    "timestamp": datetime.now(),
                    "context_docs": response.get("context_documents", 0),
                    "data_points": response.get("financial_data_points", 0)
                })
                
                # Clear input
                st.session_state.chat_input = ""
                st.rerun()
    
    # Display chat history
    if st.session_state.chat_messages:
        st.markdown("---")
        st.subheader("Conversation")
        
        for msg in st.session_state.chat_messages:
            if msg["type"] == "user":
                st.markdown(
                    f'<div class="chat-message user-message"><strong>You:</strong> {msg["content"]}</div>',
                    unsafe_allow_html=True
                )
            else:
                # Assistant message with metadata
                metadata = ""
                if msg.get("context_docs", 0) > 0 or msg.get("data_points", 0) > 0:
                    metadata = f" <small>(📄 {msg.get('context_docs', 0)} docs, 📊 {msg.get('data_points', 0)} data points)</small>"
                
                st.markdown(
                    f'<div class="chat-message assistant-message"><strong>Assistant:</strong>{metadata}<br>{msg["content"]}</div>',
                    unsafe_allow_html=True
                )


def render_documents():
    """Render the documents page."""
    st.header("📄 Document Management")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        investors = fetch_data("/investors")
        investor_options = ["All"] + [inv["code"] for inv in investors] if investors else ["All"]
        selected_investor = st.selectbox("Investor", investor_options)
    
    with col2:
        doc_types = [
            "All", "quarterly_report", "annual_report", "financial_statement",
            "investment_report", "portfolio_summary", "transaction_data", "other"
        ]
        selected_type = st.selectbox("Document Type", doc_types)
    
    with col3:
        limit = st.number_input("Limit", min_value=10, max_value=200, value=50)
    
    # Fetch documents
    params = {"limit": limit}
    if selected_investor != "All":
        params["investor_code"] = selected_investor
    if selected_type != "All":
        params["document_type"] = selected_type
    
    documents = fetch_data("/documents", params)
    
    if documents:
        df = pd.DataFrame(documents)
        
        # Display summary
        st.subheader(f"Documents ({len(documents)})")
        
        # Status overview
        if not df.empty:
            status_counts = df["processing_status"].value_counts()
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Completed", status_counts.get("completed", 0))
            with col2:
                st.metric("Pending", status_counts.get("pending", 0))
            with col3:
                st.metric("Processing", status_counts.get("processing", 0))
            with col4:
                st.metric("Failed", status_counts.get("failed", 0))
        
        # Document table
        if not df.empty:
            # Format data for display
            display_df = df.copy()
            display_df["created_at"] = pd.to_datetime(display_df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
            display_df["confidence_score"] = display_df["confidence_score"].round(2)
            
            # Select columns for display
            display_cols = [
                "filename", "document_type", "confidence_score", 
                "processing_status", "investor_name", "fund_name", "created_at"
            ]
            available_cols = [col for col in display_cols if col in display_df.columns]
            
            st.dataframe(
                display_df[available_cols],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("No documents found.")


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


if __name__ == "__main__":
    main()