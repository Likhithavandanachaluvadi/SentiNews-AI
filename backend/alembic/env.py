"""
Alembic environment for async SQLAlchemy migrations.
This file runs migrations and supports both offline/online modes.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add backend root to path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from src.database.session import Base
from src.core.config import settings

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# set sqlalchemy.url from environment
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("+asyncpg", "")  # Convert async URL to sync for Alembic
)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (using raw SQL strings).
    This is useful for generating migration scripts without connecting to DB.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (with live DB connection).
    Most common mode for production deployments.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL.replace("+asyncpg", "")
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
