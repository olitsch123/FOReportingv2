from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
import os

# --- load .env so DATABASE_URL is available ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None  # no autogenerate in this phase

def get_url():
    # 1st: take DATABASE_URL from environment (.env loaded above)
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # 2nd: fall back to config only if non-empty and not a placeholder
    cfg_url = config.get_main_option("sqlalchemy.url") or ""
    if cfg_url and not cfg_url.startswith("driver://"):
        return cfg_url
    raise RuntimeError("DATABASE_URL missing. Set in .env or sqlalchemy.url with a real DSN (not 'driver://').")

def run_migrations_offline():
    context.configure(url=get_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(get_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
