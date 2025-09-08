#!/usr/bin/env python3
"""Test document tracker functionality."""

import requests
import time
import json

API_BASE = "http://localhost:8000"

def test_document_tracker():
    """Test document tracker functionality."""
    print("=" * 60)
    print("Testing Document Tracker")
    print("=" * 60)
    
    # 1. Check tracker stats
    print("\n1. Document Tracker Stats:")
    try:
        response = requests.get(f"{API_BASE}/document-tracker/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"   Total documents: {stats.get('total', 0)}")
            print(f"   - Discovered: {stats.get('discovered', 0)}")
            print(f"   - Processing: {stats.get('processing', 0)}")
            print(f"   - Completed: {stats.get('completed', 0)}")
            print(f"   - Failed: {stats.get('failed', 0)}")
        else:
            print(f"   ✗ Error: Status {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 2. Start file watcher to populate tracker
    print("\n2. Starting file watcher to discover documents...")
    try:
        response = requests.post(
            f"{API_BASE}/file-watcher/start",
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            print("   ✓ File watcher started")
        else:
            print(f"   ✗ Failed to start: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 3. Wait for some processing
    print("\n3. Waiting 10 seconds for processing...")
    time.sleep(10)
    
    # 4. Check stats again
    print("\n4. Updated Document Tracker Stats:")
    try:
        response = requests.get(f"{API_BASE}/document-tracker/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"   Total documents: {stats.get('total', 0)}")
            print(f"   - Discovered: {stats.get('discovered', 0)}")
            print(f"   - Processing: {stats.get('processing', 0)}")
            print(f"   - Completed: {stats.get('completed', 0)}")
            print(f"   - Failed: {stats.get('failed', 0)}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 5. Export to CSV
    print("\n5. Testing CSV Export:")
    try:
        # Export all documents
        response = requests.get(f"{API_BASE}/document-tracker/export?format=csv")
        print(f"   Response status: {response.status_code}")
        
        if response.status_code == 200:
            # Save to file
            filename = "document_tracker_export.csv"
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"   ✓ Exported all documents to {filename}")
            
            # Check file size
            import os
            size = os.path.getsize(filename)
            print(f"   File size: {size:,} bytes")
            
            # Show first few lines
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f"   Total lines: {len(lines)}")
                if len(lines) > 1:
                    print("   Headers:", lines[0].strip())
                    print("   First record:", lines[1].strip() if len(lines) > 1 else "No data")
        else:
            print(f"   ✗ Export failed: {response.text}")
        
        # Export only completed documents
        response = requests.get(f"{API_BASE}/document-tracker/export?status=completed&format=csv")
        if response.status_code == 200:
            filename_completed = "document_tracker_completed.csv"
            with open(filename_completed, 'wb') as f:
                f.write(response.content)
            print(f"\n   ✓ Exported completed documents to {filename_completed}")
        else:
            print(f"   ✗ Export completed failed: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 6. Test JSON export
    print("\n6. Testing JSON Export:")
    try:
        response = requests.get(f"{API_BASE}/document-tracker/export?format=json&status=failed")
        if response.status_code == 200:
            failed_docs = response.json()
            print(f"   Failed documents: {len(failed_docs)}")
            if failed_docs:
                # Show first failed document
                doc = failed_docs[0]
                print(f"   Example: {doc.get('file_name', 'Unknown')}")
                print(f"   Error: {doc.get('error_message', 'No error message')}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # 7. Stop file watcher
    print("\n7. Stopping file watcher...")
    try:
        response = requests.post(
            f"{API_BASE}/file-watcher/stop",
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            print("   ✓ File watcher stopped")
    except:
        pass
    
    print("\n" + "=" * 60)
    print("Document Tracker Test Complete!")
    print("Check the exported CSV files for detailed document status.")
    print("=" * 60)

if __name__ == "__main__":
    test_document_tracker()