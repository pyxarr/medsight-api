# ruff: noqa: B008
import logging
from uuid import UUID as PythonUUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.notification_repository import NotificationRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, get_current_user
from api.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    """Return paginated notifications for the authenticated user."""
    notification_repository = NotificationRepository()

    try:
        total_notifications, notifications = await notification_repository.list_notifications(
            database_session=database_session,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except Exception:
        LOGGER.exception(
            "Failed to list notifications for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Notifications could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return NotificationListResponse(
        total=total_notifications,
        results=[NotificationResponse(**notification) for notification in notifications],
    )


@router.post("/notifications/read")
async def mark_all_notifications_read(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Mark all notifications as read for the authenticated user."""
    notification_repository = NotificationRepository()

    try:
        await notification_repository.mark_all_read(
            database_session=database_session,
            user_id=current_user.id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to mark all notifications read for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Notifications could not be updated. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return {"marked_read": True}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: PythonUUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Mark one notification as read for the authenticated user."""
    notification_repository = NotificationRepository()

    try:
        await notification_repository.mark_one_read(
            database_session=database_session,
            notification_id=notification_id,
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to mark notification_id=%s read for user_id=%s",
            notification_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Notification could not be updated. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return {"marked_read": True}


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
async def get_unread_notification_count(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Return the unread notification count for the authenticated user."""
    notification_repository = NotificationRepository()

    try:
        unread_count = await notification_repository.get_unread_count(
            database_session=database_session,
            user_id=current_user.id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load unread notification count for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unread notification count could not be loaded. Please try again "
                "or contact support if the problem persists."
            ),
        )

    return UnreadCountResponse(unread_count=unread_count)
