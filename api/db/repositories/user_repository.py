import re
from uuid import UUID as PythonUUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.lib.auth import CurrentUser
from api.models.user import User


class UserRepository:
    """Handle product-level user profile lookup and bootstrap operations."""

    async def get_by_id(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
    ) -> User | None:
        """Return one product user profile by UUID."""
        user_query = select(User).where(User.id == user_id)
        user_result = await database_session.execute(user_query)
        return user_result.scalar_one_or_none()

    async def get_by_username(
        self,
        database_session: AsyncSession,
        username: str,
    ) -> User | None:
        """Return one product user profile by username."""
        user_query = select(User).where(User.username == username)
        user_result = await database_session.execute(user_query)
        return user_result.scalar_one_or_none()

    async def create_from_auth_user(
        self,
        database_session: AsyncSession,
        current_user: CurrentUser,
    ) -> User:
        """Create one product user profile from authenticated Supabase claims."""
        user_uuid = current_user.id
        display_name = self._build_display_name(current_user)
        username = await self._generate_unique_username(
            database_session=database_session,
            current_user=current_user,
        )

        user_record = User(
            id=user_uuid,
            email=current_user.email,
            role=current_user.role,
            display_name=display_name,
            username=username,
            is_verified=False,
        )
        database_session.add(user_record)
        await database_session.flush()
        await database_session.refresh(user_record)
        return user_record

    async def get_or_create_from_auth_user(
        self,
        database_session: AsyncSession,
        current_user: CurrentUser,
    ) -> User:
        """Return an existing product user profile or create one from auth claims."""
        user_uuid = current_user.id
        existing_user = await self.get_by_id(
            database_session=database_session,
            user_id=user_uuid,
        )
        if existing_user is not None:
            return existing_user

        return await self.create_from_auth_user(
            database_session=database_session,
            current_user=current_user,
        )

    def _build_display_name(self, current_user: CurrentUser) -> str:
        """Build a display name from available auth claims."""
        name_parts = [
            name_part.strip()
            for name_part in [current_user.first_name, current_user.last_name]
            if name_part is not None and name_part.strip()
        ]
        if name_parts:
            return " ".join(name_parts)

        return current_user.email.split("@", 1)[0]

    async def _generate_unique_username(
        self,
        database_session: AsyncSession,
        current_user: CurrentUser,
    ) -> str:
        """Generate a unique username for a new product user profile."""
        base_username = self._build_base_username(current_user)
        candidate_username = base_username
        suffix = 1

        while await self.get_by_username(
            database_session=database_session,
            username=candidate_username,
        ) is not None:
            suffix += 1
            candidate_username = f"{base_username}{suffix}"

        return candidate_username

    def _build_base_username(self, current_user: CurrentUser) -> str:
        """Build a stable username seed from auth claims."""
        raw_username = current_user.email.split("@", 1)[0]
        normalised_username = re.sub(r"[^a-z0-9]+", "_", raw_username.lower()).strip("_")
        return normalised_username or "user"
