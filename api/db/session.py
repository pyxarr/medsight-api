from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped database session and finalise the transaction safely."""
    database_session = AsyncSessionLocal()

    try:
        yield database_session
        # Commit here so route handlers can stay focused on business logic while each
        # request still gets one clear transaction boundary.
        await database_session.commit()
    except Exception:
        # Roll back on any failure so a partially written assessment or profile change
        # never leaks across requests.
        await database_session.rollback()
        raise
    finally:
        await database_session.close()
