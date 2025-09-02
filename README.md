# FOReporting v2 - Financial Document Intelligence System

An automated database system for processing and analyzing financial documents from PE funds with AI-powered document classification, data extraction, and intelligent querying capabilities.

## Features

- **Automated Document Processing**: Monitors specified folders and automatically processes PDF, CSV, and XLSX files
- **AI-Powered Classification**: Uses OpenAI API to classify and extract structured data from financial documents
- **Multi-Entity Support**: Handles multiple investors, entities, asset classes, and consolidation scenarios
- **Vector Database**: Semantic search capabilities using ChromaDB for document embeddings
- **Chat Interface**: Natural language querying of financial data
- **Time Series Analysis**: Track financial metrics over time with forecasting capabilities
- **Unique Document IDs**: Each document gets classified and assigned a unique identifier

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   File Watcher  │    │  Document       │    │   PostgreSQL    │
│   (Watchdog)    │───▶│  Processor      │───▶│   Database      │
└─────────────────┘    │  (OpenAI API)   │    └─────────────────┘
                       └─────────────────┘              │
                                 │                      │
                                 ▼                      │
                       ┌─────────────────┐              │
                       │   ChromaDB      │              │
                       │  (Vector Store) │              │
                       └─────────────────┘              │
                                 │                      │
                                 ▼                      ▼
                       ┌─────────────────────────────────────┐
                       │        FastAPI Backend             │
                       │    (REST API + Chat Interface)     │
                       └─────────────────────────────────────┘
                                         │
                                         ▼
                       ┌─────────────────────────────────────┐
                       │      Streamlit Frontend            │
                       │   (Dashboard + Chat Interface)     │
                       └─────────────────────────────────────┘
```

## Setup

1. **Clone and Install Dependencies**
   ```bash
   git clone <repository>
   cd FOReportingv2
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp env_example.txt .env
   # Edit .env with your OpenAI API key and database credentials
   ```

3. **Setup Database**
   ```bash
   # Install PostgreSQL and create database
   createdb fodb
   
   # Run migrations
   alembic upgrade head
   ```

4. **Start the System**
   ```bash
   # Start the API server
   python -m app.main
   
   # In another terminal, start the Streamlit interface
   streamlit run app/frontend/dashboard.py
   ```

## Usage

1. **Document Processing**: Place documents in the monitored folders:
   - Investor 1: `C:\Users\OliverGötz\Equivia GmbH\01_BrainWeb Investment GmbH - Dokumente\09 Funds`
   - Investor 2: `C:\Users\OliverGötz\Equivia GmbH\01_pecunalta GmbH - Documents`

2. **Chat Interface**: Use natural language to query your financial data:
   - "Show me Q3 2023 performance for BrainWeb funds"
   - "What are the top performing assets this year?"
   - "Compare NAV trends across all funds"

3. **Dashboard**: View time series charts, portfolio summaries, and document insights

## Document Types Supported

- **Quarterly Reports**: Automatically extracts NAV, performance metrics, holdings
- **Financial Statements**: Balance sheets, P&L statements, cash flow
- **Investment Reports**: Deal summaries, valuations, exit reports
- **CSV Data**: Portfolio holdings, transaction data, benchmark data
- **Excel Files**: Complex financial models, reporting templates

## Data Model

The system supports:
- Multiple investors and entities
- Various asset classes (PE, VC, Real Estate, etc.)
- Consolidation across funds and time periods
- Gap analysis and forecasting
- Master data management for consistent reporting

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **AI/ML**: OpenAI API, ChromaDB, Sentence Transformers
- **Frontend**: Streamlit, Plotly
- **Document Processing**: PyPDF2, pandas, openpyxl
- **File Monitoring**: Watchdog