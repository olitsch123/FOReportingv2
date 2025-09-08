"""Start backend API locally with proper configuration"""
import os
import sys
import uvicorn

# Set environment variables
os.environ['DEPLOYMENT_MODE'] = 'local'
os.environ['PYTHONPATH'] = '.'
os.environ['PGCLIENTENCODING'] = 'UTF8'
os.environ['PYTHONUTF8'] = '1'

print("Starting FOReporting v2 Backend (Local Mode)...")
print("-" * 50)

try:
    # Import and verify config
    from app.config import settings
    print(f"✓ Configuration loaded")
    print(f"  Deployment mode: {settings.get('DEPLOYMENT_MODE', 'local')}")
    print(f"  Database: {settings.get('DATABASE_URL', '')[:50]}...")
    print(f"  API Key: {'✓ Configured' if settings.get('OPENAI_API_KEY') else '✗ Missing'}")
    
    # Import app
    from app.main import app
    print("✓ FastAPI app imported")
    
    # Start server
    print("\nStarting server on http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    print("-" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
    
except KeyboardInterrupt:
    print("\nServer stopped by user")
except Exception as e:
    print(f"\n❌ Failed to start server: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)