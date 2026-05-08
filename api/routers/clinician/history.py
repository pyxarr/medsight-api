import logging
from datetime import date
from typing import Literal
from uuid import UUID as PythonUUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.assessment_repository import (
    get_clinician_assessment,
    list_batch_assessments,
    list_clinician_assessments,
    list_patient_assessments,
    soft_delete_clinician_assessment,
)
from api.db.repositories.batch_repository import BatchRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, require_role
from api.schemas.assessment_history import (
    AssessmentDeleteResponse,
    AssessmentHistoryDetailResponse,
    AssessmentHistoryListResponse,
    AssessmentHistorySummaryResponse,
    BatchInfoResponse,
    BatchListResponse,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter()


def _build_patient_name(first_name: str, last_name: str) -> str:
    """Return one display-safe patient name."""
    return f"{first_name} {last_name}".strip()


def _serialise_assessment_summary(assessment_record) -> AssessmentHistorySummaryResponse:
    """Convert one ORM assessment record into a summary response."""
    patient_record = assessment_record.patient
    return AssessmentHistorySummaryResponse(
        id=assessment_record.id,
        patient_id=assessment_record.patient_external_id,
        first_name=patient_record.first_name,
        last_name=patient_record.last_name,
        patient_name=_build_patient_name(patient_record.first_name, patient_record.last_name),
        risk_level=assessment_record.risk_level,
        risk_score=(
            float(assessment_record.risk_score)
            if assessment_record.risk_score is not None
            else None
        ),
        confidence_percent=assessment_record.confidence_percent,
        created_at=assessment_record.created_at,
        batch_id=assessment_record.batch_id,
    )


def _serialise_assessment_detail(assessment_record) -> AssessmentHistoryDetailResponse:
    """Convert one ORM assessment record into a detail response."""
    patient_record = assessment_record.patient
    return AssessmentHistoryDetailResponse(
        id=assessment_record.id,
        patient_id=assessment_record.patient_external_id,
        first_name=patient_record.first_name,
        last_name=patient_record.last_name,
        patient_name=_build_patient_name(patient_record.first_name, patient_record.last_name),
        assessment_role=assessment_record.assessment_role,
        clinical_data=assessment_record.clinical_data,
        biopsy_data=assessment_record.biopsy_data,
        blood_panel_data=assessment_record.blood_panel_data,
        risk_score=(
            float(assessment_record.risk_score)
            if assessment_record.risk_score is not None
            else None
        ),
        risk_level=assessment_record.risk_level,
        confidence_percent=assessment_record.confidence_percent,
        agreement=assessment_record.agreement,
        models_used=assessment_record.models_used,
        individual_scores=assessment_record.individual_scores,
        clinical_guidance=assessment_record.clinical_guidance,
        key_risk_drivers=assessment_record.key_risk_drivers,
        ood_warning=assessment_record.ood_warning,
        created_at=assessment_record.created_at,
        batch_id=assessment_record.batch_id,
    )


@router.get(
    "/assessments",
    response_model=AssessmentHistoryListResponse,
)
async def list_clinician_assessment_history(
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
    patient_id: str | None = Query(default=None),
    patient_name: str | None = Query(default=None),
    risk_level: Literal["Low", "Medium", "High"] | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AssessmentHistoryListResponse:
    """Return a paginated clinician assessment history page."""
    try:
        total_assessments, assessment_records = await list_clinician_assessments(
            database_session=database_session,
            clinician_user_id=current_user.id,
            patient_external_id=patient_id,
            patient_name=patient_name,
            risk_level=risk_level,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load assessment history for clinician_user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Assessment history could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return AssessmentHistoryListResponse(
        total=total_assessments,
        page=page,
        page_size=page_size,
        results=[
            _serialise_assessment_summary(assessment_record)
            for assessment_record in assessment_records
        ],
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentHistoryDetailResponse,
)
async def get_clinician_assessment_detail(
    assessment_id: PythonUUID,
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
) -> AssessmentHistoryDetailResponse:
    """Return one clinician assessment history record."""
    try:
        assessment_record = await get_clinician_assessment(
            database_session=database_session,
            clinician_user_id=current_user.id,
            assessment_id=assessment_id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load assessment_id=%s for clinician_user_id=%s",
            assessment_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Assessment could not be loaded. Please try again or contact support "
                "if the problem persists."
            ),
        )

    if assessment_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found.",
        )

    return _serialise_assessment_detail(assessment_record)


@router.get(
    "/patients/{patient_id}/history",
    response_model=AssessmentHistoryListResponse,
)
async def get_patient_assessment_history(
    patient_id: str,
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
) -> AssessmentHistoryListResponse:
    """Return the full assessment timeline for one patient identifier."""
    try:
        assessment_records = await list_patient_assessments(
            database_session=database_session,
            clinician_user_id=current_user.id,
            patient_external_id=patient_id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load patient history for patient_id=%s clinician_user_id=%s",
            patient_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Patient history could not be loaded. Please try again or contact support "
                "if the problem persists."
            ),
        )

    return AssessmentHistoryListResponse(
        total=len(assessment_records),
        page=1,
        page_size=len(assessment_records),
        results=[
            _serialise_assessment_summary(assessment_record)
            for assessment_record in assessment_records
        ],
    )


@router.get(
    "/batches",
    response_model=BatchListResponse,
)
async def list_clinician_batches(
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
) -> BatchListResponse:
    """Return all batch uploads created by the current clinician."""
    batch_repository = BatchRepository()

    try:
        batch_records = await batch_repository.list_batches(
            database_session=database_session,
            clinician_user_id=current_user.id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load batch history for clinician_user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Batch history could not be loaded. Please try again or contact support "
                "if the problem persists."
            ),
        )

    return BatchListResponse(
        results=[BatchInfoResponse.model_validate(batch_record) for batch_record in batch_records]
    )


@router.get(
    "/batches/{batch_id}/assessments",
    response_model=AssessmentHistoryListResponse,
)
async def list_batch_assessment_history(
    batch_id: PythonUUID,
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
) -> AssessmentHistoryListResponse:
    """Return all assessments linked to one clinician batch."""
    batch_repository = BatchRepository()

    try:
        batch_record = await batch_repository.get_batch(
            database_session=database_session,
            clinician_user_id=current_user.id,
            batch_id=batch_id,
        )
        if batch_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found.",
            )

        assessment_records = await list_batch_assessments(
            database_session=database_session,
            clinician_user_id=current_user.id,
            batch_id=batch_id,
        )
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception(
            "Failed to load batch assessments for batch_id=%s clinician_user_id=%s",
            batch_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Batch assessments could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    return AssessmentHistoryListResponse(
        total=len(assessment_records),
        page=1,
        page_size=len(assessment_records),
        results=[
            _serialise_assessment_summary(assessment_record)
            for assessment_record in assessment_records
        ],
    )


@router.delete(
    "/assessments/{assessment_id}",
    response_model=AssessmentDeleteResponse,
)
async def delete_clinician_assessment(
    assessment_id: PythonUUID,
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
) -> AssessmentDeleteResponse:
    """Soft delete one clinician assessment history record."""
    try:
        assessment_record = await soft_delete_clinician_assessment(
            database_session=database_session,
            clinician_user_id=current_user.id,
            assessment_id=assessment_id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to delete assessment_id=%s for clinician_user_id=%s",
            assessment_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Assessment could not be deleted. Please try again or contact support "
                "if the problem persists."
            ),
        )

    if assessment_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found.",
        )

    return AssessmentDeleteResponse(detail="Assessment deleted.")
