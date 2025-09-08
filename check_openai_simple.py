"""Simple check of OpenAI vector store."""

import os
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")

print(f"OPENAI_VECTOR_STORE_ID: {vector_store_id}")

if vector_store_id:
    try:
        vs = client.beta.vector_stores.retrieve(vector_store_id)
        print(f"✅ Vector Store Status: {vs.status}")
        print(f"📊 File Count: {vs.file_counts.total}")
        print(f"💾 Size: {vs.usage_bytes:,} bytes")
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("❌ OPENAI_VECTOR_STORE_ID not set")