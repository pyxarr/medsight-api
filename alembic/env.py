from logging.config import fileConfig
import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()

from api.db.base import Base, normalise_database_url
import api.models.assessment
import api.models.batch
import api.models.community
import api.models.notification
import api.models.patient
import api.models.user

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Reuse the same URL normalisation as the application so Alembic behaves predictably
# with copied Supabase URLs and passwords that contain reserved URL characters.
database_url = normalise_database_url(os.getenv("DATABASE_URL", "")) or ""
# Alembic runs synchronous migration code, so it must connect through psycopg2 rather
# than the asyncpg driver used by the running FastAPI application.
synchronous_database_url = database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")

if synchronous_database_url:
    config.set_main_option("sqlalchemy.url", synchronous_database_url.replace("%", "%%"))

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """Restrict schema discovery to the application schema used for product tables."""
    if type_ == "schema":
        return name in (None, "public")

    return True


def include_object(object_to_compare, object_name, object_type, reflected, compare_to):
    """Exclude metadata-only helper tables from autogeneration output."""
    if object_type == "table":
        # The auth.users stub exists only to resolve the foreign key target during metadata
        # sorting, so it must never appear as a create or drop operation in revisions.
        if not reflected and object_to_compare.schema == "auth" and object_name == "users":
            return False

    return True


def run_migrations_offline() -> None:
    """Configure Alembic for SQL script generation without a live connection."""
    context.configure(
        url=synchronous_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
        include_name=include_name,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live synchronous database connection."""
    configuration = config.get_section(config.config_ini_section, {})

    # Use NullPool because Alembic opens a short-lived administrative connection and
    # should not retain pooled connections after the migration command exits.
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
            include_name=include_name,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
