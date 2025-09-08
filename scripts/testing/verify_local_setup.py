"""Verify local setup and write results to file."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

results = {
    'timestamp': datetime.now().isoformat(),
    'checks': {},
    'ready': False
}

def check_env_file():
    """Check .env configuration."""
    env_path = Path('.env')
    if not env_path.exists():
        return False, ".env file not found"
    
    with open(env_path, 'r') as f:
        content = f.read()
    
    checks = {
        'localhost_db': 'localhost:5432' in content,
        'deployment_mode': 'DEPLOYMENT_MODE=local' in content,
        'has_api_key': 'OPENAI_API_KEY=' in content and 'your-api-key-here' not in content,
        'has_db_password': 'BreslauerPlatz4' in content
    }
    
    if not checks['localhost_db']:
        return False, "DATABASE_URL not set for localhost"
    if not checks['deployment_mode']:
        return False, "DEPLOYMENT_MODE not set to local"
    if not checks['has_api_key']:
        return False, "OPENAI_API_KEY not configured"
    
    return True, "All environment variables correctly configured"

def check_postgresql():
    """Check if PostgreSQL is running locally."""
    try:
        result = subprocess.run([
            'psql', '-h', 'localhost', '-p', '5432', '-U', 'postgres',
            '-c', 'SELECT 1;'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            return True, "PostgreSQL is running on localhost:5432"
        else:
            return False, f"PostgreSQL connection failed: {result.stderr}"
    except FileNotFoundError:
        return False, "psql command not found - PostgreSQL may not be installed"
    except Exception as e:
        return False, f"PostgreSQL check failed: {str(e)}"

def check_database():
    """Check if foreporting_db exists."""
    try:
        result = subprocess.run([
            'psql', '-h', 'localhost', '-p', '5432', '-U', 'system',
            '-d', 'foreporting_db', '-c', 'SELECT 1;'
        ], capture_output=True, text=True, timeout=5, 
        env={**os.environ, 'PGPASSWORD': 'BreslauerPlatz4'})
        
        if result.returncode == 0:
            return True, "Database foreporting_db exists and is accessible"
        else:
            return False, "Cannot connect to foreporting_db"
    except Exception as e:
        return False, f"Database check failed: {str(e)}"

def check_python_deps():
    """Check if key Python dependencies are installed."""
    missing = []
    deps = ['fastapi', 'sqlalchemy', 'alembic', 'pg8000', 'streamlit', 'pandas']
    
    for dep in deps:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)
    
    if missing:
        return False, f"Missing dependencies: {', '.join(missing)}"
    return True, "All key dependencies installed"

def check_pe_modules():
    """Check if PE modules can be imported."""
    try:
        from app.pe_docs.extractors.multi_method import MultiMethodExtractor
        from app.pe_docs.storage.orm import PEStorageORM
        from app.pe_docs.validation import DocumentValidator
        return True, "All PE modules can be imported"
    except Exception as e:
        return False, f"PE module import failed: {str(e)}"

def check_alembic_status():
    """Check Alembic migration status."""
    try:
        result = subprocess.run([
            'alembic', 'current'
        ], capture_output=True, text=True, timeout=10,
        env={**os.environ, 'DEPLOYMENT_MODE': 'local'})
        
        if result.returncode == 0:
            if 'pe_enhanced_001' in result.stdout:
                return True, "All migrations applied including PE schema"
            elif result.stdout.strip():
                return False, f"Migrations incomplete: {result.stdout.strip()}"
            else:
                return False, "No migrations applied yet"
        else:
            return False, f"Alembic check failed: {result.stderr}"
    except Exception as e:
        return False, f"Alembic status check failed: {str(e)}"

# Run all checks
print("Running local setup verification...")

checks = [
    ('Environment Config', check_env_file),
    ('PostgreSQL Service', check_postgresql),
    ('Database Access', check_database),
    ('Python Dependencies', check_python_deps),
    ('PE Modules', check_pe_modules),
    ('Database Migrations', check_alembic_status)
]

all_passed = True
for name, check_func in checks:
    try:
        passed, message = check_func()
        results['checks'][name] = {
            'passed': passed,
            'message': message
        }
        if not passed:
            all_passed = False
        print(f"{'✓' if passed else '✗'} {name}: {message}")
    except Exception as e:
        results['checks'][name] = {
            'passed': False,
            'message': f"Check failed: {str(e)}"
        }
        all_passed = False
        print(f"✗ {name}: Check failed - {str(e)}")

results['ready'] = all_passed

# Write results to file
with open('local_setup_status.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'✅ Local setup is READY!' if all_passed else '❌ Local setup needs attention'}")
print("\nDetailed results saved to: local_setup_status.json")

if not all_passed:
    print("\nTo fix issues:")
    print("1. Run: setup_local_windows.bat")
    print("2. Follow any error messages")
    print("3. Run this verification again")