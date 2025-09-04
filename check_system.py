#!/usr/bin/env python3
"""Comprehensive system check for FOReporting v2."""

import os
import sys
from pathlib import Path
import json

def check_git_status():
    """Check Git repository status."""
    print("🔍 Checking Git Status...")
    import subprocess
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if result.returncode == 0:
            if result.stdout.strip():
                print(f"⚠️  Uncommitted changes found:\n{result.stdout}")
            else:
                print("✅ Git repository is clean")
        else:
            print(f"❌ Git status failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Git check failed: {e}")

def check_database():
    """Check database connection and schema."""
    print("\n🗄️ Checking Database...")
    try:
        from sqlalchemy import create_engine, text
        from app.config import settings
        url = settings.get("DATABASE_URL")
        if not url:
            print("❌ DATABASE_URL not set")
            return
        
        print(f"Database URL: {url.split('@')[0]}@[HIDDEN]")
        
        # Test connection
        if url.startswith("postgresql"):
            engine = create_engine(url, connect_args={"options": "-c client_encoding=UTF8"})
        else:
            engine = create_engine(url)
        
        with engine.connect() as conn:
            print("✅ Database connection successful")
            
            # Check if tables exist
            if url.startswith("postgresql"):
                result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            else:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            
            tables = [row[0] for row in result]
            expected_tables = ["dim_date", "dim_period", "pe_document", "pe_nav_observation", "pe_cashflow", "ingestion_file", "ingestion_job"]
            
            print(f"📊 Found {len(tables)} tables: {', '.join(tables)}")
            
            missing_tables = [t for t in expected_tables if t not in tables]
            if missing_tables:
                print(f"⚠️  Missing tables: {', '.join(missing_tables)}")
            else:
                print("✅ All expected tables present")
                
    except Exception as e:
        print(f"❌ Database check failed: {e}")

def check_field_library():
    """Check Field Library mapping files."""
    print("\n📚 Checking Field Library...")
    mapping_dir = Path("app/pe_docs/mapping")
    
    if not mapping_dir.exists():
        print("❌ Mapping directory not found")
        return
    
    expected_files = [
        "field_library.yaml",
        "column_map.csv", 
        "regex_bank.yaml",
        "phrase_bank.yaml",
        "validation_rules.yaml",
        "units.yaml"
    ]
    
    for file in expected_files:
        file_path = mapping_dir / file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✅ {file} ({size} bytes)")
        else:
            print(f"❌ {file} missing")
    
    # Check seed files
    seeds_dir = Path("app/pe_docs/seeds")
    if seeds_dir.exists():
        seed_files = list(seeds_dir.glob("*.xlsx")) + list(seeds_dir.glob("*.pdf"))
        print(f"📁 Seed files: {len(seed_files)} files in seeds directory")
    else:
        print("⚠️  Seeds directory not found")

def check_dependencies():
    """Check required Python dependencies."""
    print("\n📦 Checking Dependencies...")
    
    required_packages = [
        "fastapi", "uvicorn", "sqlalchemy", "alembic", "pydantic",
        "pandas", "openai", "chromadb", "watchdog", "streamlit",
        "PyPDF2", "openpyxl", "psycopg2", "python-dotenv"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            missing.append(package)
            print(f"❌ {package}")
    
    if missing:
        print(f"\n⚠️  Install missing packages: pip install {' '.join(missing)}")
    else:
        print("\n✅ All dependencies installed")

def check_config():
    """Check configuration files."""
    print("\n⚙️ Checking Configuration...")
    
    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file exists")
        # Check required variables using settings (without printing values)
        from app.config import settings
        required_settings = ["DATABASE_URL", "INVESTOR1_PATH", "INVESTOR2_PATH"]
        for setting in required_settings:
            if settings.get(setting):
                print(f"✅ {setting} is set")
            else:
                print(f"❌ {setting} not set")
    else:
        print("❌ .env file missing")
    
    # Check folder paths
    for i, path_setting in enumerate(["INVESTOR1_PATH", "INVESTOR2_PATH"], 1):
        path = settings.get(path_setting)
        if path and Path(path).exists():
            print(f"✅ Investor {i} folder exists")
        else:
            print(f"❌ Investor {i} folder not found: {path}")

def check_project_structure():
    """Check project structure."""
    print("\n📁 Checking Project Structure...")
    
    expected_dirs = [
        "app", "app/database", "app/services", "app/processors", 
        "app/frontend", "scripts", "alembic", "alembic/versions"
    ]
    
    for dir_path in expected_dirs:
        if Path(dir_path).exists():
            print(f"✅ {dir_path}/")
        else:
            print(f"❌ {dir_path}/ missing")
    
    # Check key files
    key_files = [
        "app/main.py", "app/config.py", "requirements.txt", 
        "README.md", "alembic.ini", ".cursorrules"
    ]
    
    for file_path in key_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} missing")

def check_vector_store():
    """Check vector store setup."""
    print("\n🔍 Checking Vector Store...")
    try:
        import chromadb
        from app.config import settings
        chroma_dir = settings.get("CHROMA_DIR", "./data/chroma")
        print(f"✅ ChromaDB available")
        print(f"📁 Vector store directory: {chroma_dir}")
        
        if Path(chroma_dir).exists():
            print("✅ ChromaDB directory exists")
        else:
            print("⚠️  ChromaDB directory will be created on first use")
            
    except ImportError:
        print("❌ ChromaDB not installed")

def main():
    """Run comprehensive system check."""
    print("🚀 FOReporting v2 - Comprehensive System Check")
    print("=" * 60)
    
    # Set UTF-8 environment
    os.environ["PGCLIENTENCODING"] = "UTF8"
    os.environ["PYTHONUTF8"] = "1"
    
    # Load environment
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Environment loaded from .env")
    except Exception as e:
        print(f"⚠️  Could not load .env: {e}")
    
    # Run all checks
    check_git_status()
    check_project_structure()
    check_config()
    check_dependencies()
    check_field_library()
    check_database()
    check_vector_store()
    
    print("\n" + "=" * 60)
    print("🎯 System Check Complete!")
    
    # Summary
    print("\n📋 Quick Start Commands:")
    print("1. Start API server: python -m app.main")
    print("2. Start dashboard: streamlit run app/frontend/dashboard.py")
    print("3. Test processing: python scripts/test_processing.py")

if __name__ == "__main__":
    main()