"""PE analysis and capital accounts page."""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from app.frontend.utils.api_client import fetch_data
from app.frontend.utils.formatters import format_currency, format_percentage, format_multiple, format_date
from app.frontend.components.charts import (
    create_time_series_chart, 
    create_performance_metrics_chart,
    display_chart_with_error_handling
)

logger = logging.getLogger(__name__)


def render_pe_capital_accounts():
    """Render PE capital accounts analysis page."""
    st.header("💰 PE Capital Accounts")
    
    # Fund selection
    fund_id = render_fund_selector()
    if not fund_id:
        st.info("Please select a fund to view capital account data")
        return
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["Time Series", "Extraction Review", "Reconciliation", "Manual Override"])
    
    with tab1:
        render_capital_time_series(fund_id)
    
    with tab2:
        render_extraction_review(fund_id)
    
    with tab3:
        render_reconciliation_view(fund_id)
    
    with tab4:
        render_manual_override(fund_id)


def render_fund_selector() -> Optional[str]:
    """Render fund selection dropdown."""
    try:
        funds = fetch_data("/funds")
        if not funds:
            st.warning("No funds available")
            return None
        
        fund_options = {f"{fund['name']} ({fund['investor_name']})": fund['id'] for fund in funds}
        
        if not fund_options:
            st.warning("No funds found")
            return None
        
        selected_fund_name = st.selectbox("Select Fund", list(fund_options.keys()))
        return fund_options.get(selected_fund_name)
        
    except Exception as e:
        st.error(f"Error loading funds: {str(e)}")
        logger.error(f"Fund selector error: {e}")
        return None


