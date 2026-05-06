import logging

import pandas as pd
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.repositories.assessment_repository import create_clinician_assessment
from api.db.session import get_db
from api.lib.auth import CurrentUser, require_role
from api.schemas.assessment import (
    ClinicianPredictionRequest,
    MemberPredictionRequest,
)

LOGGER = logging.getLogger(__name__)

router = APIRouter()


@router.post("/member/assess")
async def member_assess(
    request: Request,
    body: MemberPredictionRequest,
    current_user: CurrentUser = Depends(require_role("member")),
):
    """Return a member-facing assessment result from clinical data only."""
    ensemble = request.app.state.ensemble
    ood_detector = request.app.state.ood_detector

    ucth_dataframe = pd.DataFrame([body.clinical_data.model_dump()])
    out_of_distribution_result = ood_detector.detect(ucth_dataframe)
    result = ensemble.predict(ucth_features=ucth_dataframe)

    warning_message = None
    if out_of_distribution_result["has_warning"]:
        warning_message = (
            "Some of your values were outside the expected range. "
            "Please consult your clinician for a more accurate assessment."
        )

    return {
        "patient_id": body.patient_id,
        "risk_level": result["risk_level"],
        "guidance": result["clinical_guidance"],
        "has_warning": out_of_distribution_result["has_warning"],
        "warning_message": warning_message,
    }


@router.post("/clinician/assess")
async def clinician_assess(
    request: Request,
    body: ClinicianPredictionRequest,
    current_user: CurrentUser = Depends(require_role("clinician")),
    database_session: AsyncSession = Depends(get_db),
):
    """Return a detailed clinician assessment report."""
    ensemble = request.app.state.ensemble
    ood_detector = request.app.state.ood_detector
    explainer = request.app.state.explainer

    ucth_preprocessor = request.app.state.ucth_preprocessor
    wisconsin_preprocessor = request.app.state.wisconsin_preprocessor
    coimbra_preprocessor = request.app.state.coimbra_preprocessor

    wisconsin_feature_names = request.app.state.wisconsin_feature_names
    ucth_feature_names = request.app.state.ucth_feature_names
    coimbra_feature_names = request.app.state.coimbra_feature_names

    ucth_dataframe = pd.DataFrame([body.clinical_data.model_dump()])

    wisconsin_dataframe = None
    if body.biopsy_data is not None:
        wisconsin_dataframe = pd.DataFrame([body.biopsy_data.model_dump()])
        # Keep the live feature names aligned with the persisted model inputs so SHAP and
        # inference both receive the exact schema the Wisconsin artefacts expect.
        wisconsin_dataframe.columns = wisconsin_feature_names

    coimbra_dataframe = None
    if body.blood_panel is not None:
        coimbra_dataframe = pd.DataFrame([body.blood_panel.model_dump()])
        # Inject age here because the public blood-panel schema deliberately excludes it
        # while the persisted Coimbra pipeline still requires age at inference time.
        coimbra_dataframe.insert(0, "age", body.clinical_data.age)

    out_of_distribution_result = ood_detector.detect(ucth_dataframe)
    result = ensemble.predict(
        ucth_features=ucth_dataframe,
        wisconsin_features=wisconsin_dataframe,
        coimbra_features=coimbra_dataframe,
    )

    scaled_ucth = ucth_preprocessor.transform(ucth_dataframe)
    scaled_wisconsin = (
        wisconsin_preprocessor.transform(wisconsin_dataframe)
        if wisconsin_dataframe is not None
        else None
    )
    scaled_coimbra = (
        coimbra_preprocessor.transform(coimbra_dataframe)
        if coimbra_dataframe is not None
        else None
    )

    drivers = explainer.explain(
        preprocessed_ucth_features=scaled_ucth,
        ucth_feature_names=ucth_feature_names,
        preprocessed_wisconsin_features=scaled_wisconsin,
        wisconsin_feature_names=wisconsin_feature_names if scaled_wisconsin is not None else None,
        preprocessed_coimbra_features=scaled_coimbra,
        coimbra_feature_names=coimbra_feature_names if scaled_coimbra is not None else None,
    )

    response_payload = {
        "patient_id": body.patient_id,
        "risk_score": result["final_risk_score"],
        "risk_level": result["risk_level"],
        "confidence_percent": result["confidence_percent"],
        "agreement": result["agreement"],
        "models_used": result["models_used"],
        "individual_scores": result["individual_scores"],
        "clinical_guidance": result["clinical_guidance"],
        "key_risk_drivers": drivers,
        "ood_warning": {
            "has_warning": out_of_distribution_result["has_warning"],
            "flagged": out_of_distribution_result["flagged"],
        },
    }

    try:
        await create_clinician_assessment(
            database_session=database_session,
            clinician_user_id=current_user.id,
            patient_id=body.patient_id,
            assessment_role="clinician",
            clinical_data=body.clinical_data.model_dump(),
            biopsy_data=(
                body.biopsy_data.model_dump()
                if body.biopsy_data is not None
                else None
            ),
            blood_panel_data=(
                body.blood_panel.model_dump()
                if body.blood_panel is not None
                else None
            ),
            risk_score=response_payload["risk_score"],
            risk_level=response_payload["risk_level"],
            confidence_percent=response_payload["confidence_percent"],
            agreement=response_payload["agreement"],
            models_used=response_payload["models_used"],
            individual_scores=response_payload["individual_scores"],
            clinical_guidance=response_payload["clinical_guidance"],
            key_risk_drivers=response_payload["key_risk_drivers"],
            ood_warning=response_payload["ood_warning"],
        )
    except Exception:
        LOGGER.exception(
            "Failed to persist clinician assessment for patient_id=%s clinician_user_id=%s",
            body.patient_id,
            current_user.id,
        )

    return response_payload
