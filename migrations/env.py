"""
Alembic environment configuration.

Supports two modes:
  • Online (default) — uses a live database connection obtained from the
    DATABASE_URL environment variable via AppSettings.
  • Offline — generates SQL scripts without a live connection.

When invoked programmatically from `mindforge.infrastructure.db.run_migrations`,
the caller passes a synchronous connection via `config.attributes["connection"]`
and `run_migrations_online()` detects this path.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# SQLAlchemy metadata — import after package is installed so that this file
# works both when run by the Alembic CLI and when called programmatically.
# ---------------------------------------------------------------------------
try:
    from mindforge.infrastructure.persistence.models import Base  # noqa: F401

    target_metadata = Base.metadata
except ImportError:
    # Fallback during bootstrap when models may not yet be importable.
    target_metadata = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Resolve database URL
# ---------------------------------------------------------------------------


def _get_url() -> str:
    """
    Resolve the database URL.  Priority:
    1. Explicit value already set on config (e.g., from test fixture).
    2. DATABASE_URL environment variable.
    3. AppSettings (reads .env).
    """
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url

    url = os.environ.get("DATABASE_URL")
    if url:
        # asyncpg URLs must be downgraded to psycopg2 for synchronous Alembic
        return url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        from mindforge.infrastructure.config import load_settings

        settings = load_settings()
        return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    except Exception:
        raise RuntimeError(
            "Cannot determine DATABASE_URL for Alembic.  "
            "Set the DATABASE_URL environment variable or configure .env."
        )


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Programmatic path: caller passes its synchronous connection.
    passed_conn = config.attributes.get("connection")
    if passed_conn is not None:
        context.configure(
            connection=passed_conn,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    # CLI path: create a new synchronous engine from the resolved URL.
    cfg_section = config.get_section(config.config_ini_section) or {}
    cfg_section["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        cfg_section,
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
