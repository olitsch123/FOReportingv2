"""Script to run the complete FOReporting v2 system."""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))


def run_api_server():
    """Run the FastAPI server."""
    print("🚀 Starting API server...")
    try:
        subprocess.run([
            sys.executable, "-m", "app.main"
        ], cwd=Path(__file__).parent.parent)
    except KeyboardInterrupt:
        print("\n🛑 API server stopped")


def run_streamlit_dashboard():
    """Run the Streamlit dashboard."""
    print("🚀 Starting Streamlit dashboard...")
    try:
        subprocess.run([
            "streamlit", "run", "app/frontend/dashboard.py",
            "--server.port", "8501",
            "--server.headless", "true"
        ], cwd=Path(__file__).parent.parent)
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped")


def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        "fastapi", "uvicorn", "streamlit", "pandas", "plotly",
        "openai", "chromadb", "watchdog", "sqlalchemy"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nPlease install dependencies: pip install -r requirements.txt")
        return False
    
    return True


def check_environment():
    """Check if environment is properly configured."""
    env_file = Path(__file__).parent.parent / ".env"
    
    if not env_file.exists():
        print("❌ .env file not found")
        print("Please copy env_example.txt to .env and configure your settings")
        return False
    
    # Check for required environment variables
    from app.config import settings
    
    try:
        # This will raise an error if required env vars are missing
        _ = settings.openai_api_key
        _ = settings.database_url
        print("✅ Environment configuration looks good")
        return True
    except Exception as e:
        print(f"❌ Environment configuration error: {str(e)}")
        return False


def main():
    """Main function to run the system."""
    print("🌟 FOReporting v2 - Financial Document Intelligence System")
    print("=" * 60)
    
    # Check dependencies
    print("🔍 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    
    # Check environment
    print("🔍 Checking environment configuration...")
    if not check_environment():
        sys.exit(1)
    
    print("✅ All checks passed!")
    print("=" * 60)
    
    print("🚀 Starting system components...")
    print("\nThis will start:")
    print("  1. FastAPI server (http://localhost:8000)")
    print("  2. Streamlit dashboard (http://localhost:8501)")
    print("\nPress Ctrl+C to stop all services")
    print("=" * 60)
    
    # Give user a moment to read
    time.sleep(3)
    
    try:
        # Start API server in a separate thread
        api_thread = threading.Thread(target=run_api_server, daemon=True)
        api_thread.start()
        
        # Wait a bit for API server to start
        print("⏳ Waiting for API server to start...")
        time.sleep(5)
        
        # Start Streamlit dashboard (this will block)
        run_streamlit_dashboard()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down system...")
        print("✅ All services stopped")


if __name__ == "__main__":
    main()