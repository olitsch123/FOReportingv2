"""Configuration management for FOReporting v2."""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings."""
    
    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4-1106-preview"
    embedding_model: str = "text-embedding-3-small"
    
    # Database Configuration
    database_url: str
    
    # ChromaDB Configuration
    chroma_persist_directory: str = "./chroma_db"
    
    # Document Processing
    investor1_folder: str
    investor2_folder: str
    
    # API Configuration
    api_host: str = "localhost"
    api_port: int = 8000
    
    # Logging
    log_level: str = "INFO"
    
    # File Processing
    supported_extensions: List[str] = [".pdf", ".csv", ".xlsx", ".xls"]
    max_file_size_mb: int = 100
    
    # AI Processing
    max_tokens: int = 4000
    temperature: float = 0.1
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    @validator("investor1_folder", "investor2_folder")
    def validate_folder_paths(cls, v):
        """Validate that folder paths exist."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Folder path does not exist: {v}")
        return str(path.absolute())
    
    @validator("database_url")
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("Database URL must be a PostgreSQL connection string")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


# Folder mapping for investors
INVESTOR_FOLDERS = {
    "brainweb": settings.investor1_folder,
    "pecunalta": settings.investor2_folder,
}


def get_investor_from_path(file_path: str) -> Optional[str]:
    """Determine which investor a file belongs to based on its path."""
    file_path = Path(file_path).absolute()
    
    for investor, folder in INVESTOR_FOLDERS.items():
        if str(file_path).startswith(folder):
            return investor
    
    return None