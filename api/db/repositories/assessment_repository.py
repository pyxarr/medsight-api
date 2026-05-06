from decimal import Decimal
from uuid import UUID as PythonUUID

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
