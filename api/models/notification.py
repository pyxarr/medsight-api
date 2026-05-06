from datetime import datetime
from uuid import UUID as PythonUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Notification(Base):
    """Persist user-facing notification messages and their read state."""
    __tablename__ = "notifications"

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    # Cascade here because a notification has no value once the owning user record is gone.
    user_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Use a different Python attribute name because metadata is reserved on declarative
    # models, while the database column still needs to remain named metadata.
    metadata_payload: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    # Use a server-side timestamp so notification creation time does not depend on the
    # application clock of whichever process inserted the row.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
