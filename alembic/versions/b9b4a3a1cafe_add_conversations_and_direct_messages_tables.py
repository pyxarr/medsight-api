"""add conversations and direct messages tables

Revision ID: b9b4a3a1cafe
Revises: 5f03e59af02c
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9b4a3a1cafe"
down_revision: Union[str, Sequence[str], None] = "5f03e59af02c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the conversation and direct message tables."""
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Cascade delete because the conversation has no meaning without the member.
        sa.Column("member_user_id", sa.UUID(), nullable=False),
        # Cascade delete because the conversation has no meaning without the clinician.
        sa.Column("clinician_user_id", sa.UUID(), nullable=False),
        # Keep creation time authoritative on the database clock.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["member_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clinician_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_user_id",
            "clinician_user_id",
            name="uq_member_clinician_conversation",
        ),
    )
    op.create_table(
        "direct_messages",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Messages belong entirely to their parent conversation.
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        # Messages should disappear with the sender account.
        sa.Column("sender_user_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("media_type", sa.Text(), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        # Keep message chronology authoritative on the database clock.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop the direct messaging tables in reverse dependency order."""
    op.drop_table("direct_messages")
    op.drop_table("conversations")
