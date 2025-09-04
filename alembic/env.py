from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
import os
from pathlib import Path

# --- robust .env load from project root (don't print secrets) ---
try:
    from dotenv import load_dotenv
    PROJECT_ROOT = Path(__file__).resolve().parents[1]   # ...\FOReportingv2
    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

# --- neutralize libpq config lookups under non-ASCII home ---
os.environ.setdefault("HOME", str(PROJECT_ROOT))                  # override "~"
os.environ.setdefault("PGSYSCONFDIR", str(PROJECT_ROOT))          # service file dir
os.environ.setdefault("PGPASSFILE", str(PROJECT_ROOT / ".pgpass"))# password file
os.environ.setdefault("PGCLIENTENCODING", "UTF8")                 # client encoding

# ensure .pgpass exists (can be empty)
try:
    (PROJECT_ROOT / ".pgpass").touch(exist_ok=True)
except Exception:
    pass

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None  # not using autogenerate here

def get_url():
    # Prefer env DATABASE_URL; fall back to ini only if not a dummy
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        # Use psycopg (v3) - the project's chosen driver
        if not url.startswith("postgresql+psycopg://"):
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://")
            elif url.startswith("postgresql+psycopg2://"):
                url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://")
        # Also handle deployment mode conversion
        deployment_mode = os.getenv("DEPLOYMENT_MODE", "local")
        if deployment_mode == "local" and "postgres:5432" in url:
            url = url.replace("postgres:5432", "localhost:5432")
        return url
    cfg_url = (config.get_main_option("sqlalchemy.url") or "").strip()
    if cfg_url and not cfg_url.startswith("driver://"):
        return cfg_url
    raise RuntimeError("DATABASE_URL missing. Put real DSN in .env or set sqlalchemy.url (not 'driver://').")

def run_migrations_offline():
    context.configure(url=get_url(), literal_binds=True, dialect_opts={"paramstyle":"named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    # Force UTF-8 via libpq options; robust on Windows with non-ASCII paths
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
        connect_args={
            "client_encoding": "utf8"
        }
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
