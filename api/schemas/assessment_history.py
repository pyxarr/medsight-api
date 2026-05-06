from datetime import datetime
from typing import Any
from uuid import UUID as PythonUUID

from pydantic import BaseModel, ConfigDict


class AssessmentHistorySummary(BaseModel):
    """Represent a summary entry in clinician assessment history."""

    model_config = ConfigDict(from_attributes=True)

    id: PythonUUID
    patient_id: str
    risk_level: str | None
    risk_score: float | None
    confidence_percent: int | None
    models_used: int | None
    agreement: str | None
    created_at: datetime


class AssessmentHistoryListResponse(BaseModel):
    """Represent a paginated clinician assessment history response."""

    total: int
    page: int
    page_size: int
    results: list[AssessmentHistorySummary]


class AssessmentHistoryDetailResponse(BaseModel):
    """Represent the full stored clinician assessment record."""

    model_config = ConfigDict(from_attributes=True)

    id: PythonUUID
    patient_id: str
    clinical_data: dict[str, Any]
    biopsy_data: dict[str, Any] | None
    blood_panel_data: dict[str, Any] | None
    risk_score: float | None
    risk_level: str | None
    confidence_percent: int | None
    agreement: str | None
    models_used: int | None
    individual_scores: dict[str, Any] | None
    clinical_guidance: str | None
    key_risk_drivers: list[dict[str, Any]] | dict[str, Any] | None
    ood_warning: dict[str, Any] | None
    created_at: datetime


class AssessmentDeleteResponse(BaseModel):
    """Represent a successful clinician assessment deletion response."""

    detail: str
