import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Set UTF-8 encoding for Windows
os.environ.setdefault('PYTHONUTF8', '1')
load_dotenv(encoding='utf-8')  # do not print secrets

def _get_deployment_mode() -> str:
    """Get deployment mode from environment."""
    return os.getenv("DEPLOYMENT_MODE", "local").lower()

def _get_database_url() -> str:
    """Get database URL based on deployment mode."""
    mode = _get_deployment_mode()
    if mode == "local":
        # Check if local override exists
        local_url = os.getenv("DATABASE_URL_LOCAL")
        if local_url:
            return local_url
        # Try to convert Docker URL to local (psycopg3 compatible)
        docker_url = os.getenv("DATABASE_URL", "")
        if "postgres:5432" in docker_url:
            # Convert to psycopg3 format
            return docker_url.replace("postgresql+psycopg2://", "postgresql://").replace("postgres:5432", "localhost:5432")
    return os.getenv("DATABASE_URL", "")

def _get_investor_path(investor_num: int) -> str:
    """Get investor path based on deployment mode."""
    mode = _get_deployment_mode()
    path_key = f"INVESTOR{investor_num}_PATH"
    host_key = f"INVESTOR{investor_num}_PATH_HOST"
    
    if mode == "docker":
        return os.getenv(host_key) or os.getenv(path_key, "")
    else:
        return os.getenv(path_key) or os.getenv(host_key, "")

def _get_chroma_dir() -> str:
    """Get Chroma directory based on deployment mode."""
    mode = _get_deployment_mode()
    if mode == "docker":
        return os.getenv("CHROMA_DIR", "/app/data/chroma")
    else:
        return os.getenv("CHROMA_DIR", "./data/chroma")

def _read_runtime_yaml() -> dict:
    p = BASE_DIR / "config" / "runtime.yaml"
    if p.exists():
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
            if isinstance(data, dict):
                return data
    return {}

def load_settings() -> dict:
    rt = _read_runtime_yaml()

    vector_backend = (rt.get("vector_backend") or "openai").strip().lower()
    reporting_ccy = (rt.get("reporting_ccy") or "EUR").strip().upper()
    openai_cfg = rt.get("openai") or {}
    ingestion_cfg = rt.get("ingestion") or {}
    scoring_cfg = rt.get("scoring") or {}
    tolerances_cfg = rt.get("tolerances") or {}

    settings = {
        # deployment configuration
        "DEPLOYMENT_MODE": _get_deployment_mode(),
        # tracked defaults
        "VECTOR_BACKEND": vector_backend,              # openai | chroma
        "REPORTING_CCY": reporting_ccy,
        # allow env to override runtime.yaml
        "OPENAI_LLM_MODEL": os.getenv("OPENAI_LLM_MODEL") or openai_cfg.get("llm_model", "gpt-4.1"),
        "OPENAI_EMBED_MODEL": os.getenv("OPENAI_EMBED_MODEL") or openai_cfg.get("embedding_model", "text-embedding-3-large"),
        "PE_SYNC_MODE": bool(ingestion_cfg.get("sync_mode", True)),
        "PE_RESCAN_CRON": ingestion_cfg.get("rescan_cron", "0 * * * *"),
        "SCORING": scoring_cfg,
        "TOLERANCES": tolerances_cfg,
        # secrets & paths (env ONLY)
        "DATABASE_URL": _get_database_url(),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_VECTOR_STORE_ID": os.getenv("OPENAI_VECTOR_STORE_ID"),
        "INVESTOR1_PATH": _get_investor_path(1),
        "INVESTOR2_PATH": _get_investor_path(2),
        "CHROMA_DIR": _get_chroma_dir(),
    }
    return settings

settings = load_settings()

def get_investor_from_path(file_path: str) -> str:
    """Determine which investor a file belongs to based on its path."""
    try:
        file_path = str(Path(file_path).absolute())
        
        investor1_path = settings.get("INVESTOR1_PATH", "")
        investor2_path = settings.get("INVESTOR2_PATH", "")
        
        # Handle UTF-8 paths safely
        if investor1_path:
            try:
                if file_path.startswith(investor1_path):
                    return "brainweb"
            except (UnicodeError, UnicodeDecodeError):
                pass
        
        if investor2_path:
            try:
                if file_path.startswith(investor2_path):
                    return "pecunalta"
            except (UnicodeError, UnicodeDecodeError):
                pass
        
        return "unknown"
    except Exception:
        return "unknown"
