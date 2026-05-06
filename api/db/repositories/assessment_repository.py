from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID as PythonUUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.assessment import Assessment


async def create_clinician_assessment(
    database_session: AsyncSession,
    clinician_user_id: str,
    patient_id: str,
    assessment_role: str,
    clinical_data: dict,
    biopsy_data: dict | None,
    blood_panel_data: dict | None,
    risk_score: float,
    risk_level: str,
    confidence_percent: int,
    agreement: str,
    models_used: int,
    individual_scores: dict,
    clinical_guidance: str,
    key_risk_drivers: list[dict] | dict | None,
    ood_warning: dict,
) -> Assessment:
    """Create and persist a clinician assessment record."""
    assessment_record = Assessment(
        clinician_user_id=PythonUUID(clinician_user_id),
        patient_id=patient_id,
        assessment_role=assessment_role,
        clinical_data=clinical_data,
        biopsy_data=biopsy_data,
        blood_panel_data=blood_panel_data,
        risk_score=Decimal(str(risk_score)),
        risk_level=risk_level,
        confidence_percent=confidence_percent,
        agreement=agreement,
        models_used=models_used,
        individual_scores=individual_scores,
        clinical_guidance=clinical_guidance,
        key_risk_drivers=key_risk_drivers,
        ood_warning=ood_warning,
    )

    database_session.add(assessment_record)

    try:
        await database_session.commit()
    except Exception:
        await database_session.rollback()
        raise

    await database_session.refresh(assessment_record)

    return assessment_record


async def list_clinician_assessments(
    database_session: AsyncSession,
    clinician_user_id: str,
    patient_id: str | None,
    risk_level: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> tuple[int, list[Assessment]]:
    """Return a paginated page of active clinician assessments."""
    clinician_identifier = PythonUUID(clinician_user_id)
    assessment_filters = [
        Assessment.clinician_user_id == clinician_identifier,
        # Exclude soft-deleted rows in SQL so pagination and counts stay consistent with
        # the history view rather than shrinking after application-side filtering.
        Assessment.deleted_at.is_(None),
    ]

    if patient_id is not None:
        assessment_filters.append(Assessment.patient_id == patient_id)

    if risk_level is not None:
        assessment_filters.append(Assessment.risk_level == risk_level)

    # Translate calendar-date filters into timestamp ranges so PostgreSQL can still use
    # created_at indexes instead of wrapping the column in a date() function.
    if date_from is not None:
        created_at_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        assessment_filters.append(Assessment.created_at >= created_at_start)

    if date_to is not None:
        created_at_end = datetime.combine(
            date_to + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        assessment_filters.append(Assessment.created_at < created_at_end)

    total_query = (
        select(func.count()).select_from(Assessment).where(*assessment_filters)
    )
    assessments_query = (
        select(Assessment)
        .where(*assessment_filters)
        .order_by(Assessment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    total_result = await database_session.execute(total_query)
    assessments_result = await database_session.execute(assessments_query)

    total_assessments = total_result.scalar_one()
    assessment_records = list(assessments_result.scalars().all())

    return total_assessments, assessment_records


async def get_clinician_assessment(
    database_session: AsyncSession,
    clinician_user_id: str,
    assessment_id: PythonUUID,
) -> Assessment | None:
    """Return one active clinician assessment by identifier."""
    assessment_query = select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.clinician_user_id == PythonUUID(clinician_user_id),
        # Enforce the soft-delete boundary in SQL so deleted records cannot leak through
        # alternative callers that forget to apply the history visibility rule.
        Assessment.deleted_at.is_(None),
    )
    assessment_result = await database_session.execute(assessment_query)

    return assessment_result.scalar_one_or_none()


async def soft_delete_clinician_assessment(
    database_session: AsyncSession,
    clinician_user_id: str,
    assessment_id: PythonUUID,
) -> Assessment | None:
    """Apply a soft delete to one active clinician assessment."""
    assessment_record = await get_clinician_assessment(
        database_session=database_session,
        clinician_user_id=clinician_user_id,
        assessment_id=assessment_id,
    )

    if assessment_record is None:
        return None

    assessment_record.deleted_at = datetime.now(timezone.utc)

    try:
        await database_session.commit()
    except Exception:
        await database_session.rollback()
        raise

    await database_session.refresh(assessment_record)

    return assessment_record
