from datetime import datetime
from decimal import Decimal
from uuid import UUID as PythonUUID
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class Assessment(Base):
    """Persist submitted assessment inputs and the generated result bundle."""
    __tablename__ = "assessments"

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    # Set the link to null instead of deleting the record so audit history survives even
    # if a related member or clinician account is later removed.
    clinician_user_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Set the link to null instead of deleting the record so assessment traceability is
    # preserved when the associated member profile no longer exists.
    member_user_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    patient_id: Mapped[str] = mapped_column(String, nullable=False)
    assessment_role: Mapped[str] = mapped_column(String, nullable=False)
    clinical_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    biopsy_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    blood_panel_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agreement: Mapped[str | None] = mapped_column(String, nullable=True)
    models_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    individual_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    clinical_guidance: Mapped[str | None] = mapped_column(String, nullable=True)
    key_risk_drivers: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    ood_warning: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Use a server-side timestamp so the persisted assessment time is authoritative even
    # if future writes come from background jobs or direct SQL tooling.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
