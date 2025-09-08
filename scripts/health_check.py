"""Health check script for PE system acceptance."""
import os
from pathlib import Path

from app.config import settings
from app.database.connection import engine


def check_utf8_encoding():
    """Check database UTF-8 encoding."""
    try:
        with engine.connect() as conn:
            server_result = conn.execute("SHOW server_encoding").fetchone()
            client_result = conn.execute("SHOW client_encoding").fetchone()
            
            server_enc = server_result[0] if server_result else 'Unknown'
            client_enc = client_result[0] if client_result else 'Unknown'
            
            print(f"UTF-8 Health Check:")
            print(f"Server: {server_enc}")
            print(f"Client: {client_enc}")
            
            if server_enc == 'UTF8' and client_enc == 'UTF8':
                print("✅ UTF-8 encoding: OK")
                return True
            else:
                print("❌ UTF-8 encoding: FAIL")
                return False
                
    except Exception as e:
        print(f"❌ UTF-8 check failed: {e}")
        return False

def check_database_url():
    """Check DATABASE_URL format."""
    db_url = os.getenv('DATABASE_URL', '')
    
    if db_url.startswith('postgresql+psycopg2://'):
        print("✅ DB URL format: OK")
        return True
    else:
        print("❌ DB URL format: FAIL")
        return False

def check_pe_paths():
    """Check PE investor paths."""
    investor1_path = settings.get('INVESTOR1_PATH')
    investor2_path = settings.get('INVESTOR2_PATH')
    
    paths_ok = True
    
    if investor1_path:
        if Path(investor1_path).exists():
            print(f"✅ INVESTOR1_PATH exists: {investor1_path}")
        else:
            print(f"❌ INVESTOR1_PATH missing: {investor1_path}")
            paths_ok = False
    else:
        print("⚠️  INVESTOR1_PATH not configured")
    
    if investor2_path:
        if Path(investor2_path).exists():
            print(f"✅ INVESTOR2_PATH exists: {investor2_path}")
        else:
            print(f"❌ INVESTOR2_PATH missing: {investor2_path}")
            paths_ok = False
    else:
        print("⚠️  INVESTOR2_PATH not configured")
    
    return paths_ok

def main():
    """Run all health checks."""
    print("🔍 PE System Health Check")
    print("=" * 40)
    
    checks = [
        check_utf8_encoding(),
        check_database_url(),
        check_pe_paths()
    ]
    
    if all(checks):
        print("\\n🎉 All health checks passed!")
        return True
    else:
        print("\\n❌ Some health checks failed")
        return False

if __name__ == '__main__':
    main()