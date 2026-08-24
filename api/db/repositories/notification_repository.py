from datetime import UTC, datetime
from uuid import UUID as PythonUUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models.conversation import DirectMessage
from api.db.models.notification import Notification
from api.models.community import CommunityPost
from api.models.user import User


class NotificationRepository:
    """Handle persistence and retrieval for user notifications."""

    async def create_notification(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
        type: str,
        actor_user_id: PythonUUID,
        post_id: PythonUUID | None,
        conversation_id: PythonUUID | None = None,
    ) -> Notification:
        """Insert one notification row and return the created record."""
        notification = Notification(
            user_id=user_id,
            type=type,
            actor_user_id=actor_user_id,
            post_id=post_id,
            conversation_id=conversation_id,
        )
        database_session.add(notification)
        await database_session.flush()
        await database_session.refresh(notification)
        return notification

    async def list_notifications(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict]]:
        """Return grouped notifications for one user with actor details and previews."""
        notification_query = (
            select(Notification, User)
            .join(User, User.id == Notification.actor_user_id)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        notification_result = await database_session.execute(notification_query)
        notification_rows = notification_result.all()

        if not notification_rows:
            return 0, []

        post_ids = {
            notification.post_id
            for notification, _ in notification_rows
            if notification.post_id is not None
        }
        conversation_ids = {
            notification.conversation_id
            for notification, _ in notification_rows
            if notification.conversation_id is not None
        }

        post_preview_map = await self._load_post_previews(
            database_session=database_session,
            post_ids=post_ids,
        )
        message_preview_map = await self._load_message_previews(
            database_session=database_session,
            conversation_ids=conversation_ids,
        )

        grouped_notifications: dict[tuple, dict] = {}
        grouped_order: list[tuple] = []

        for notification, actor_user in notification_rows:
            group_key = self._build_group_key(notification)
            group_entry = grouped_notifications.get(group_key)

            if group_entry is None:
                group_entry = self._build_group_entry(
                    notification=notification,
                    actor_user=actor_user,
                    post_preview_map=post_preview_map,
                    message_preview_map=message_preview_map,
                )
                grouped_notifications[group_key] = group_entry
                grouped_order.append(group_key)
                continue

            existing_actor_ids = {actor["id"] for actor in group_entry["users"]}
            if actor_user.id not in existing_actor_ids:
                group_entry["users"].append(self._build_actor_payload(actor_user))

            group_entry["is_read"] = group_entry["is_read"] and notification.is_read
            if notification.created_at > group_entry["created_at"]:
                group_entry["created_at"] = notification.created_at
                group_entry["time"] = self._format_relative_time(notification.created_at)

            if len(group_entry["users"]) > 1:
                group_entry["type"] = "grouped"
            group_entry["metrics"] = {"count": len(group_entry["users"])}
            if notification.type == "message":
                group_entry["content"] = message_preview_map.get(
                    (notification.conversation_id, notification.actor_user_id)
                )

        grouped_items = [grouped_notifications[group_key] for group_key in grouped_order]
        grouped_items.sort(key=lambda notification: notification["created_at"], reverse=True)

        paginated_items = grouped_items[offset: offset + limit]
        return len(grouped_items), paginated_items

    async def mark_all_read(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
    ) -> None:
        """Mark all unread notifications for one user as read."""
        await database_session.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )

    async def mark_one_read(
        self,
        database_session: AsyncSession,
        notification_id: PythonUUID,
        user_id: PythonUUID,
    ) -> None:
        """Mark one notification as read after verifying ownership."""
        notification_query = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        notification_result = await database_session.execute(notification_query)
        notification = notification_result.scalar_one_or_none()

        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )

        notification.is_read = True
        await database_session.flush()

    async def get_unread_count(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
    ) -> int:
        """Return the unread notification count for one user."""
        unread_count_query = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        unread_count_result = await database_session.execute(unread_count_query)
        return unread_count_result.scalar_one()

    async def _load_post_previews(
        self,
        database_session: AsyncSession,
        post_ids: set[PythonUUID],
    ) -> dict[PythonUUID, str | None]:
        """Load post previews keyed by post identifier."""
        if not post_ids:
            return {}

        post_query = select(CommunityPost.id, CommunityPost.content).where(
            CommunityPost.id.in_(list(post_ids))
        )
        post_result = await database_session.execute(post_query)
        return {post_id: content for post_id, content in post_result.all()}

    async def _load_message_previews(
        self,
        database_session: AsyncSession,
        conversation_ids: set[PythonUUID],
    ) -> dict[tuple[PythonUUID, PythonUUID], str | None]:
        """Load message previews keyed by conversation and sender identifiers."""
        if not conversation_ids:
            return {}

        message_query = (
            select(DirectMessage)
            .where(DirectMessage.conversation_id.in_(list(conversation_ids)))
            .order_by(DirectMessage.created_at.desc())
        )
        message_result = await database_session.execute(message_query)

        preview_map: dict[tuple[PythonUUID, PythonUUID], str | None] = {}
        for message in message_result.scalars().all():
            preview_key = (message.conversation_id, message.sender_user_id)
            if preview_key not in preview_map:
                preview_map[preview_key] = message.content

        return preview_map

    def _build_group_key(self, notification: Notification) -> tuple:
        """Build a grouping key for one notification row."""
        if notification.type == "message":
            return (notification.id,)

        if notification.type in {"like", "repost", "reply"} and notification.post_id is not None:
            return (notification.type, notification.post_id)

        if notification.type == "follow":
            return (notification.type,)

        return (notification.id,)

    def _build_group_entry(
        self,
        notification: Notification,
        actor_user: User,
        post_preview_map: dict[PythonUUID, str | None],
        message_preview_map: dict[tuple[PythonUUID, PythonUUID], str | None],
    ) -> dict:
        """Build one notification response payload from a database row."""
        return {
            "type": "single",
            "actionType": notification.type,
            "users": [self._build_actor_payload(actor_user)],
            "message": self._build_message_label(notification.type),
            "content": self._build_content_preview(
                notification=notification,
                post_preview_map=post_preview_map,
                message_preview_map=message_preview_map,
            ),
            "time": self._format_relative_time(notification.created_at),
            "post_id": notification.post_id,
            "conversation_id": notification.conversation_id,
            "is_read": notification.is_read,
            "created_at": notification.created_at,
            "metrics": None,
        }

    def _build_actor_payload(self, actor_user: User) -> dict:
        """Build one actor payload from a user record."""
        return {
            "id": actor_user.id,
            "display_name": actor_user.display_name,
            "username": actor_user.username,
            "avatar_url": actor_user.avatar_url,
            "role": actor_user.role,
            "is_verified": actor_user.is_verified,
        }

    def _build_message_label(self, notification_type: str) -> str:
        """Return a short notification label for the UI."""
        if notification_type == "follow":
            return "followed you"
        if notification_type == "like":
            return "liked your post"
        if notification_type == "repost":
            return "reposted your post"
        if notification_type == "reply":
            return "replied to your post"
        if notification_type == "message":
            return "sent you a message"

        return "updated you"

    def _build_content_preview(
        self,
        notification: Notification,
        post_preview_map: dict[PythonUUID, str | None],
        message_preview_map: dict[tuple[PythonUUID, PythonUUID], str | None],
    ) -> str | None:
        """Return a preview string for one notification when a preview is available."""
        if notification.type in {"like", "repost", "reply"} and notification.post_id is not None:
            return self._truncate_text(post_preview_map.get(notification.post_id))

        if notification.type == "message" and notification.conversation_id is not None:
            return self._truncate_text(
                message_preview_map.get((notification.conversation_id, notification.actor_user_id))
            )

        return None

    def _format_relative_time(self, created_at: datetime) -> str:
        """Format one timestamp as a short relative time string."""
        elapsed_seconds = int((datetime.now(UTC) - created_at).total_seconds())
        if elapsed_seconds < 60:
            return "just now"

        elapsed_minutes = elapsed_seconds // 60
        if elapsed_minutes < 60:
            return f"{elapsed_minutes}m ago"

        elapsed_hours = elapsed_minutes // 60
        if elapsed_hours < 24:
            return f"{elapsed_hours}h ago"

        elapsed_days = elapsed_hours // 24
        return f"{elapsed_days}d ago"

    def _truncate_text(self, content: str | None, limit: int = 120) -> str | None:
        """Truncate preview text to a concise UI-friendly length."""
        if content is None:
            return None

        if len(content) <= limit:
            return content

        return f"{content[: limit - 1].rstrip()}…"
