from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
import os
from pathlib import Path

# Load .env from repo root (don't print secrets)
try:
    from dotenv import load_dotenv
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None

def get_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    cfg_url = (config.get_main_option("sqlalchemy.url") or "").strip()
    if cfg_url and not cfg_url.startswith("driver://"):
        return cfg_url
    raise RuntimeError("DATABASE_URL missing. Put real DSN in .env or set sqlalchemy.url (not 'driver://').")

def run_migrations_offline():
    context.configure(url=get_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    # Create engine with database-specific settings
    url = get_url()
    if url.startswith("postgresql"):
        # Pass UTF-8 option to Postgres explicitly (robust on Windows with non-ASCII paths)
        connectable = create_engine(
            url,
            poolclass=pool.NullPool,
            connect_args={"options": "-c client_encoding=UTF8"}
        )
    else:
        # For SQLite and other databases
        connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
