import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.community_repository import CommunityRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, get_current_user

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.post("/users/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def follow_user(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> None:
    """Create a follow relationship between the authenticated user and the target user. If the relationship already exists, the request succeeds silently without error. The target user posts will then appear in the authenticated user following feed."""
    repository = CommunityRepository()

    if str(current_user.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself.",
        )

    try:
        await repository.follow_user(
            database_session=database_session,
            follower_id=current_user.id,
            following_id=UUID(user_id),
        )
    except Exception:
        LOGGER.exception(
            "Failed to follow user_id=%s for follower_id=%s",
            user_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Could not follow user. Please try again or contact "
                "support if the problem persists."
            ),
        )


@router.delete("/users/{user_id}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> None:
    """Remove a follow relationship between the authenticated user and the target user. If the relationship does not exist, the request succeeds silently without error. The target user posts will no longer appear in the authenticated user following feed."""
    repository = CommunityRepository()

    try:
        await repository.unfollow_user(
            database_session=database_session,
            follower_id=current_user.id,
            following_id=UUID(user_id),
        )
    except Exception:
        LOGGER.exception(
            "Failed to unfollow user_id=%s for follower_id=%s",
            user_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Could not unfollow user. Please try again or contact "
                "support if the problem persists."
            ),
        )
