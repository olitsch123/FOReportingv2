"""Check and fix database configuration for local vs Docker."""

import os
import sys

from dotenv import load_dotenv

print("=" * 60)
print("Database Configuration Check")
print("=" * 60)

# Load .env file
if os.path.exists('.env'):
    load_dotenv()
    print("✓ .env file found")
else:
    print("✗ .env file NOT found!")
    print("  Create one from env_example.txt")
    sys.exit(1)

# Check DATABASE_URL
db_url = os.getenv('DATABASE_URL')
deployment_mode = os.getenv('DEPLOYMENT_MODE', 'local')

print(f"\nCurrent Configuration:")
print(f"  DEPLOYMENT_MODE: {deployment_mode}")
if db_url:
    # Hide password
    import re
    safe_url = re.sub(r'://[^:]+:[^@]+@', '://[USER]:[PASS]@', db_url)
    print(f"  DATABASE_URL: {safe_url}")
    
    # Check if URL is appropriate for deployment mode
    if 'postgres:5432' in db_url and deployment_mode == 'local':
        print("\n⚠️ CONFIGURATION MISMATCH DETECTED!")
        print("  You have Docker DATABASE_URL but DEPLOYMENT_MODE=local")
        print("  This means:")
        print("  - PostgreSQL is running in Docker")
        print("  - But you're running Python locally")
        print("\n  SOLUTION: Change DATABASE_URL in .env to use localhost:")
        fixed_url = db_url.replace('@postgres:5432', '@localhost:5432')
        safe_fixed = re.sub(r'://[^:]+:[^@]+@', '://[USER]:[PASS]@', fixed_url)
        print(f"  {safe_fixed}")
        
    elif 'localhost:5432' in db_url and deployment_mode == 'docker':
        print("\n⚠️ CONFIGURATION MISMATCH DETECTED!")
        print("  You have local DATABASE_URL but DEPLOYMENT_MODE=docker")
        print("  SOLUTION: Change DATABASE_URL in .env to use postgres:")
        fixed_url = db_url.replace('@localhost:5432', '@postgres:5432')
        safe_fixed = re.sub(r'://[^:]+:[^@]+@', '://[USER]:[PASS]@', fixed_url)
        print(f"  {safe_fixed}")
        
    else:
        print("\n✓ DATABASE_URL appears correctly configured")
else:
    print("  DATABASE_URL: NOT SET!")

# Check Docker status
print("\n" + "-" * 60)
print("Docker Status Check:")
import subprocess

try:
    # Check if Docker is running
    result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}'], 
                          capture_output=True, text=True, timeout=5)
    
    if result.returncode == 0:
        output = result.stdout
        if 'foreportingv2-postgres' in output or 'postgres' in output:
            print("✓ PostgreSQL container is running")
            
            # Check if we can connect from host
            print("\nTesting connection from host to Docker PostgreSQL...")
            test_cmd = ['docker', 'exec', 'foreportingv2-postgres-1', 
                       'psql', '-U', 'system', '-d', 'foreporting_db', '-c', 'SELECT 1']
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                print("✓ Can connect to PostgreSQL in Docker")
            else:
                print("✗ Cannot connect to PostgreSQL in Docker")
                print(f"  Error: {result.stderr}")
        else:
            print("✗ PostgreSQL container NOT running")
            print("  Run: docker-compose up -d")
            print("\nRunning containers:")
            print(output)
    else:
        print("✗ Docker not available or not running")
        
except Exception as e:
    print(f"✗ Docker check failed: {e}")

# Summary
print("\n" + "=" * 60)
print("RECOMMENDATIONS:")
print("=" * 60)

if db_url and 'postgres:5432' in db_url and deployment_mode == 'local':
    print("\n1. You're running Python LOCALLY but DATABASE_URL points to Docker network")
    print("   Edit .env and change:")
    print("   FROM: postgres:5432")
    print("   TO:   localhost:5432")
    print("\n2. Make sure Docker PostgreSQL is running:")
    print("   docker-compose up -d")
    print("\n3. Then install dependencies and run tests:")
    print("   pip install pg8000==1.31.2")
    print("   python test_end_to_end.py")
    
elif deployment_mode == 'docker':
    print("\n1. You're in Docker mode, run everything inside Docker:")
    print("   docker-compose up -d")
    print("   docker-compose exec backend pip install -r requirements.txt")
    print("   docker-compose exec backend python test_end_to_end.py")
    
else:
    print("\n1. Ensure PostgreSQL is accessible")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Run tests: python test_end_to_end.py")

print("\n" + "=" * 60)