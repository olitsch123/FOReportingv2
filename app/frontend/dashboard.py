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
        ["Dashboard", "Chat Interface", "Documents", "Funds", "Analytics", "PE — Portfolio", "PE — Documents & RAG"]
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
    elif page == "PE — Portfolio":
        render_pe_portfolio()
    elif page == "PE — Documents & RAG":
        render_pe_documents_rag()


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


if __name__ == "__main__":
    main()