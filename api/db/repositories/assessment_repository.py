from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID as PythonUUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.assessment import Assessment
from api.models.patient import Patient

async def create_clinician_assessment(
    database_session: AsyncSession,
    clinician_user_id: PythonUUID,
    patient_id: PythonUUID,
    patient_external_id: str,
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
    batch_id: PythonUUID | None = None,
) -> Assessment:
    """Create and persist a clinician assessment record."""
    assessment_record = Assessment(
        clinician_user_id=clinician_user_id,
        patient_id=patient_id,
        patient_external_id=patient_external_id,
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
        batch_id=batch_id,
    )

    database_session.add(assessment_record)

    try:
        await database_session.flush()
    except Exception:
        await database_session.rollback()
        raise

    await database_session.refresh(assessment_record)

    return assessment_record


async def list_clinician_assessments(
    database_session: AsyncSession,
    clinician_user_id: PythonUUID,
    patient_external_id: str | None,
    patient_name: str | None,
    risk_level: str | None,
    date_from: date | None,
    date_to: date | None,
    page: int,
    page_size: int,
) -> tuple[int, list[Assessment]]:
    """Return a paginated page of active clinician assessments."""
    patient_join_required = patient_external_id is not None or patient_name is not None
    assessment_filters = [
        Assessment.clinician_user_id == clinician_user_id,
        Assessment.deleted_at.is_(None),
    ]

    if patient_external_id is not None:
        assessment_filters.append(Assessment.patient_external_id == patient_external_id)

    if patient_name is not None:
        normalised_patient_name = f"%{patient_name.strip().lower()}%"
        assessment_filters.append(
            or_(
                func.lower(Patient.first_name).like(normalised_patient_name),
                func.lower(Patient.last_name).like(normalised_patient_name),
                func.lower(func.concat(Patient.first_name, " ", Patient.last_name)).like(
                    normalised_patient_name
                ),
            )
        )

    if risk_level is not None:
        assessment_filters.append(Assessment.risk_level == risk_level)

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

    total_query = select(func.count()).select_from(Assessment)
    assessments_query = select(Assessment).options(selectinload(Assessment.patient))

    if patient_join_required:
        total_query = total_query.join(Patient, Assessment.patient_id == Patient.id)
        assessments_query = assessments_query.join(Patient, Assessment.patient_id == Patient.id)

    total_query = total_query.where(*assessment_filters)
    assessments_query = (
        assessments_query.where(*assessment_filters)
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
    clinician_user_id: PythonUUID,
    assessment_id: PythonUUID,
) -> Assessment | None:
    """Return one active clinician assessment by identifier."""
    assessment_query = select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.clinician_user_id == clinician_user_id,
        Assessment.deleted_at.is_(None),
    ).options(selectinload(Assessment.patient), selectinload(Assessment.batch))
    assessment_result = await database_session.execute(assessment_query)

    return assessment_result.scalar_one_or_none()


async def soft_delete_clinician_assessment(
    database_session: AsyncSession,
    clinician_user_id: PythonUUID,
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


async def list_batch_assessments(
    database_session: AsyncSession,
    clinician_user_id: PythonUUID,
    batch_id: PythonUUID,
) -> list[Assessment]:
    """Return active assessments belonging to one clinician batch."""
    assessments_query = (
        select(Assessment)
        .where(
            Assessment.clinician_user_id == clinician_user_id,
            Assessment.batch_id == batch_id,
            Assessment.deleted_at.is_(None),
        )
        .options(selectinload(Assessment.patient), selectinload(Assessment.batch))
        .order_by(Assessment.created_at.desc())
    )
    assessments_result = await database_session.execute(assessments_query)
    return list(assessments_result.scalars().all())


async def list_patient_assessments(
    database_session: AsyncSession,
    clinician_user_id: PythonUUID,
    patient_external_id: str,
) -> list[Assessment]:
    """Return active assessments for one patient external identifier."""
    assessments_query = (
        select(Assessment)
        .where(
            Assessment.clinician_user_id == clinician_user_id,
            Assessment.patient_external_id == patient_external_id,
            Assessment.deleted_at.is_(None),
        )
        .options(selectinload(Assessment.patient), selectinload(Assessment.batch))
        .order_by(Assessment.created_at.desc())
    )
    assessments_result = await database_session.execute(assessments_query)
    return list(assessments_result.scalars().all())


async def create_member_assessment(
    database_session: AsyncSession,
    member_user_id: PythonUUID,
    patient_id: PythonUUID,
    patient_external_id: str,
    assessment_role: str,
    clinical_data: dict,
    risk_level: str,
    key_risk_drivers: list[dict] | dict | None,
    ood_warning: dict | None,
) -> Assessment:
    """Create and persist a member assessment record with plain-language fields."""
    assessment_record = Assessment(
        member_user_id=member_user_id,
        patient_id=patient_id,
        patient_external_id=patient_external_id,
        assessment_role=assessment_role,
        clinical_data=clinical_data,
        risk_level=risk_level,
        key_risk_drivers=key_risk_drivers,
        ood_warning=ood_warning,
    )

    database_session.add(assessment_record)

    try:
        await database_session.flush()
    except Exception:
        await database_session.rollback()
        raise

    await database_session.refresh(assessment_record)

    return assessment_record


async def get_member_assessment(
    database_session: AsyncSession,
    member_user_id: PythonUUID,
    assessment_id: PythonUUID,
) -> Assessment | None:
    """Return one active member assessment by identifier."""
    assessment_query = select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.member_user_id == member_user_id,
        Assessment.deleted_at.is_(None),
    ).options(selectinload(Assessment.patient))
    assessment_result = await database_session.execute(assessment_query)

    return assessment_result.scalar_one_or_none()


async def list_member_assessments(
    database_session: AsyncSession,
    member_user_id: PythonUUID,
    status_filter: str | None,
    page: int,
    page_size: int,
) -> tuple[int, list[Assessment]]:
    """Return a paginated page of active member assessments."""
    assessment_filters = [
        Assessment.member_user_id == member_user_id,
        Assessment.deleted_at.is_(None),
    ]

    if status_filter is not None:
        if status_filter == "High risk":
            assessment_filters.append(Assessment.risk_level == "High")
        elif status_filter == "Success":
            assessment_filters.append(
                Assessment.risk_level.in_(["Low", "Medium"])
            )

    total_query = select(func.count()).select_from(Assessment)
    assessments_query = (
        select(Assessment)
        .options(selectinload(Assessment.patient))
        .where(*assessment_filters)
        .order_by(Assessment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    total_result = await database_session.execute(total_query.where(*assessment_filters))
    assessments_result = await database_session.execute(assessments_query)

    total_assessments = total_result.scalar_one()
    assessment_records = list(assessments_result.scalars().all())

    return total_assessments, assessment_records
