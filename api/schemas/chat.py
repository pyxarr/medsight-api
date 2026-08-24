from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class StartConversationRequest(BaseModel):
    """Describe the user that should be opened in a new direct conversation."""

    model_config = ConfigDict(from_attributes=True)

    other_user_id: UUID


class SendMessageRequest(BaseModel):
    """Describe a direct message payload with optional media support."""

    model_config = ConfigDict(from_attributes=True)

    content: str | None = None
    media_url: str | None = None
    media_type: str | None = None

    @model_validator(mode="after")
    def ensure_content_or_media(self) -> "SendMessageRequest":
        """Require either message text or media to be present."""
        if not self.content and not self.media_url:
            raise ValueError("Either content or media_url must be provided.")

        return self


class MessageResponse(BaseModel):
    """Represent one direct message inside a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    sender_user_id: UUID
    content: str | None
    media_url: str | None
    media_type: str | None
    is_read: bool
    created_at: datetime


class ParticipantInfo(BaseModel):
    """Represent the public profile details for a chat participant."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    username: str
    avatar_url: str | None
    role: str
    is_verified: bool


class ConversationResponse(BaseModel):
    """Represent one conversation summary for a conversation list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    other_participant: ParticipantInfo
    last_message_at: datetime | None
    unread_count: int
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    """Represent one conversation with its message history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    other_participant: ParticipantInfo
    messages: list[MessageResponse]
    created_at: datetime


class MessageListResponse(BaseModel):
    """Represent a paginated list of direct messages."""

    total: int
    results: list[MessageResponse]
