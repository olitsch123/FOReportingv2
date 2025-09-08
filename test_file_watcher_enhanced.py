#!/usr/bin/env python3
"""Enhanced test script for file watcher functionality."""

import requests
import json
import time

API_BASE = "http://localhost:8000"

def test_file_watcher():
    """Test file watcher functionality."""
    print("=" * 60)
    print("Enhanced File Watcher Test")
    print("=" * 60)
    
    # 1. Check initial status
    print("\n1. Checking file watcher status...")
    try:
        response = requests.get(f"{API_BASE}/file-watcher/status")
        status = response.json()
        
        print(f"   Is running: {status['is_running']}")
        print(f"   Total files found: {status['total_files_found']}")
        
        print("\n   Watched folders:")
        for folder in status['watched_folders']:
            print(f"   - {folder['name']}: {folder['path']}")
            print(f"     Exists: {folder['exists']}, Files: {folder['file_count']}")
        
        if status['scan_errors']:
            print("\n   Errors:")
            for error in status['scan_errors']:
                print(f"   - {error}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return
    
    # 2. Trigger manual scan
    print("\n2. Triggering manual scan...")
    try:
        response = requests.post(
            f"{API_BASE}/file-watcher/scan",
            headers={"Content-Type": "application/json"}
        )
        scan_result = response.json()
        
        print(f"   Status: {scan_result['status']}")
        print(f"   Message: {scan_result['message']}")
        
        if scan_result.get('results'):
            results = scan_result['results']
            print(f"\n   Folders scanned:")
            for folder in results['folders_scanned']:
                print(f"   - {folder['name']}: {folder['files_found']} files")
            
            if results['errors']:
                print(f"\n   Errors:")
                for error in results['errors']:
                    print(f"   - {error}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 3. Wait and check status again
    print("\n3. Waiting 5 seconds and checking status again...")
    time.sleep(5)
    
    try:
        response = requests.get(f"{API_BASE}/file-watcher/status")
        status = response.json()
        
        print(f"   Is running: {status['is_running']}")
        print(f"   Total files found: {status['total_files_found']}")
        print(f"   Queue size: {status['queue_size']}")
        
        if status['discovered_files']:
            print(f"\n   Recent discoveries:")
            for file in status['discovered_files'][:5]:  # Show first 5
                print(f"   - {file['path']} ({file['status']})")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 4. Check if files are getting processed
    print("\n4. Checking processed documents...")
    try:
        response = requests.get(f"{API_BASE}/documents?limit=5")
        docs = response.json()
        
        if docs:
            print(f"   Found {len(docs)} recent documents:")
            for doc in docs[:5]:
                print(f"   - {doc.get('file_name', 'Unknown')} ({doc.get('document_type', 'Unknown')})")
        else:
            print("   No documents found yet")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_file_watcher()