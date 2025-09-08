"""Complete local setup for FOReporting v2 - 100% accuracy."""

import os
import subprocess
import sys
import time
from pathlib import Path

print("="*60)
print("FOReporting v2 - Complete Local Setup")
print("="*60)

# Step 1: Check .env configuration
print("\n1. Checking .env configuration...")
env_path = Path('.env')
if not env_path.exists():
    print("❌ .env file not found! Create from env_example.txt")
    sys.exit(1)

with open(env_path, 'r') as f:
    env_content = f.read()

# Check if DATABASE_URL is set for local
if 'localhost:5432' in env_content:
    print("✓ DATABASE_URL is set for localhost")
elif 'postgres:5432' in env_content:
    print("⚠️ DATABASE_URL points to Docker hostname 'postgres'")
    print("   Updating to localhost...")
    new_content = env_content.replace('@postgres:5432', '@localhost:5432')
    with open(env_path, 'w') as f:
        f.write(new_content)
    print("✓ Updated DATABASE_URL to use localhost")

# Ensure DEPLOYMENT_MODE is local
if 'DEPLOYMENT_MODE=local' not in env_content:
    print("⚠️ Setting DEPLOYMENT_MODE=local in .env")
    with open(env_path, 'a') as f:
        f.write('\n# Local deployment mode\nDEPLOYMENT_MODE=local\n')

# Step 2: Check local PostgreSQL
print("\n2. Checking local PostgreSQL...")
try:
    # Try to connect to local PostgreSQL
    result = subprocess.run([
        'psql', '-h', 'localhost', '-p', '5432', '-U', 'postgres',
        '-c', 'SELECT version();'
    ], capture_output=True, text=True, timeout=5)
    
    if result.returncode == 0:
        print("✓ Local PostgreSQL is running")
    else:
        print("❌ Cannot connect to local PostgreSQL")
        print("   Please install and start PostgreSQL locally")
        print("   Download from: https://www.postgresql.org/download/windows/")
        sys.exit(1)
except FileNotFoundError:
    print("❌ psql command not found")
    print("   Please install PostgreSQL and add it to PATH")
    sys.exit(1)
except Exception as e:
    print(f"❌ PostgreSQL check failed: {e}")
    sys.exit(1)

# Step 3: Create database and user
print("\n3. Setting up database...")
db_commands = [
    "CREATE USER system WITH PASSWORD 'BreslauerPlatz4' CREATEDB SUPERUSER;",
    "CREATE DATABASE foreporting_db OWNER system ENCODING 'UTF8';",
    "GRANT ALL PRIVILEGES ON DATABASE foreporting_db TO system;"
]

for cmd in db_commands:
    try:
        result = subprocess.run([
            'psql', '-h', 'localhost', '-p', '5432', '-U', 'postgres',
            '-c', cmd
        ], capture_output=True, text=True)
        if 'already exists' in result.stderr:
            print(f"   ℹ️ {cmd.split()[1]} {cmd.split()[2]} already exists")
        elif result.returncode == 0:
            print(f"   ✓ {cmd.split()[0]} {cmd.split()[1]} completed")
        else:
            print(f"   ⚠️ {result.stderr}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n✅ Local setup configuration complete!")
print("\nNext steps:")
print("1. Run: python -m pip install -r requirements.txt")
print("2. Run: alembic upgrade head")
print("3. Run: python run.py")
print("4. In new terminal: streamlit run app/frontend/dashboard.py")
print("5. In new terminal: python app/services/watcher_runner.py")