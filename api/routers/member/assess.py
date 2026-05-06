import pandas as pd
from fastapi import APIRouter, Depends, Request
from api.lib.auth import CurrentUser, require_role
from api.schemas.assessment import MemberPredictionRequest

router = APIRouter()

@router.post("/assess")
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
