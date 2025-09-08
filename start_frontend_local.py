"""Start Streamlit frontend locally"""
import os
import sys
import subprocess

# Set environment variables
os.environ['DEPLOYMENT_MODE'] = 'local'
os.environ['PYTHONPATH'] = '.'
os.environ['PGCLIENTENCODING'] = 'UTF8'
os.environ['PYTHONUTF8'] = '1'

print("Starting FOReporting v2 Frontend (Local Mode)...")
print("-" * 50)

try:
    # Verify backend is running
    import requests
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code == 200:
            print("✓ Backend API is running")
        else:
            print("⚠️ Backend API returned status:", response.status_code)
    except:
        print("⚠️ Backend API is not reachable - make sure it's running on port 8000")
    
    print("\nStarting Streamlit dashboard...")
    print("Dashboard will open at: http://localhost:8501")
    print("-" * 50)
    
    # Start streamlit
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "app/frontend/dashboard.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ])
    
except KeyboardInterrupt:
    print("\nFrontend stopped by user")
except Exception as e:
    print(f"\n❌ Failed to start frontend: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)