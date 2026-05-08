from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssessmentDeleteResponse(BaseModel):
    """Represent a successful assessment delete response."""

    detail: str


class AssessmentHistorySummaryResponse(BaseModel):
    """Represent one clinician assessment summary row."""

    id: UUID
    patient_id: str
    first_name: str
    last_name: str
    patient_name: str
    risk_level: str | None
    risk_score: float | None
    confidence_percent: int | None
    created_at: datetime
    batch_id: UUID | None = None


class AssessmentHistoryListResponse(BaseModel):
    """Represent one paginated clinician assessment history page."""

    total: int
    page: int
    page_size: int
    results: list[AssessmentHistorySummaryResponse]


class AssessmentHistoryDetailResponse(BaseModel):
    """Represent one full clinician assessment history record."""

    id: UUID
    patient_id: str
    first_name: str
    last_name: str
    patient_name: str
    assessment_role: str
    clinical_data: dict
    biopsy_data: dict | None
    blood_panel_data: dict | None
    risk_score: float | None
    risk_level: str | None
    confidence_percent: int | None
    agreement: str | None
    models_used: int | None
    individual_scores: dict | None
    clinical_guidance: str | None
    key_risk_drivers: list[dict] | dict | None
    ood_warning: dict | None
    created_at: datetime
    batch_id: UUID | None = None


class BatchRowResult(BaseModel):
    """Represent the processing outcome for one batch CSV row."""

    row_index: int
    patient_id: str
    patient_name: str
    status: Literal["success", "failed"]
    result: dict | None = None
    error: str | None = None


class BatchSummaryResponse(BaseModel):
    """Represent one aggregate batch processing summary."""

    total: int
    success: int
    failed: int


class BatchAssessmentResponse(BaseModel):
    """Represent the response payload for one batch assessment upload."""

    batch_id: UUID
    summary: BatchSummaryResponse
    results: list[BatchRowResult]


class BatchInfoResponse(BaseModel):
    """Represent one clinician batch session summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_path: str
    total_records: int
    created_at: datetime


class BatchListResponse(BaseModel):
    """Represent a clinician batch history listing."""

    results: list[BatchInfoResponse]
