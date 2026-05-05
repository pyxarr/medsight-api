import pandas as pd
from fastapi import APIRouter, Request, Depends

from api.lib.auth import require_role, CurrentUser
from api.schemas.assessment import (
    MemberPredictionRequest,
    ClinicianPredictionRequest
)

router = APIRouter()


# Endpoints
@router.post("/member/assess")
async def member_assess(
    request: Request, 
    body: MemberPredictionRequest, 
    current_user: CurrentUser = Depends(require_role("member"))
):
    """
    Member endpoint — accepts clinical data only.
    Returns a simple result: risk level, guidance, and warnings.
    No technical details — designed for members.
    """
    ensemble     = request.app.state.ensemble
    ood_detector = request.app.state.ood_detector

    # Convert clinical data to DataFrame
    ucth_dataframe = pd.DataFrame([body.clinical_data.model_dump()])

    # Run OOD check
    ood_result = ood_detector.detect(ucth_dataframe)

    # Run prediction
    result = ensemble.predict(ucth_features=ucth_dataframe)

    # Simple warning message for members
    warning_message = None
    if ood_result["has_warning"]:
        warning_message = (
            "Some of your values were outside the expected range. "
            "Please consult your clinician for a more accurate assessment."
        )

    return {
        "patient_id":      body.patient_id,
        "risk_level":      result["risk_level"],
        "guidance":        result["clinical_guidance"],
        "has_warning":     ood_result["has_warning"],
        "warning_message": warning_message,
    }


@router.post("/clinician/assess")
async def clinician_assess(
    request: Request, 
    body: ClinicianPredictionRequest, 
    current_user: CurrentUser = Depends(require_role("clinician"))
):
    """
    Clinician endpoint — accepts clinical + optional biopsy + optional blood panel.
    Returns the full detailed report matching the mockup designs.
    """
    ensemble     = request.app.state.ensemble
    ood_detector = request.app.state.ood_detector
    explainer    = request.app.state.explainer

    ucth_preprocessor      = request.app.state.ucth_preprocessor
    wisconsin_preprocessor = request.app.state.wisconsin_preprocessor
    coimbra_preprocessor   = request.app.state.coimbra_preprocessor

    wisconsin_feature_names = request.app.state.wisconsin_feature_names
    ucth_feature_names      = request.app.state.ucth_feature_names
    coimbra_feature_names   = request.app.state.coimbra_feature_names

    # Build DataFrames from request
    ucth_dataframe = pd.DataFrame([body.clinical_data.model_dump()])

    wisconsin_dataframe = None
    if body.biopsy_data is not None:
        wisconsin_dataframe = pd.DataFrame([body.biopsy_data.model_dump()])
        # Rename to match WDBC feature names
        wisconsin_dataframe.columns = wisconsin_feature_names

    coimbra_dataframe = None
    if body.blood_panel is not None:
        coimbra_dataframe = pd.DataFrame([body.blood_panel.model_dump()])
        # Inject age from clinical data as the Coimbra model expects it
        coimbra_dataframe.insert(0, "age", body.clinical_data.age)

    # OOD check
    ood_result = ood_detector.detect(ucth_dataframe)

    # Ensemble prediction
    result = ensemble.predict(
        ucth_features=ucth_dataframe,
        wisconsin_features=wisconsin_dataframe,
        coimbra_features=coimbra_dataframe,
    )

    # SHAP explanations
    scaled_ucth      = ucth_preprocessor.transform(ucth_dataframe)
    scaled_wisconsin = wisconsin_preprocessor.transform(wisconsin_dataframe) if wisconsin_dataframe is not None else None
    scaled_coimbra   = coimbra_preprocessor.transform(coimbra_dataframe)     if coimbra_dataframe   is not None else None

    drivers = explainer.explain(
        preprocessed_ucth_features=scaled_ucth,
        ucth_feature_names=ucth_feature_names,
        preprocessed_wisconsin_features=scaled_wisconsin,
        wisconsin_feature_names=wisconsin_feature_names if scaled_wisconsin is not None else None,
        preprocessed_coimbra_features=scaled_coimbra,
        coimbra_feature_names=coimbra_feature_names if scaled_coimbra is not None else None,
    )

    return {
        "patient_id":          body.patient_id,
        "risk_score":          result["final_risk_score"],
        "risk_level":          result["risk_level"],
        "confidence_percent":  result["confidence_percent"],
        "agreement":           result["agreement"],
        "models_used":         result["models_used"],
        "individual_scores":   result["individual_scores"],
        "clinical_guidance":   result["clinical_guidance"],
        "key_risk_drivers":    drivers,
        "ood_warning": {
            "has_warning": ood_result["has_warning"],
            "flagged":     ood_result["flagged"],
        },
    }
