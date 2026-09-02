import re
from uuid import UUID as PythonUUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.lib.auth import CurrentUser
from api.models.community import Follow
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

    async def update_profile(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
        display_name: str | None = None,
        username: str | None = None,
        institution: str | None = None,
        specialisation: str | None = None,
        experience_years: int | None = None,
        location: str | None = None,
    ) -> User:
        """Update profile fields (partial update). Handles display_name, username for all roles, and clinician fields for clinicians."""
        user = await self.get_by_id(database_session=database_session, user_id=user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        # Handle username update with uniqueness check
        if username is not None and username != user.username:
            existing = await self.get_by_username(
                database_session=database_session,
                username=username,
            )
            if existing is not None and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken.",
                )
            user.username = username

        # Handle display_name update
        if display_name is not None:
            if not display_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="display_name cannot be empty.",
                )
            user.display_name = display_name.strip()

        # Only update provided clinician fields — partial update
        if institution is not None:
            user.institution = institution
        if specialisation is not None:
            user.specialisation = specialisation
        if experience_years is not None:
            if experience_years < 0 or experience_years > 50:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="experience_years must be between 0 and 50.",
                )
            user.experience_years = experience_years
        if location is not None:
            user.location = location

        # Note: is_verified, medical_licence_number, licence_document_url
        # are intentionally NOT updated here (verification flow keeps them as-is).

        database_session.add(user)
        try:
            await database_session.flush()
        except IntegrityError:
            await database_session.rollback()
            # Re-check username uniqueness in case of race condition
            if username is not None:
                existing = await self.get_by_username(
                    database_session=database_session,
                    username=username,
                )
                if existing is not None and existing.id != user_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Username already taken.",
                    )
            raise

        await database_session.refresh(user)
        return user

    async def check_username_available(
        self,
        database_session: AsyncSession,
        username: str,
        exclude_user_id: PythonUUID,
    ) -> bool:
        """Return True if username is available for the given user (excluding their current username)."""
        existing = await self.get_by_username(
            database_session=database_session,
            username=username,
        )
        if existing is None:
            return True
        return existing.id == exclude_user_id

    async def submit_verification(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
        medical_licence_number: str,
        licence_document_url: str | None = None,
    ) -> User:
        """Record a clinician's licence credentials and persist the change."""
        user_query = select(User).where(User.id == user_id)
        user_result = await database_session.execute(user_query)
        user_record = user_result.scalar_one_or_none()

        if user_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        user_record.medical_licence_number = medical_licence_number
        # Leave an existing licence document link untouched when no new file is
        # supplied so a resubmission cannot silently clear the stored reference.
        if licence_document_url is not None:
            user_record.licence_document_url = licence_document_url

        database_session.add(user_record)
        await database_session.commit()
        await database_session.refresh(user_record)
        return user_record

    async def update_avatar(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
        avatar_url: str,
    ) -> User:
        """Persist a new avatar URL for one user and return the updated record."""
        user_query = select(User).where(User.id == user_id)
        user_result = await database_session.execute(user_query)
        user_record = user_result.scalar_one_or_none()

        if user_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        user_record.avatar_url = avatar_url

        database_session.add(user_record)
        await database_session.commit()
        await database_session.refresh(user_record)
        return user_record

    async def get_public_profile(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
        requesting_user_id: PythonUUID,
    ) -> tuple[User, int, int, bool]:
        """Return one user profile with follower and following counts and follow status."""
        user_query = select(User).where(User.id == user_id)
        user_result = await database_session.execute(user_query)
        user_record = user_result.scalar_one_or_none()

        if user_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        followers_count_query = (
            select(func.count())
            .select_from(Follow)
            .where(Follow.following_id == user_id)
        )
        followers_count_result = await database_session.execute(followers_count_query)
        followers_count = followers_count_result.scalar_one()

        following_count_query = (
            select(func.count())
            .select_from(Follow)
            .where(Follow.follower_id == user_id)
        )
        following_count_result = await database_session.execute(following_count_query)
        following_count = following_count_result.scalar_one()

        is_following_query = (
            select(func.count())
            .select_from(Follow)
            .where(
                Follow.follower_id == requesting_user_id,
                Follow.following_id == user_id,
            )
        )
        is_following_result = await database_session.execute(is_following_query)
        is_following = is_following_result.scalar_one() > 0

        return user_record, followers_count, following_count, is_following

    def _build_base_username(self, current_user: CurrentUser) -> str:
        """Build a stable username seed from auth claims."""
        raw_username = current_user.email.split("@", 1)[0]
        normalised_username = re.sub(r"[^a-z0-9]+", "_", raw_username.lower()).strip("_")
        return normalised_username or "user"
