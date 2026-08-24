from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActorInfo(BaseModel):
    """Represent one actor in a notification entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    username: str
    avatar_url: str | None
    role: str
    is_verified: bool


class NotificationResponse(BaseModel):
    """Represent one grouped or single notification item for the UI."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    type: Literal["grouped", "single"]
    action_type: str = Field(alias="actionType")
    users: list[ActorInfo]
    message: str
    content: str | None = None
    time: str | None = None
    post_id: UUID | None = None
    conversation_id: UUID | None = None
    is_read: bool
    created_at: datetime
    metrics: dict[str, int] | None = None


class NotificationListResponse(BaseModel):
    """Represent a paginated notification list."""

    total: int
    results: list[NotificationResponse]


class UnreadCountResponse(BaseModel):
    """Represent the unread notification count."""

    unread_count: int
