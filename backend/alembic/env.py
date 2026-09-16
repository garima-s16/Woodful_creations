import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app` importable when alembic is run from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.platform.config import settings
from app.platform.database import Base
from app import models  # noqa: F401 - registers every model on Base.metadata

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False matters here specifically because
    # this env.py can now be triggered two ways: the standalone `alembic`
    # CLI (where wiping other loggers is harmless - nothing else is
    # running) and app.platform.database, called from inside the live
    # FastAPI app on every startup. Without this, fileConfig()'s default
    # behavior silently disables uvicorn's own logger as a side effect,
    # making the app look hung - it keeps running, it just stops
    # printing anything after the migration check runs.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Always use the live app settings, not a hardcoded url in alembic.ini -
# this is the same DATABASE_URL the app itself connects with, whether
# that's local SQLite or the docker-compose Postgres instance.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
