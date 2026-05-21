from datetime import datetime
from uuid import UUID as PythonUUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class CommunityPost(Base):
    """Represent a community feed item or a reply to another post via a self-referencing link."""

    __tablename__ = "community_posts"

    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    # Cascade delete so all posts and replies disappear when the author account is removed.
    author_user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(String, nullable=False)
    media_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Cascade delete replies when their parent post is removed so orphaned replies cannot exist.
    parent_post_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("community_posts.id", ondelete="CASCADE"),
        nullable=True,
    )
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    # Use a server-side timestamp so the creation time is authoritative regardless of which
    # application instance inserts the row.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CommunityReaction(Base):
    """Track a single user's reaction to a specific post, preventing duplicate reactions per type."""

    __tablename__ = "community_reactions"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", "reaction_type", name="uq_post_user_reaction"),
    )

    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    # Cascade delete because reactions have no meaning without the parent post.
    post_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("community_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Cascade delete because reactions have no meaning without the user who created them.
    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reaction_type: Mapped[str] = mapped_column(String, nullable=False)
    # Use a server-side timestamp so the reaction time is authoritative regardless of which
    # application instance inserts the row.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Follow(Base):
    """Record a follower-following relationship between two users, preventing duplicate pairs."""

    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_follower_following"),
    )

    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    # Cascade delete so the follow relationship is removed when the follower account is deleted.
    follower_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Cascade delete so the follow relationship is removed when the followed account is deleted.
    following_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Use a server-side timestamp so the follow time is authoritative regardless of which
    # application instance inserts the row.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
