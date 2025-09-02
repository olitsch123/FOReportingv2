from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
import os

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = None  # we are not using autogenerate here

def get_url():
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("Set DATABASE_URL in your environment or sqlalchemy.url in alembic.ini")
    return url

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
