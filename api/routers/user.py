import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.user_repository import UserRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, get_current_user
from api.schemas.user import UserProfileResponse

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Return the current product user profile and bootstrap it when missing."""
    user_repository = UserRepository()

    try:
        user_record = await user_repository.get_or_create_from_auth_user(
            database_session=database_session,
            current_user=current_user,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load or create product user profile for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "User profile could not be loaded. Please try again or contact support "
                "if the problem persists."
            ),
        )

    return UserProfileResponse.model_validate(user_record)
