import logging
from typing import Literal
from uuid import UUID as PythonUUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.assessment_repository import (
    create_member_assessment,
    get_member_assessment,
    list_member_assessments,
)
from api.db.repositories.patient_repository import PatientRepository
from api.db.repositories.user_repository import UserRepository
from api.db.session import get_db
from api.lib.auth import CurrentUser, require_role
from api.schemas.member import (
    MemberAssessmentDetailResponse,
    MemberAssessmentListItem,
    MemberAssessmentListResponse,
    MemberAssessmentResponse,
    MemberManualAssessRequest,
    MemberOodWarning,
    MemberTopFactor,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter()

MODEL_LIMITATIONS = (
    "This self-assessment tool provides risk estimates based on clinical statistical models "
    "and is not a clinical diagnosis. Always consult a qualified medical professional for health decisions."
)

FEATURE_LABELS = {
    "age": "Age",
    "menopause": "Menopause status",
    "tumor_size_cm": "Tumour size",
    "invasive_nodes": "Invasive lymph nodes",
    "breast_side": "Breast side",
    "metastasis": "Metastasis status",
    "breast_quadrant": "Breast quadrant",
    "breast_disease_history": "Breast disease history",
}

EXPLANATIONS = {
    "age": {
        "increases_risk": "Your age is above the typical range used in our training data, which contributes to a higher risk estimate.",
        "decreases_risk": "Your age aligns with a lower risk baseline in our training data.",
    },
    "menopause": {
        "increases_risk": "Postmenopausal status is associated with higher risk estimates in our clinical dataset.",
        "decreases_risk": "Premenopausal status corresponds to a lower risk estimate in our clinical dataset.",
    },
    "tumor_size_cm": {
        "increases_risk": "Larger tumour size measurements contribute positively to the risk calculation.",
        "decreases_risk": "Smaller tumour size measurements contribute towards a lower risk score.",
    },
    "invasive_nodes": {
        "increases_risk": "Higher invasive lymph node count significantly increases the overall risk estimate.",
        "decreases_risk": "Low or zero invasive lymph node count supports a lower risk assessment.",
    },
    "breast_side": {
        "increases_risk": "Specific breast measurement indicators contribute to the risk score.",
        "decreases_risk": "Breast measurement indicators align with standard baseline values.",
    },
    "metastasis": {
        "increases_risk": "Indication of metastasis significantly elevates the risk calculation.",
        "decreases_risk": "Absence of metastasis contributes to a lower risk estimate.",
    },
    "breast_quadrant": {
        "increases_risk": "The quadrant location of the lesion contributes to the risk calculation.",
        "decreases_risk": "The quadrant location corresponds to a lower risk baseline.",
    },
    "breast_disease_history": {
        "increases_risk": "A prior history of breast disease contributes to a higher risk calculation.",
        "decreases_risk": "No prior history of breast disease supports a lower risk estimate.",
    },
}


def _get_suggested_action(risk_level: str) -> str:
    """Return a plain-language suggested action tailored to the risk level."""
    normalized = risk_level.strip().capitalize()
    if normalized == "High":
        return "Specialist review recommended. Please visit a breast care clinic or specialist as soon as possible."
    if normalized == "Medium":
        return "Schedule a consultation with a healthcare practitioner for further evaluation."
    return "Routine screening recommended as per national health guidelines."


def _format_top_factors(shap_drivers: list[dict] | dict | None) -> list[MemberTopFactor]:
    """Transform SHAP risk drivers into plain-language top factors."""
    if not shap_drivers:
        return []

    drivers_list = shap_drivers if isinstance(shap_drivers, list) else [shap_drivers]
    top_factors: list[MemberTopFactor] = []

    for driver in drivers_list:
        raw_feature = driver.get("feature", "")
        direction = driver.get("direction", "increases_risk")
        label = FEATURE_LABELS.get(raw_feature, raw_feature.replace("_", " ").capitalize())

        feature_explanations = EXPLANATIONS.get(raw_feature, {})
        explanation = feature_explanations.get(
            direction,
            f"Your {label.lower()} measurement influences the assessment result.",
        )

        top_factors.append(MemberTopFactor(feature=label, explanation=explanation))

    return top_factors


def _format_ood_warning(ood_data: dict | None) -> MemberOodWarning | None:
    """Format out-of-distribution warning for member display."""
    if not ood_data or not ood_data.get("has_warning"):
        return MemberOodWarning(has_warning=False, flagged_features=[], severity=None)

    flagged = ood_data.get("flagged") or ood_data.get("flagged_features") or []
    flagged_labels: list[str] = []
    for flagged_item in flagged:
        if isinstance(flagged_item, dict):
            flagged_feature_name = str(flagged_item.get("feature", ""))
        else:
            flagged_feature_name = str(flagged_item)

        if not flagged_feature_name:
            continue

        flagged_labels.append(
            FEATURE_LABELS.get(
                flagged_feature_name,
                flagged_feature_name.replace("_", " ").capitalize(),
            )
        )

    severity = ood_data.get("severity") or "Minor"

    return MemberOodWarning(
        has_warning=True,
        flagged_features=flagged_labels,
        severity=severity if severity in ("Minor", "Major") else "Minor",
    )


@router.post(
    "/manual-assess",
    response_model=MemberAssessmentResponse,
)
async def member_manual_assess(
    request: Request,
    body: MemberManualAssessRequest,
    current_user: CurrentUser = Depends(require_role("member")),
    database_session: AsyncSession = Depends(get_db),
) -> MemberAssessmentResponse:
    """Submit a member-led self-assessment and persist plain-language report."""
    patient_repository = PatientRepository()
    if body.patient_id:
        patient_record = await patient_repository.get_by_external_id(
            database_session=database_session,
            patient_external_id=body.patient_id,
        )
        if patient_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {body.patient_id} not found.",
            )
    else:
        patient_record = await patient_repository.create_patient(
            database_session=database_session,
            first_name=body.first_name,
            last_name=body.last_name,
        )

    # Ensure user profile exists in product users table
    user_repository = UserRepository()
    await user_repository.get_or_create_from_auth_user(
        database_session=database_session,
        current_user=current_user,
    )

    # Run inference pipeline using UCTH clinical features
    ucth_dataframe = pd.DataFrame([body.clinical_data.model_dump()])

    ood_detector = request.app.state.ood_detector
    ensemble = request.app.state.ensemble
    explainer = request.app.state.explainer

    ood_result = ood_detector.detect(ucth_dataframe)
    prediction_result = ensemble.predict(ucth_features=ucth_dataframe)

    scaled_ucth_features = request.app.state.ucth_preprocessor.transform(ucth_dataframe)
    shap_drivers = explainer.explain(
        preprocessed_ucth_features=scaled_ucth_features,
        ucth_feature_names=request.app.state.ucth_feature_names,
    )

    top_factors = _format_top_factors(shap_drivers)
    suggested_action = _get_suggested_action(prediction_result["risk_level"])
    ood_warning = _format_ood_warning(ood_result)

    try:
        assessment_record = await create_member_assessment(
            database_session=database_session,
            member_user_id=current_user.id,
            patient_id=patient_record.id,
            patient_external_id=patient_record.patient_id,
            assessment_role="member",
            clinical_data=body.clinical_data.model_dump(),
            risk_level=prediction_result["risk_level"],
            key_risk_drivers=shap_drivers,
            ood_warning=ood_result,
        )
    except Exception as e:
        LOGGER.exception(
            "Failed to persist member assessment for member_user_id=%s. Error: %s",
            current_user.id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assessment could not be saved. Please try again or contact support if the problem persists.",
        )

    return MemberAssessmentResponse(
        assessment_id=assessment_record.id,
        patient_id=patient_record.patient_id,
        risk_level=prediction_result["risk_level"],
        top_factors=top_factors,
        suggested_action=suggested_action,
        model_limitations=MODEL_LIMITATIONS,
        ood_warning=ood_warning,
        created_at=assessment_record.created_at,
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=MemberAssessmentDetailResponse,
)
async def get_member_assessment_detail(
    assessment_id: PythonUUID,
    current_user: CurrentUser = Depends(require_role("member")),
    database_session: AsyncSession = Depends(get_db),
) -> MemberAssessmentDetailResponse:
    """Fetch a single member assessment for the report view."""
    try:
        assessment_record = await get_member_assessment(
            database_session=database_session,
            member_user_id=current_user.id,
            assessment_id=assessment_id,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load assessment_id=%s for member_user_id=%s",
            assessment_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assessment could not be loaded. Please try again or contact support if the problem persists.",
        )

    if assessment_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found.",
        )

    patient_record = assessment_record.patient
    patient_name = f"{patient_record.first_name} {patient_record.last_name}".strip() if patient_record else ""
    sample_date = assessment_record.created_at.strftime("%d/%m/%Y")

    top_factors = _format_top_factors(assessment_record.key_risk_drivers)
    suggested_action = _get_suggested_action(assessment_record.risk_level or "Low")
    ood_warning = _format_ood_warning(assessment_record.ood_warning)

    return MemberAssessmentDetailResponse(
        assessment_id=assessment_record.id,
        patient_id=assessment_record.patient_external_id,
        patient_name=patient_name,
        sample_date=sample_date,
        risk_level=assessment_record.risk_level or "Low",
        top_factors=top_factors,
        suggested_action=suggested_action,
        model_limitations=MODEL_LIMITATIONS,
        ood_warning=ood_warning,
        created_at=assessment_record.created_at,
    )


@router.get(
    "/assessments",
    response_model=MemberAssessmentListResponse,
)
async def list_member_assessment_history(
    current_user: CurrentUser = Depends(require_role("member")),
    database_session: AsyncSession = Depends(get_db),
    status_filter: Literal["Success", "High risk"] | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> MemberAssessmentListResponse:
    """List the current user's past member assessments."""
    try:
        total, assessment_records = await list_member_assessments(
            database_session=database_session,
            member_user_id=current_user.id,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
    except Exception:
        LOGGER.exception(
            "Failed to load member assessment history for member_user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assessment history could not be loaded. Please try again or contact support if the problem persists.",
        )

    results: list[MemberAssessmentListItem] = []
    for record in assessment_records:
        patient_record = record.patient
        patient_name = f"{patient_record.first_name} {patient_record.last_name}".strip() if patient_record else ""
        item_status: Literal["Success", "High risk"] = "High risk" if record.risk_level == "High" else "Success"

        results.append(
            MemberAssessmentListItem(
                id=record.id,
                patient_name=patient_name,
                patient_id=record.patient_external_id,
                risk_level=record.risk_level or "Low",
                status=item_status,
                created_at=record.created_at,
            )
        )

    return MemberAssessmentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=results,
    )
