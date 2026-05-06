import os

from sqlalchemy import Column, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


def normalise_database_url(raw_database_url: str | None) -> str | None:
    """Normalise the configured database URL for async SQLAlchemy use."""
    if not raw_database_url:
        return raw_database_url

    # Accept a sync driver string here because Alembic and copied connection strings
    # often use it, while the application session layer must always use asyncpg.
    if raw_database_url.startswith("postgresql+psycopg2"):
        raw_database_url = raw_database_url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)

    # Accept the plain PostgreSQL scheme because Supabase examples and dashboard values
    # may omit the async driver even when the backend needs one.
    if raw_database_url.startswith("postgresql://"):
        raw_database_url = raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Encode any @ characters inside the password so host parsing remains stable.
    scheme_and_credentials, separator, host_and_path = raw_database_url.rpartition("@")
    if separator and "://" in scheme_and_credentials:
        connection_scheme, credentials = scheme_and_credentials.split("://", 1)
        credentials = credentials.replace("@", "%40")
        return f"{connection_scheme}://{credentials}@{host_and_path}"

    return raw_database_url


database_url = normalise_database_url(os.getenv("DATABASE_URL"))

# Keep loaded ORM instances usable after commit because async request handlers commonly
# return serialised data immediately after the transaction closes.
engine = create_async_engine(database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Provide the shared declarative base for all ORM models."""
    pass


# Register a minimal external table reference so SQLAlchemy can resolve the foreign key
# to Supabase Auth users during metadata sorting and Alembic autogeneration.
Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
)
