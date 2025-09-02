"""Initialize the database with sample data."""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.database.connection import engine, Base, get_db_session
from app.database.models import Investor
from app.config import INVESTOR_FOLDERS


def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


def create_investors():
    """Create initial investor records."""
    print("Creating investor records...")
    
    investors_data = [
        {
            "name": "BrainWeb Investment GmbH",
            "code": "brainweb",
            "description": "BrainWeb Investment GmbH - Private Equity and Venture Capital",
            "folder_path": INVESTOR_FOLDERS.get("brainweb", "")
        },
        {
            "name": "pecunalta GmbH",
            "code": "pecunalta",
            "description": "pecunalta GmbH - Investment Management",
            "folder_path": INVESTOR_FOLDERS.get("pecunalta", "")
        }
    ]
    
    try:
        with get_db_session() as db:
            for investor_data in investors_data:
                # Check if investor already exists
                existing = db.query(Investor).filter(
                    Investor.code == investor_data["code"]
                ).first()
                
                if not existing:
                    investor = Investor(**investor_data)
                    db.add(investor)
                    print(f"✅ Created investor: {investor_data['name']}")
                else:
                    print(f"⚠️ Investor already exists: {investor_data['name']}")
            
            db.commit()
            
    except Exception as e:
        print(f"❌ Error creating investors: {str(e)}")


def main():
    """Main initialization function."""
    print("🚀 Initializing FOReporting v2 Database...")
    print("=" * 50)
    
    try:
        # Create tables
        create_tables()
        
        # Create investors
        create_investors()
        
        print("=" * 50)
        print("✅ Database initialization completed successfully!")
        print("\nNext steps:")
        print("1. Copy env_example.txt to .env and configure your settings")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Start the API server: python -m app.main")
        print("4. Start the dashboard: streamlit run app/frontend/dashboard.py")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()