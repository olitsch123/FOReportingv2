from pathlib import Path
import os, yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Set UTF-8 encoding for Windows
os.environ.setdefault('PYTHONUTF8', '1')
load_dotenv(encoding='utf-8')  # do not print secrets

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
    reporting_ccy  = (rt.get("reporting_ccy") or "EUR").strip().upper()
    openai_cfg     = rt.get("openai") or {}
    ingestion_cfg  = rt.get("ingestion") or {}
    scoring_cfg    = rt.get("scoring") or {}
    tolerances_cfg = rt.get("tolerances") or {}

    settings = {
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
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_VECTOR_STORE_ID": os.getenv("OPENAI_VECTOR_STORE_ID"),
        "INVESTOR1_PATH": os.getenv("INVESTOR1_PATH"),
        "INVESTOR2_PATH": os.getenv("INVESTOR2_PATH"),
        "CHROMA_DIR": os.getenv("CHROMA_DIR"),
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
