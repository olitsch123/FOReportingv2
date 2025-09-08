"""Database connection and session management."""

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.config import load_settings

# Load settings
settings = load_settings()
logger = logging.getLogger(__name__)

# Create database engine (lazy initialization)
engine = None
SessionLocal = None

def init_database():
    """Initialize database connection (production-grade Windows safe)."""
    global engine, SessionLocal
    
    if engine is None:
        database_url = settings.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL not found in environment or config")
        
        # Standardize on psycopg3 format
        if "postgresql+psycopg2://" in database_url:
            database_url = database_url.replace("postgresql+psycopg2://", "postgresql+psycopg://")
        elif "postgresql+pg8000://" in database_url:
            database_url = database_url.replace("postgresql+pg8000://", "postgresql+psycopg://")
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://")
        
        logger.info(f"Using database URL format: {database_url.split('@')[0]}@[HIDDEN]")

        # Production-grade Windows UTF-8 handling
        import locale
        import sys

        # Force UTF-8 in current process
        if sys.platform == "win32":
            try:
                # Set locale to UTF-8 for Windows
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_ALL, 'C.UTF-8')
                except locale.Error:
                    pass  # Continue with system default
        
        # psycopg3 connection arguments - handles UTF-8 natively
        connect_args = {
            "application_name": "FOReporting_v2",
            "connect_timeout": 10,
            "options": "-c timezone=UTC"
        }
        
        try:
            engine = create_engine(
                database_url,
                future=True,  # SQLAlchemy 2.x style
                echo=settings.get("LOG_LEVEL") == "DEBUG",
                pool_pre_ping=True,
                pool_recycle=1800,  # 30 minutes
                pool_timeout=20,
                pool_size=10,
                max_overflow=20,
                connect_args=connect_args,
                # Production settings
                pool_reset_on_return='commit',
                # Isolation level for production
                isolation_level="READ_COMMITTED"
            )
            
            # Test the connection immediately
            from sqlalchemy import text
            with engine.connect() as test_conn:
                test_conn.execute(text("SELECT 1"))
                logger.info("Database connection test successful")
            
        except Exception as engine_error:
            logger.error(f"Database engine creation failed: {engine_error}")
            raise RuntimeError(f"Cannot create database engine: {engine_error}")

        # Create session factory (SQLAlchemy 2.x future style)
        SessionLocal = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            future=True
        )
        
        logger.info("Database engine and session factory created successfully")
    
    return engine, SessionLocal

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session."""
    try:
        init_database()
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    except Exception as e:
        # If database is not available, yield None
        # This allows endpoints to handle database unavailability gracefully
        raise RuntimeError(f"Database connection failed: {e}")


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database session."""
    try:
        init_database()
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}")


def test_connection():
    """Test database connection."""
    try:
        engine, _ = init_database()
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print("✓ Database connection successful!")
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


def get_engine():
    """Get the database engine."""
    engine, _ = init_database()
    return engine


def get_session():
    """Get a database session (compatibility wrapper)."""
    return get_db_session()