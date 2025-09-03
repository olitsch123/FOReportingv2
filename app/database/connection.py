"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from app.config import load_settings
import os

# Load settings
settings = load_settings()

# Create database engine
database_url = os.getenv("DATABASE_URL") or settings.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL not found in environment or config")

engine = create_engine(
    database_url,
    echo=settings.get("LOG_LEVEL") == "DEBUG",
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"options": "-c client_encoding=UTF8"}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()