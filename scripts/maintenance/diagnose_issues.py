"""Diagnose FOReporting v2 issues."""

import os
import subprocess
import sys

print("=" * 60)
print("FOReporting v2 Diagnostic Tool")
print("=" * 60)

# 1. Check Python version
print("\n1. Python Environment:")
print(f"   Python: {sys.version}")
print(f"   Executable: {sys.executable}")

# 2. Check if pg8000 is installed
print("\n2. Checking critical dependencies:")
try:
    import pg8000
    print(f"   ✓ pg8000 installed: version {pg8000.__version__}")
except ImportError:
    print("   ✗ pg8000 NOT INSTALLED - This is critical!")
    print("     Run: pip install pg8000==1.31.2")

try:
    import sqlalchemy
    print(f"   ✓ SQLAlchemy installed: version {sqlalchemy.__version__}")
except ImportError:
    print("   ✗ SQLAlchemy NOT INSTALLED")

try:
    import fastapi
    print("   ✓ FastAPI installed")
except ImportError:
    print("   ✗ FastAPI NOT INSTALLED")

# 3. Check environment variables
print("\n3. Environment Variables:")
db_url = os.getenv("DATABASE_URL")
if db_url:
    # Hide password in output
    import re
    safe_url = re.sub(r'://[^:]+:[^@]+@', '://[USER]:[PASS]@', db_url)
    print(f"   ✓ DATABASE_URL: {safe_url}")
else:
    print("   ✗ DATABASE_URL not set")
    print("     Check your .env file")

# 4. Test database connection
print("\n4. Database Connection Test:")
if 'pg8000' in sys.modules:
    try:
        from app.database.connection import test_connection
        test_connection()
    except Exception as e:
        print(f"   ✗ Connection test failed: {e}")
else:
    print("   ⚠️ Cannot test - pg8000 not installed")

# 5. Check if Docker is available
print("\n5. Docker Status:")
try:
    result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print(f"   ✓ Docker installed: {result.stdout.strip()}")
        
        # Check if containers are running
        result = subprocess.run(['docker-compose', 'ps'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            output = result.stdout
            if 'postgres' in output and 'Up' in output:
                print("   ✓ PostgreSQL container appears to be running")
            else:
                print("   ⚠️ PostgreSQL container may not be running")
                print("     Run: docker-compose up -d")
    else:
        print("   ✗ Docker command failed")
except Exception as e:
    print(f"   ✗ Docker check failed: {e}")

# 6. Summary
print("\n" + "=" * 60)
print("DIAGNOSIS SUMMARY")
print("=" * 60)

issues = []
if 'pg8000' not in sys.modules:
    issues.append("pg8000 module is missing - CRITICAL")
if not db_url:
    issues.append("DATABASE_URL environment variable not set")

if issues:
    print("\n⚠️ Issues found:")
    for issue in issues:
        print(f"   - {issue}")
    print("\nRecommended actions:")
    print("1. Run: pip install -r requirements.txt")
    print("2. Ensure .env file exists with DATABASE_URL")
    print("3. Run: docker-compose up -d")
    print("4. Re-run this diagnostic")
else:
    print("\n✅ Basic checks passed!")
    print("You can now run: python test_end_to_end.py")

print("\n" + "=" * 60)