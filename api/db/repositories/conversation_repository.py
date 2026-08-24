from uuid import UUID as PythonUUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models.conversation import Conversation, DirectMessage


class ConversationRepository:
    """Handle private conversation and direct message persistence."""

    async def _get_participant_conversation(
        self,
        database_session: AsyncSession,
        conversation_id: PythonUUID,
        requesting_user_id: PythonUUID,
    ) -> Conversation:
        """Return one conversation only when the requester is a participant."""
        conversation_query = select(Conversation).where(Conversation.id == conversation_id)
        conversation_result = await database_session.execute(conversation_query)
        conversation = conversation_result.scalar_one_or_none()

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        if requesting_user_id not in (
            conversation.member_user_id,
            conversation.clinician_user_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorised to access this conversation.",
            )

        return conversation

    async def get_or_create_conversation(
        self,
        database_session: AsyncSession,
        member_user_id: PythonUUID,
        clinician_user_id: PythonUUID,
    ) -> Conversation:
        """Return the existing conversation for one member and clinician pair or create it."""
        if member_user_id == clinician_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A conversation requires one member and one clinician.",
            )

        conversation_query = select(Conversation).where(
            Conversation.member_user_id == member_user_id,
            Conversation.clinician_user_id == clinician_user_id,
        )
        conversation_result = await database_session.execute(conversation_query)
        conversation = conversation_result.scalar_one_or_none()
        if conversation is not None:
            return conversation

        conversation = Conversation(
            member_user_id=member_user_id,
            clinician_user_id=clinician_user_id,
        )
        database_session.add(conversation)

        try:
            await database_session.flush()
        except IntegrityError:
            await database_session.rollback()
            conversation_result = await database_session.execute(conversation_query)
            conversation = conversation_result.scalar_one_or_none()
            if conversation is None:
                raise

        await database_session.refresh(conversation)
        return conversation

    async def get_conversation_by_id(
        self,
        database_session: AsyncSession,
        conversation_id: PythonUUID,
        requesting_user_id: PythonUUID,
    ) -> Conversation:
        """Return one conversation when the requester participates in it."""
        return await self._get_participant_conversation(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=requesting_user_id,
        )

    async def list_conversations_for_user(
        self,
        database_session: AsyncSession,
        user_id: PythonUUID,
    ) -> list[tuple[Conversation, int]]:
        """Return all conversations for one user with unread message counts."""
        conversation_query = select(Conversation).where(
            or_(
                Conversation.member_user_id == user_id,
                Conversation.clinician_user_id == user_id,
            )
        ).order_by(
            Conversation.last_message_at.desc().nullslast(),
            Conversation.created_at.desc(),
        )
        conversation_result = await database_session.execute(conversation_query)
        conversations = list(conversation_result.scalars().all())

        if not conversations:
            return []

        conversation_ids = [conversation.id for conversation in conversations]
        unread_count_query = select(
            DirectMessage.conversation_id,
            func.count(),
        ).where(
            DirectMessage.conversation_id.in_(conversation_ids),
            DirectMessage.sender_user_id != user_id,
            DirectMessage.is_read.is_(False),
        ).group_by(DirectMessage.conversation_id)
        unread_count_result = await database_session.execute(unread_count_query)
        unread_counts = {
            conversation_id: unread_count
            for conversation_id, unread_count in unread_count_result.all()
        }

        return [
            (conversation, unread_counts.get(conversation.id, 0))
            for conversation in conversations
        ]

    async def send_message(
        self,
        database_session: AsyncSession,
        conversation_id: PythonUUID,
        sender_user_id: PythonUUID,
        content: str | None,
        media_url: str | None,
        media_type: str | None,
    ) -> DirectMessage:
        """Insert one direct message and update the conversation recency timestamp."""
        await self._get_participant_conversation(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=sender_user_id,
        )

        direct_message = DirectMessage(
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            content=content,
            media_url=media_url,
            media_type=media_type,
        )
        database_session.add(direct_message)
        await database_session.flush()
        await database_session.refresh(direct_message)

        await database_session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(last_message_at=func.now())
        )

        return direct_message

    async def list_messages(
        self,
        database_session: AsyncSession,
        conversation_id: PythonUUID,
        requesting_user_id: PythonUUID,
        limit: int,
        offset: int,
    ) -> tuple[int, list[DirectMessage]]:
        """Return paginated messages for one conversation after checking access."""
        await self._get_participant_conversation(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=requesting_user_id,
        )

        total_query = select(func.count()).select_from(DirectMessage).where(
            DirectMessage.conversation_id == conversation_id,
        )
        total_result = await database_session.execute(total_query)
        total_messages = total_result.scalar_one()

        message_query = (
            select(DirectMessage)
            .where(DirectMessage.conversation_id == conversation_id)
            .order_by(DirectMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        message_result = await database_session.execute(message_query)
        messages = list(message_result.scalars().all())

        return total_messages, messages

    async def mark_conversation_read(
        self,
        database_session: AsyncSession,
        conversation_id: PythonUUID,
        reader_user_id: PythonUUID,
    ) -> None:
        """Mark all unread messages from the other participant as read."""
        await self._get_participant_conversation(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=reader_user_id,
        )

        await database_session.execute(
            update(DirectMessage)
            .where(
                DirectMessage.conversation_id == conversation_id,
                DirectMessage.sender_user_id != reader_user_id,
                DirectMessage.is_read.is_(False),
            )
            .values(is_read=True)
        )

    async def get_unread_count(
        self,
        database_session: AsyncSession,
        conversation_id: PythonUUID,
        user_id: PythonUUID,
    ) -> int:
        """Return the unread message count for one participant in one conversation."""
        await self._get_participant_conversation(
            database_session=database_session,
            conversation_id=conversation_id,
            requesting_user_id=user_id,
        )

        unread_count_query = select(func.count()).select_from(DirectMessage).where(
            DirectMessage.conversation_id == conversation_id,
            DirectMessage.sender_user_id != user_id,
            DirectMessage.is_read.is_(False),
        )
        unread_count_result = await database_session.execute(unread_count_query)
        return unread_count_result.scalar_one()
