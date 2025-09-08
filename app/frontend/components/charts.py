"""Chart components using Plotly."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from app.frontend.utils.formatters import format_currency, format_percentage

logger = logging.getLogger(__name__)


def create_time_series_chart(
    data: List[Dict[str, Any]], 
    x_field: str, 
    y_field: str,
    title: str,
    currency: str = "EUR"
) -> go.Figure:
    """Create a time series chart."""
    try:
        if not data:
            return create_empty_chart("No data available")
        
        df = pd.DataFrame(data)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df[x_field],
            y=df[y_field],
            mode='lines+markers',
            name=y_field.replace('_', ' ').title(),
            line=dict(width=3),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title=x_field.replace('_', ' ').title(),
            yaxis_title=y_field.replace('_', ' ').title(),
            hovermode='x unified',
            template='plotly_white'
        )
        
        # Format y-axis for currency
        if 'balance' in y_field or 'nav' in y_field or 'value' in y_field:
            fig.update_yaxis(tickformat=',.0f')
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating time series chart: {e}")
        return create_empty_chart(f"Chart error: {str(e)}")


def create_performance_metrics_chart(metrics_data: Dict[str, float]) -> go.Figure:
    """Create performance metrics bar chart."""
    try:
        if not metrics_data:
            return create_empty_chart("No performance data")
        
        metrics = list(metrics_data.keys())
        values = list(metrics_data.values())
        
        fig = go.Figure(data=[
            go.Bar(
                x=metrics,
                y=values,
                marker_color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'][:len(metrics)]
            )
        ])
        
        fig.update_layout(
            title="Performance Metrics",
            xaxis_title="Metric",
            yaxis_title="Value",
            template='plotly_white'
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating performance chart: {e}")
        return create_empty_chart(f"Chart error: {str(e)}")


def create_portfolio_composition_chart(portfolio_data: List[Dict[str, Any]]) -> go.Figure:
    """Create portfolio composition pie chart."""
    try:
        if not portfolio_data:
            return create_empty_chart("No portfolio data")
        
        df = pd.DataFrame(portfolio_data)
        
        fig = px.pie(
            df, 
            values='value', 
            names='name',
            title="Portfolio Composition"
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(template='plotly_white')
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating portfolio chart: {e}")
        return create_empty_chart(f"Chart error: {str(e)}")


def create_capital_flow_chart(capital_data: List[Dict[str, Any]]) -> go.Figure:
    """Create capital flow waterfall chart."""
    try:
        if not capital_data:
            return create_empty_chart("No capital flow data")
        
        df = pd.DataFrame(capital_data)
        
        fig = go.Figure(go.Waterfall(
            name="Capital Flow",
            orientation="v",
            measure=df.get('measure', ['relative'] * len(df)),
            x=df.get('period', range(len(df))),
            y=df.get('amount', [0] * len(df)),
            text=df.get('label', [''] * len(df)),
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        ))
        
        fig.update_layout(
            title="Capital Flow Analysis",
            xaxis_title="Period",
            yaxis_title="Amount",
            template='plotly_white'
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating capital flow chart: {e}")
        return create_empty_chart(f"Chart error: {str(e)}")


def create_comparison_chart(
    data1: List[Dict[str, Any]], 
    data2: List[Dict[str, Any]],
    label1: str,
    label2: str,
    x_field: str,
    y_field: str
) -> go.Figure:
    """Create comparison chart between two datasets."""
    try:
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=(label1, label2),
            specs=[[{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        if data1:
            df1 = pd.DataFrame(data1)
            fig.add_trace(
                go.Scatter(x=df1[x_field], y=df1[y_field], name=label1),
                row=1, col=1
            )
        
        if data2:
            df2 = pd.DataFrame(data2)
            fig.add_trace(
                go.Scatter(x=df2[x_field], y=df2[y_field], name=label2),
                row=1, col=2
            )
        
        fig.update_layout(
            title="Comparison Analysis",
            template='plotly_white'
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating comparison chart: {e}")
        return create_empty_chart(f"Chart error: {str(e)}")


def create_empty_chart(message: str = "No data available") -> go.Figure:
    """Create an empty chart with a message."""
    fig = go.Figure()
    
    fig.add_annotation(
        x=0.5,
        y=0.5,
        text=message,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=16, color="gray")
    )
    
    fig.update_layout(
        template='plotly_white',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False)
    )
    
    return fig


def create_portfolio_composition_chart(portfolio_data: List[Dict[str, Any]]) -> go.Figure:
    """Create portfolio composition pie chart."""
    try:
        if not portfolio_data:
            return create_empty_chart("No portfolio data")
        
        df = pd.DataFrame(portfolio_data)
        
        fig = px.pie(
            df, 
            values='value', 
            names='name',
            title="Portfolio Composition"
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(template='plotly_white')
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating portfolio chart: {e}")
        return create_empty_chart(f"Chart error: {str(e)}")


def display_chart_with_error_handling(chart_func, *args, **kwargs):
    """Display chart with error handling."""
    try:
        fig = chart_func(*args, **kwargs)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error displaying chart: {str(e)}")
        logger.error(f"Chart display error: {e}")