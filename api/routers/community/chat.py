# ruff: noqa: B008
import logging
from uuid import UUID as PythonUUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models.conversation import Conversation, DirectMessage
from api.db.repositories.conversation_repository import ConversationRepository
from api.db.repositories.notification_repository import NotificationRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, get_current_user
from api.models.user import User
from api.schemas.chat import (
    ConversationDetailResponse,
    ConversationResponse,
    MessageListResponse,
    MessageResponse,
    ParticipantInfo,
    SendMessageRequest,
    StartConversationRequest,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter()


def _serialise_participant(user_record: User) -> ParticipantInfo:
    """Convert one user record into a participant response."""
    return ParticipantInfo(
        id=user_record.id,
        display_name=user_record.display_name,
        username=user_record.username,
        avatar_url=user_record.avatar_url,
        role=user_record.role,
        is_verified=user_record.is_verified,
    )


async def _load_users_by_id(
    database_session: AsyncSession,
    user_ids: set[PythonUUID],
) -> dict[PythonUUID, User]:
    """Load multiple user records and return them keyed by identifier."""
    if not user_ids:
        return {}

    user_query = select(User).where(User.id.in_(list(user_ids)))
    user_result = await database_session.execute(user_query)
    return {user.id: user for user in user_result.scalars().all()}


def _get_other_participant_id(conversation: Conversation, current_user_id: PythonUUID) -> PythonUUID:
    """Return the other participant identifier for one conversation."""
    if conversation.member_user_id == current_user_id:
        return conversation.clinician_user_id

    return conversation.member_user_id


def _serialise_message(message_record: DirectMessage) -> MessageResponse:
    """Convert one direct message record into a message response."""
    return MessageResponse.model_validate(message_record)


@router.post("/conversations", response_model=ConversationResponse)
async def start_conversation(
    request: StartConversationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create or return one private conversation between a member and a clinician."""
    repository = ConversationRepository()

    other_user_query = select(User).where(User.id == request.other_user_id)
    other_user_result = await database_session.execute(other_user_query)
    other_user = other_user_result.scalar_one_or_none()

    if other_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if current_user.role == other_user.role or {
        current_user.role,
        other_user.role,
    } != {"member", "clinician"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A conversation requires one member and one clinician.",
        )

    if current_user.role == "member":
        member_user_id = current_user.id
        clinician_user_id = other_user.id
    else:
        member_user_id = other_user.id
        clinician_user_id = current_user.id

    try:
        conversation = await repository.get_or_create_conversation(
            database_session=database_session,
            member_user_id=member_user_id,
            clinician_user_id=clinician_user_id,
        )
        unread_count = await repository.get_unread_count(
            database_session=database_session,
            conversation_id=conversation.id,
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to start conversation for user_id=%s other_user_id=%s",
            current_user.id,
            request.other_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Conversation could not be started. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return ConversationResponse(
        id=conversation.id,
        other_participant=_serialise_participant(other_user),
        last_message_at=conversation.last_message_at,
        unread_count=unread_count,
        created_at=conversation.created_at,
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    """Return all conversations for the authenticated user ordered by recency."""
    repository = ConversationRepository()

    try:
        conversations_with_counts = await repository.list_conversations_for_user(
            database_session=database_session,
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to list conversations for user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Conversations could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    participant_ids = {
        conversation.clinician_user_id
        if conversation.member_user_id == current_user.id
        else conversation.member_user_id
        for conversation, _ in conversations_with_counts
    }
    participant_map = await _load_users_by_id(database_session, participant_ids)

    return [
        ConversationResponse(
            id=conversation.id,
            other_participant=_serialise_participant(
                participant_map[_get_other_participant_id(conversation, current_user.id)]
            ),
            last_message_at=conversation.last_message_at,
            unread_count=unread_count,
            created_at=conversation.created_at,
        )
        for conversation, unread_count in conversations_with_counts
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(
    conversation_id: PythonUUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """Return one conversation with its messages and clear its unread state."""
    repository = ConversationRepository()

    try:
        conversation = await repository.get_conversation_by_id(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=current_user.id,
        )
        _total_messages, messages = await repository.list_messages(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=current_user.id,
            limit=50,
            offset=0,
        )
        await repository.mark_conversation_read(
            database_session=database_session,
            conversation_id=conversation_id,
            reader_user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to load conversation_id=%s for user_id=%s",
            conversation_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Conversation could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    participant_map = await _load_users_by_id(
        database_session,
        {
            _get_other_participant_id(conversation, current_user.id),
        },
    )

    return ConversationDetailResponse(
        id=conversation.id,
        other_participant=_serialise_participant(
            participant_map[_get_other_participant_id(conversation, current_user.id)]
        ),
        messages=[_serialise_message(message) for message in messages],
        created_at=conversation.created_at,
    )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_direct_message(
    conversation_id: PythonUUID,
    request: SendMessageRequest,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send one direct message in an existing conversation."""
    repository = ConversationRepository()
    notification_repository = NotificationRepository()

    try:
        conversation = await repository.get_conversation_by_id(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=current_user.id,
        )
        message = await repository.send_message(
            database_session=database_session,
            conversation_id=conversation_id,
            sender_user_id=current_user.id,
            content=request.content,
            media_url=request.media_url,
            media_type=request.media_type,
        )
        other_participant_id = _get_other_participant_id(conversation, current_user.id)
        if other_participant_id != current_user.id:
            await notification_repository.create_notification(
                database_session=database_session,
                user_id=other_participant_id,
                type="message",
                actor_user_id=current_user.id,
                post_id=None,
                conversation_id=conversation_id,
            )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to send message in conversation_id=%s for user_id=%s",
            conversation_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Message could not be sent. Please try again or contact support "
                "if the problem persists."
            ),
        )

    other_participant_id = _get_other_participant_id(conversation, current_user.id)
    if other_participant_id != current_user.id:
        try:
            await notification_repository.create_notification(
                database_session=database_session,
                user_id=other_participant_id,
                type="message",
                actor_user_id=current_user.id,
                post_id=None,
                conversation_id=conversation_id,
            )
        except Exception:
            LOGGER.exception(
                "Failed to create message notification in conversation_id=%s from user_id=%s",
                conversation_id,
                current_user.id,
            )

    return _serialise_message(message)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def list_direct_messages(
    conversation_id: PythonUUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MessageListResponse:
    """Return paginated direct messages for one conversation."""
    repository = ConversationRepository()

    try:
        total_messages, messages = await repository.list_messages(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=current_user.id,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to list messages for conversation_id=%s user_id=%s",
            conversation_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Messages could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return MessageListResponse(
        total=total_messages,
        results=[_serialise_message(message) for message in messages],
    )


@router.post("/conversations/{conversation_id}/read")
async def mark_conversation_as_read(
    conversation_id: PythonUUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Mark one conversation as read for the authenticated user."""
    repository = ConversationRepository()

    try:
        await repository.mark_conversation_read(
            database_session=database_session,
            conversation_id=conversation_id,
            reader_user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to mark conversation_id=%s as read for user_id=%s",
            conversation_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Conversation could not be marked as read. Please try again or "
                "contact support if the problem persists."
            ),
        )

    return {"marked_read": True}
