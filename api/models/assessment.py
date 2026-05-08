from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID as PythonUUID

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base


if TYPE_CHECKING:
    from api.models.batch import Batch
    from api.models.patient import Patient


class Assessment(Base):
    """Persist submitted assessment inputs and the generated result bundle."""

    __tablename__ = "assessments"

    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
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
    # Link to the patient profile to maintain a consistent identity across assessments.
    patient_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The human-readable identifier (e.g., P-2024-001) stored for fast retrieval and display.
    patient_external_id: Mapped[str] = mapped_column(String, nullable=False)
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
    # Link to the batch upload session if this record was created via CSV.
    batch_id: Mapped[PythonUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Use a server-side timestamp so the persisted assessment time is authoritative even
    # if future writes come from background jobs or direct SQL tooling.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    patient: Mapped["Patient"] = relationship(back_populates="assessments")
    batch: Mapped["Batch | None"] = relationship(back_populates="assessments")
