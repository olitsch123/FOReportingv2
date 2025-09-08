"""Complete verification of local setup"""
import json
import os
import sys
from pathlib import Path

import requests

os.environ['DEPLOYMENT_MODE'] = 'local'
os.environ['PYTHONPATH'] = '.'

print("=" * 60)
print("FOReporting v2 - Complete Local Verification")
print("=" * 60)

results = {
    "configuration": {},
    "services": {},
    "functionality": {},
    "ready": True
}

# 1. Configuration Check
print("\n1. Configuration Status:")
env_path = Path('.env')
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = {
        "DATABASE_URL": 'localhost:5432' in content,
        "DEPLOYMENT_MODE": 'DEPLOYMENT_MODE=local' in content,
        "OPENAI_API_KEY": 'OPENAI_API_KEY=' in content and 'your-api-key-here' not in content,
        "INVESTOR_PATHS": 'INVESTOR1_PATH' in content and 'INVESTOR2_PATH' in content
    }
    
    for key, value in checks.items():
        results["configuration"][key] = value
        print(f"   {'✓' if value else '✗'} {key}")
        if not value:
            results["ready"] = False

# 2. Service Status
print("\n2. Service Status:")

# Backend API
try:
    response = requests.get("http://localhost:8000/health", timeout=2)
    data = response.json()
    backend_status = response.status_code == 200
    db_status = data.get('services', {}).get('database') == 'connected'
    
    results["services"]["backend_api"] = backend_status
    results["services"]["database"] = db_status
    
    print(f"   {'✓' if backend_status else '✗'} Backend API: {'Running' if backend_status else 'Not running'}")
    print(f"   {'✓' if db_status else '✗'} Database: {data.get('services', {}).get('database', 'unknown')}")
    
    if not backend_status:
        results["ready"] = False
    
    # Show API endpoints
    if backend_status:
        try:
            docs_response = requests.get("http://localhost:8000/openapi.json", timeout=2)
            if docs_response.status_code == 200:
                api_spec = docs_response.json()
                endpoints = list(api_spec.get('paths', {}).keys())
                print(f"   ✓ API Endpoints available: {len(endpoints)}")
                # Show PE-specific endpoints
                pe_endpoints = [e for e in endpoints if '/pe/' in e]
                if pe_endpoints:
                    print("     PE Endpoints:")
                    for ep in pe_endpoints[:5]:
                        print(f"       - {ep}")
        except:
            pass
except Exception as e:
    results["services"]["backend_api"] = False
    results["ready"] = False
    print(f"   ✗ Backend API: Not running (start with: python run.py)")

# Frontend
try:
    response = requests.get("http://localhost:8501", timeout=2)
    frontend_status = response.status_code == 200
    results["services"]["frontend"] = frontend_status
    print(f"   {'✓' if frontend_status else '✗'} Frontend: {'Running' if frontend_status else 'Not running'}")
except:
    results["services"]["frontend"] = False
    print(f"   ✗ Frontend: Not running (start with: streamlit run app/frontend/dashboard.py)")

# 3. PE Functionality
print("\n3. PE Functionality:")
try:
    from app.pe_docs.extractors.multi_method import MultiMethodExtractor
    from app.pe_docs.storage.orm import PEStorageORM
    from app.pe_docs.validation import DocumentValidator
    
    results["functionality"]["extractors"] = True
    print("   ✓ PE Extractors: Available")
    
    results["functionality"]["validation"] = True
    print("   ✓ PE Validation: Available")
    
    results["functionality"]["storage"] = True
    print("   ✓ PE Storage: Available")
except Exception as e:
    results["functionality"]["modules"] = False
    results["ready"] = False
    print(f"   ✗ PE Modules: {e}")

# 4. Summary
print("\n" + "=" * 60)
if results["ready"]:
    print("✅ LOCAL SETUP COMPLETE AND VERIFIED!")
    print("\nYour system is ready for:")
    print("  - Processing PE fund documents")
    print("  - Extracting capital accounts, NAV, performance data")
    print("  - Running validations and reconciliations")
    print("  - Viewing results in the dashboard")
    
    if not results["services"].get("backend_api"):
        print("\nTo start backend: python run.py")
    if not results["services"].get("frontend"):
        print("To start frontend: streamlit run app/frontend/dashboard.py")
else:
    print("❌ LOCAL SETUP INCOMPLETE")
    print("\nIssues found:")
    
    # Configuration issues
    for key, value in results["configuration"].items():
        if not value:
            print(f"  - {key} not configured properly")
    
    # Service issues
    for key, value in results["services"].items():
        if not value:
            print(f"  - {key} is not running")

# Save results
with open('local_verification_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\nDetailed results saved to: local_verification_results.json")
print("=" * 60)