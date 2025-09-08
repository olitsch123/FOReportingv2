"""Test the chat API endpoint."""

import requests
import json

# API base URL
API_BASE_URL = "http://localhost:8000"

def test_chat():
    """Test the chat endpoint."""
    print("Testing Chat API...")
    print("=" * 60)
    
    # Test message
    test_message = "What capital account documents do we have in the system?"
    
    # Send chat request
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={"message": test_message},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Chat API Success!")
            print(f"\n📝 User: {test_message}")
            print(f"\n🤖 Assistant: {data.get('response', 'No response')}")
            print(f"\n📊 Context:")
            print(f"   - Documents used: {data.get('context_documents', 0)}")
            print(f"   - Data points: {data.get('financial_data_points', 0)}")
            print(f"   - Session ID: {data.get('session_id', 'None')}")
        else:
            print(f"❌ Chat API Error: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_chat()