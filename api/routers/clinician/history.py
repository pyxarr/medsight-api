import logging
from datetime import date
from typing import Literal
from uuid import UUID as PythonUUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.assessment_repository import (
    get_clinician_assessment,
    list_clinician_assessments,
    soft_delete_clinician_assessment,
)
from api.db.session import get_db
from api.lib.auth import CurrentUser, require_role
from api.schemas.assessment_history import (
    AssessmentDeleteResponse,
    AssessmentHistoryDetailResponse,
    AssessmentHistoryListResponse,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter()

@router.get(
    "/assessments",
    response_model=AssessmentHistoryListResponse,
)
async def list_clinician_assessment_history(
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
    patient_id: str | None = Query(default=None),
    risk_level: Literal["Low", "Medium", "High"] | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Return a paginated clinician assessment history page."""
    try:
        total_assessments, assessment_records = await list_clinician_assessments(
            database_session=database_session,
            clinician_user_id=current_user.id,
            patient_id=patient_id,
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
                "Assessment history could not be loaded. Please try again or "
                "contact support if the problem persists."
            ),
        )

    return AssessmentHistoryListResponse(
        total=total_assessments,
        page=page,
        page_size=page_size,
        results=assessment_records,
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentHistoryDetailResponse,
)
async def get_clinician_assessment_detail(
    assessment_id: PythonUUID,
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
):
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
                "Assessment could not be loaded. Please try again or contact "
                "support if the problem persists."
            ),
        )

    if assessment_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found.",
        )

    return assessment_record


@router.delete(
    "/assessments/{assessment_id}",
    response_model=AssessmentDeleteResponse,
)
async def delete_clinician_assessment(
    assessment_id: PythonUUID,
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
):
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
                "Assessment could not be deleted. Please try again or contact "
                "support if the problem persists."
            ),
        )

    if assessment_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found.",
        )

    return AssessmentDeleteResponse(detail="Assessment deleted.")
