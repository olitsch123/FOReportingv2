from pathlib import Path
import os, yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv()  # do not print secrets

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
        "OPENAI_LLM_MODEL": openai_cfg.get("llm_model", "gpt-4.1"),
        "OPENAI_EMBED_MODEL": openai_cfg.get("embedding_model", "text-embedding-3-large"),
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