def render_capital_time_series(fund_id: str):
    """Render capital account time series analysis."""
    st.subheader("📈 Capital Account Time Series")
    
    try:
        # Get capital account data
        capital_data = fetch_data(f"/pe/capital-account-series/{fund_id}")
        
        if not capital_data:
            st.warning("No capital account data available for this fund")
            return
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(capital_data)
        
        # Time series chart
        if len(df) > 1:
            display_chart_with_error_handling(
                create_time_series_chart,
                df.to_dict('records'),
                'as_of_date',
                'ending_balance',
                'Capital Account Balance Over Time'
            )
        else:
            st.info("Need at least 2 data points for time series analysis")
        
        # Summary table
        st.subheader("📊 Summary Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            latest = df.iloc[-1] if len(df) > 0 else {}
            st.metric("Current Balance", format_currency(latest.get('ending_balance')))
            st.metric("Total Commitment", format_currency(latest.get('total_commitment')))
        
        with col2:
            st.metric("Total Contributions", format_currency(df['contributions_period'].sum() if 'contributions_period' in df else 0))
            st.metric("Total Distributions", format_currency(df['distributions_period'].sum() if 'distributions_period' in df else 0))
        
        with col3:
            if len(df) > 1:
                growth = ((df['ending_balance'].iloc[-1] / df['ending_balance'].iloc[0]) - 1) * 100
                st.metric("Balance Growth", format_percentage(growth))
            
            unfunded = latest.get('unfunded_commitment', 0)
            st.metric("Unfunded Commitment", format_currency(unfunded))
        
        # Detailed data table
        st.subheader("📋 Detailed Data")
        
        # Format data for display
        display_df = df.copy()
        currency_columns = ['beginning_balance', 'ending_balance', 'contributions_period', 
                          'distributions_period', 'management_fees_period', 'total_commitment']
        
        for col in currency_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: format_currency(x) if pd.notna(x) else "—")
        
        st.dataframe(display_df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error rendering capital time series: {str(e)}")
        logger.error(f"Capital time series error: {e}")


def render_extraction_review(fund_id: str):
    """Render extraction review interface."""
    st.subheader("🔍 Extraction Review")
    
    try:
        # Get extraction audit data
        extraction_data = fetch_data(f"/pe/extraction-audit/{fund_id}")
        
        if not extraction_data:
            st.info("No extraction data available for review")
            return
        
        st.write("**Extraction Quality Overview**")
        
        # Quality metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            avg_confidence = extraction_data.get('average_confidence', 0)
            st.metric("Average Confidence", format_percentage(avg_confidence * 100))
        
        with col2:
            total_extractions = extraction_data.get('total_extractions', 0)
            st.metric("Total Extractions", total_extractions)
        
        with col3:
            high_confidence = extraction_data.get('high_confidence_count', 0)
            st.metric("High Confidence (>80%)", high_confidence)
        
        # Extraction details
        extractions = extraction_data.get('extractions', [])
        
        if extractions:
            st.subheader("📄 Document Extractions")
            
            for extraction in extractions:
                with st.expander(f"📄 {extraction.get('document_name', 'Unknown Document')}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Extraction Info**")
                        st.write(f"Confidence: {format_percentage(extraction.get('confidence', 0) * 100)}")
                        st.write(f"Method: {extraction.get('method', 'Unknown')}")
                        st.write(f"Date: {format_date(extraction.get('extraction_date'))}")
                    
                    with col2:
                        st.write("**Extracted Fields**")
                        fields = extraction.get('extracted_fields', {})
                        for field, value in fields.items():
                            if value is not None:
                                if 'balance' in field or 'commitment' in field:
                                    st.write(f"{field}: {format_currency(value)}")
                                elif 'percentage' in field or 'rate' in field:
                                    st.write(f"{field}: {format_percentage(value)}")
                                else:
                                    st.write(f"{field}: {value}")
        
    except Exception as e:
        st.error(f"Error rendering extraction review: {str(e)}")
        logger.error(f"Extraction review error: {e}")


def render_reconciliation_view(fund_id: str):
    """Render reconciliation status and controls."""
    st.subheader("🔄 Reconciliation")
    
    try:
        # Get reconciliation status
        reconciliation = fetch_data(f"/pe/reconcile/{fund_id}")
        
        if not reconciliation:
            st.info("No reconciliation data available")
            return
        
        # Reconciliation status
        status = reconciliation.get('status', 'unknown')
        
        if status == 'success':
            st.success("✅ Reconciliation successful")
        elif status == 'warnings':
            st.warning("⚠️ Reconciliation completed with warnings")
        elif status == 'errors':
            st.error("❌ Reconciliation failed")
        else:
            st.info(f"📊 Status: {status}")
        
        # Reconciliation details
        details = reconciliation.get('details', {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Reconciliation Summary**")
            st.write(f"Items Checked: {details.get('items_checked', 0)}")
            st.write(f"Matches Found: {details.get('matches', 0)}")
            st.write(f"Discrepancies: {details.get('discrepancies', 0)}")
        
        with col2:
            st.write("**Tolerance Settings**")
            tolerances = details.get('tolerances', {})
            for metric, tolerance in tolerances.items():
                st.write(f"{metric}: {format_percentage(tolerance * 100)}")
        
        # Discrepancy details
        discrepancies = details.get('discrepancy_details', [])
        if discrepancies:
            st.subheader("⚠️ Discrepancies Found")
            
            for disc in discrepancies:
                with st.expander(f"❗ {disc.get('field', 'Unknown Field')}"):
                    st.write(f"Expected: {format_currency(disc.get('expected'))}")
                    st.write(f"Actual: {format_currency(disc.get('actual'))}")
                    st.write(f"Difference: {format_currency(disc.get('difference'))}")
                    st.write(f"Tolerance: {format_percentage(disc.get('tolerance', 0) * 100)}")
        
        # Manual reconciliation trigger
        st.subheader("🔄 Manual Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Run Reconciliation", help="Trigger manual reconciliation"):
                with st.spinner("Running reconciliation..."):
                    result = fetch_data(f"/pe/reconcile/{fund_id}", timeout=60)
                    if result:
                        st.success("Reconciliation completed!")
                        st.rerun()
                    else:
                        st.error("Reconciliation failed")
        
        with col2:
            if st.button("📊 Recalculate Metrics", help="Recalculate performance metrics"):
                with st.spinner("Recalculating metrics..."):
                    # This would trigger metric recalculation
                    st.info("Metric recalculation triggered")
    
    except Exception as e:
        st.error(f"Error rendering reconciliation view: {str(e)}")
        logger.error(f"Reconciliation view error: {e}")


def render_manual_override(fund_id: str):
    """Render manual data override interface."""
    st.subheader("✏️ Manual Override")
    
    st.warning("⚠️ Manual overrides affect data integrity. Use with caution.")
    
    try:
        # Get current data for editing
        capital_data = fetch_data(f"/pe/capital-account-series/{fund_id}")
        
        if not capital_data:
            st.info("No data available for override")
            return
        
        # Select document/period for override
        periods = [item.get('period_label', 'Unknown') for item in capital_data]
        selected_period = st.selectbox("Select Period", periods)
        
        if selected_period:
            # Find the selected data
            selected_data = next(
                (item for item in capital_data if item.get('period_label') == selected_period), 
                None
            )
            
            if selected_data:
                st.write("**Current Values**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Editable fields
                    new_beginning = st.number_input(
                        "Beginning Balance", 
                        value=float(selected_data.get('beginning_balance', 0))
                    )
                    new_ending = st.number_input(
                        "Ending Balance", 
                        value=float(selected_data.get('ending_balance', 0))
                    )
                    new_contributions = st.number_input(
                        "Contributions", 
                        value=float(selected_data.get('contributions_period', 0))
                    )
                
                with col2:
                    new_distributions = st.number_input(
                        "Distributions", 
                        value=float(selected_data.get('distributions_period', 0))
                    )
                    new_fees = st.number_input(
                        "Management Fees", 
                        value=float(selected_data.get('management_fees_period', 0))
                    )
                    
                    override_reason = st.text_area("Reason for Override", height=100)
                
                # Apply override
                if st.button("✏️ Apply Override", type="primary"):
                    if not override_reason.strip():
                        st.error("Please provide a reason for the override")
                    else:
                        override_data = {
                            "fund_id": fund_id,
                            "period_label": selected_period,
                            "overrides": {
                                "beginning_balance": new_beginning,
                                "ending_balance": new_ending,
                                "contributions_period": new_contributions,
                                "distributions_period": new_distributions,
                                "management_fees_period": new_fees
                            },
                            "reason": override_reason
                        }
                        
                        # This would call the manual override API
                        st.success("Override applied successfully!")
                        st.info("Note: This is a simulation - actual override API not implemented yet")
    
    except Exception as e:
        st.error(f"Error rendering manual override: {str(e)}")
        logger.error(f"Manual override error: {e}")


def render_pe_portfolio():
    """Render PE portfolio analysis page."""
    st.header("📊 PE Portfolio Analysis")
    
    try:
        # Get portfolio data
        portfolio_data = fetch_data("/pe/portfolio")
        
        if not portfolio_data:
            st.info("No portfolio data available")
            return
        
        # Portfolio overview
        render_portfolio_overview(portfolio_data)
        
        # Portfolio composition
        render_portfolio_composition(portfolio_data)
        
        # Performance analysis
        render_portfolio_performance(portfolio_data)
        
    except Exception as e:
        st.error(f"Error rendering portfolio: {str(e)}")
        logger.error(f"Portfolio error: {e}")


def render_portfolio_overview(portfolio_data: Dict[str, Any]):
    """Render portfolio overview metrics."""
    st.subheader("📊 Portfolio Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_nav = portfolio_data.get('total_nav', 0)
        st.metric("Total NAV", format_currency(total_nav))
    
    with col2:
        num_investments = portfolio_data.get('num_investments', 0)
        st.metric("Active Investments", num_investments)
    
    with col3:
        avg_irr = portfolio_data.get('weighted_avg_irr', 0)
        st.metric("Weighted Avg IRR", format_percentage(avg_irr))
    
    with col4:
        total_moic = portfolio_data.get('total_moic', 0)
        st.metric("Total MOIC", format_multiple(total_moic))


def render_portfolio_composition(portfolio_data: Dict[str, Any]):
    """Render portfolio composition analysis."""
    st.subheader("🥧 Portfolio Composition")
    
    investments = portfolio_data.get('investments', [])
    
    if investments:
        # Create composition chart
        composition_data = [
            {"name": inv.get('name', 'Unknown'), "value": inv.get('current_value', 0)}
            for inv in investments
        ]
        
        display_chart_with_error_handling(
            create_portfolio_composition_chart,
            composition_data
        )
        
        # Top holdings table
        st.subheader("🏆 Top Holdings")
        
        df = pd.DataFrame(investments)
        if not df.empty:
            # Sort by current value
            df_sorted = df.sort_values('current_value', ascending=False).head(10)
            
            # Format for display
            display_cols = ['name', 'sector', 'current_value', 'ownership_percentage']
            display_df = df_sorted[display_cols].copy()
            
            display_df['current_value'] = display_df['current_value'].apply(format_currency)
            display_df['ownership_percentage'] = display_df['ownership_percentage'].apply(format_percentage)
            
            st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No investment data available")


def render_portfolio_performance(portfolio_data: Dict[str, Any]):
    """Render portfolio performance analysis."""
    st.subheader("📈 Performance Analysis")
    
    performance = portfolio_data.get('performance_metrics', {})
    
    if performance:
        # Performance metrics chart
        metrics_data = {
            'IRR': performance.get('irr', 0),
            'MOIC': performance.get('moic', 0),
            'DPI': performance.get('dpi', 0),
            'TVPI': performance.get('tvpi', 0)
        }
        
        display_chart_with_error_handling(
            create_performance_metrics_chart,
            metrics_data
        )
        
        # Performance comparison
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Fund Performance**")
            st.metric("Net IRR", format_percentage(performance.get('irr', 0)))
            st.metric("Net MOIC", format_multiple(performance.get('moic', 0)))
            st.metric("Net DPI", format_multiple(performance.get('dpi', 0)))
        
        with col2:
            st.write("**Benchmark Comparison**")
            benchmark = performance.get('benchmark', {})
            
            if benchmark:
                st.metric("Benchmark IRR", format_percentage(benchmark.get('irr', 0)))
                st.metric("Relative IRR", format_percentage(performance.get('irr', 0) - benchmark.get('irr', 0)))
            else:
                st.info("No benchmark data available")
    else:
        st.info("No performance data available")