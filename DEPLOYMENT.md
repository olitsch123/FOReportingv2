# FOReporting v2 - Deployment Guide

This guide will help you set up and deploy the FOReporting v2 system on your Windows PC.

## Prerequisites

### 1. Software Requirements
- **Python 3.9+** (Download from [python.org](https://www.python.org/downloads/))
- **PostgreSQL 12+** (Download from [postgresql.org](https://www.postgresql.org/downloads/))
- **Git** (Download from [git-scm.com](https://git-scm.com/downloads))

### 2. API Keys
- **OpenAI API Key** - Get from [platform.openai.com](https://platform.openai.com/api-keys)

## Installation Steps

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd FOReportingv2
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up PostgreSQL Database

1. **Install PostgreSQL** and create a database:
```sql
CREATE DATABASE fodb;
CREATE USER fodb_user WITH ENCRYPTED PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE fodb TO fodb_user;
```

2. **Note your connection details** for the .env file

### 5. Configure Environment

1. **Copy the example environment file:**
```bash
copy env_example.txt .env
```

2. **Edit .env file** with your settings:
```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration
DATABASE_URL=postgresql://fodb_user:your_password@localhost:5432/fodb

# ChromaDB Configuration
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Document Processing - UPDATE THESE PATHS
INVESTOR1_FOLDER=C:\Users\OliverGötz\Equivia GmbH\01_BrainWeb Investment GmbH - Dokumente\09 Funds
INVESTOR2_FOLDER=C:\Users\OliverGötz\Equivia GmbH\01_pecunalta GmbH - Documents

# API Configuration
API_HOST=localhost
API_PORT=8000

# Logging
LOG_LEVEL=INFO
```

### 6. Initialize Database
```bash
python scripts/init_db.py
```

### 7. Test the System
```bash
python scripts/test_processing.py
```

## Running the System

### Option 1: Automated Startup (Recommended)
```bash
python scripts/run_system.py
```

This will start both the API server and Streamlit dashboard automatically.

### Option 2: Manual Startup

1. **Start the API Server:**
```bash
python -m app.main
```

2. **In another terminal, start the Dashboard:**
```bash
streamlit run app/frontend/dashboard.py
```

## Accessing the System

- **API Documentation**: http://localhost:8000/docs
- **Streamlit Dashboard**: http://localhost:8501
- **Health Check**: http://localhost:8000/health

## Folder Structure

Your investor folders should be organized like this:
```
C:\Users\OliverGötz\Equivia GmbH\01_BrainWeb Investment GmbH - Dokumente\09 Funds\
├── Fund_A\
│   ├── Q1_2023_Report.pdf
│   ├── Q2_2023_Report.pdf
│   └── Financial_Data.xlsx
└── Fund_B\
    ├── Annual_Report_2023.pdf
    └── Portfolio_Summary.csv

C:\Users\OliverGötz\Equivia GmbH\01_pecunalta GmbH - Documents\
├── Fund_X\
│   └── Quarterly_Report_Q3_2023.pdf
└── Fund_Y\
    └── Investment_Summary.xlsx
```

## Usage Guide

### 1. Document Processing
- The system automatically monitors your investor folders
- Supported formats: PDF, CSV, XLSX, XLS
- Documents are automatically classified and processed
- Financial data is extracted and stored

### 2. Chat Interface
Navigate to the "Chat Interface" in the dashboard and ask questions like:
- "What was the NAV for BrainWeb funds in Q3 2023?"
- "Show me the IRR performance across all funds"
- "Compare the MOIC for private equity vs venture capital funds"
- "What are the top performing funds this year?"

### 3. Dashboard Features
- **Dashboard**: Overview of system statistics and recent documents
- **Documents**: Browse and filter processed documents
- **Funds**: View fund details and performance charts
- **Analytics**: Portfolio-wide analysis and insights

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify PostgreSQL is running
   - Check DATABASE_URL in .env file
   - Ensure database user has proper permissions

2. **OpenAI API Error**
   - Verify your API key is correct
   - Check your OpenAI account has sufficient credits
   - Ensure API key has proper permissions

3. **File Processing Issues**
   - Verify folder paths in .env are correct
   - Ensure the system has read access to the folders
   - Check file formats are supported

4. **Import Errors**
   - Ensure virtual environment is activated
   - Verify all dependencies are installed: `pip install -r requirements.txt`

### Logs and Debugging

- Check console output for error messages
- API logs are displayed in the terminal running the API server
- Set `LOG_LEVEL=DEBUG` in .env for more detailed logging

### Performance Optimization

1. **For Large Document Collections:**
   - Consider increasing `MAX_FILE_SIZE_MB` in settings
   - Monitor ChromaDB disk usage
   - Consider periodic cleanup of old embeddings

2. **For Better AI Performance:**
   - Use `gpt-4-1106-preview` for better document analysis
   - Adjust `CHUNK_SIZE` and `CHUNK_OVERLAP` for your documents
   - Consider using different embedding models for different document types

## System Architecture

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

## Security Considerations

1. **API Keys**: Never commit .env files to version control
2. **Database**: Use strong passwords and consider encryption
3. **Network**: Consider firewall rules if exposing beyond localhost
4. **File Access**: Ensure proper file system permissions

## Backup and Maintenance

1. **Database Backup**: Regularly backup your PostgreSQL database
2. **Vector Store**: Backup the ChromaDB directory
3. **Documents**: The system doesn't modify original files
4. **Updates**: Keep dependencies updated for security patches

## Support

For issues and questions:
1. Check this deployment guide
2. Review error logs
3. Test with the provided test scripts
4. Check the API documentation at `/docs`

## Next Steps

Once the system is running:
1. Add your financial documents to the monitored folders
2. Wait for processing to complete
3. Explore the chat interface and dashboard
4. Set up regular data exports if needed
5. Consider automated backup procedures