"""Test file watcher integration with API and frontend."""
import os
import sys
import requests
import time
from pathlib import Path

# Set environment
os.environ['DEPLOYMENT_MODE'] = 'local'
os.environ['PYTHONPATH'] = '.'

print("=" * 60)
print("Testing File Watcher Integration")
print("=" * 60)

API_BASE = "http://localhost:8000"

def test_api_endpoint(endpoint, method="GET", data=None):
    """Test an API endpoint."""
    try:
        if method == "GET":
            response = requests.get(f"{API_BASE}{endpoint}", timeout=5)
        elif method == "POST":
            headers = {"Content-Type": "application/json"}
            response = requests.post(f"{API_BASE}{endpoint}", json=data or {}, headers=headers, timeout=5)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"Status {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

# 1. Check API health
print("\n1. Checking API health...")
success, data = test_api_endpoint("/health")
if success:
    services = data.get("services", {})
    fw_status = services.get("file_watcher", "unknown")
    print(f"   ✓ API is healthy")
    print(f"   File watcher in health: {fw_status}")
else:
    print(f"   ✗ API health check failed: {data}")
    print("   Make sure the backend is running: python run.py")
    sys.exit(1)

# 2. Test file watcher status endpoint
print("\n2. Testing file watcher status endpoint...")
success, data = test_api_endpoint("/file-watcher/status")
if success:
    print(f"   ✓ Status endpoint working")
    print(f"   Is running: {data.get('is_running', False)}")
    print(f"   Watched folders: {len(data.get('watched_folders', []))}")
    print(f"   Queue size: {data.get('queue_size', 0)}")
    initial_running = data.get('is_running', False)
else:
    print(f"   ✗ Status endpoint failed: {data}")
    initial_running = False

# 3. Test stop endpoint (if running)
if initial_running:
    print("\n3. Testing stop endpoint...")
    success, data = test_api_endpoint("/file-watcher/stop", method="POST")
    if success:
        print(f"   ✓ Stop successful: {data.get('message', '')}")
        time.sleep(1)
        
        # Verify it stopped
        success, status = test_api_endpoint("/file-watcher/status")
        if success and not status.get('is_running'):
            print("   ✓ Verified: File watcher is stopped")
        else:
            print("   ✗ File watcher still running after stop")
    else:
        print(f"   ✗ Stop failed: {data}")

# 4. Test start endpoint
print("\n4. Testing start endpoint...")
success, data = test_api_endpoint("/file-watcher/start", method="POST")
if success:
    print(f"   ✓ Start successful: {data.get('message', '')}")
    time.sleep(2)
    
    # Verify it started
    success, status = test_api_endpoint("/file-watcher/status")
    if success and status.get('is_running'):
        print("   ✓ Verified: File watcher is running")
        print(f"   Watching folders: {status.get('watched_folders', [])}")
    else:
        print("   ✗ File watcher not running after start")
else:
    print(f"   ✗ Start failed: {data}")

# 5. Check updated health endpoint
print("\n5. Checking updated health endpoint...")
success, data = test_api_endpoint("/health")
if success:
    services = data.get("services", {})
    fw_status = services.get("file_watcher", "unknown")
    print(f"   ✓ File watcher status in health: {fw_status}")
else:
    print(f"   ✗ Health check failed: {data}")

# 6. Test stats endpoint
print("\n6. Checking stats endpoint...")
success, data = test_api_endpoint("/stats")
if success:
    fw_info = data.get("file_watcher", {})
    print(f"   ✓ File watcher in stats: {fw_info}")
else:
    print(f"   ✗ Stats check failed: {data}")

# 7. Stop file watcher for cleanup
print("\n7. Cleanup - stopping file watcher...")
success, data = test_api_endpoint("/file-watcher/stop", method="POST")
if success:
    print(f"   ✓ Cleanup successful")

print("\n" + "=" * 60)
print("✅ File Watcher Integration Test Complete!")
print("\nFrontend Integration:")
print("1. Open http://localhost:8501")
print("2. Check sidebar for File Watcher controls")
print("3. Try Start/Stop buttons")
print("4. Check main dashboard for File Watcher Activity section")
print("=" * 60)