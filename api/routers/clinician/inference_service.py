import io
from typing import Any

import pandas as pd
from fastapi import Request, UploadFile

from api.schemas.assessment import ClinicianPredictionRequest


def prepare_assessment_dataframes(
    request: Request,
    body: ClinicianPredictionRequest,
) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """Convert one clinician request into dataset-specific DataFrames."""
    ucth_dataframe = pd.DataFrame([body.clinical_data.model_dump()])

    wisconsin_dataframe = None
    if body.biopsy_data is not None:
        wisconsin_dataframe = pd.DataFrame([body.biopsy_data.model_dump()])
        wisconsin_dataframe.columns = request.app.state.wisconsin_feature_names

    coimbra_dataframe = None
    if body.blood_panel is not None:
        coimbra_dataframe = pd.DataFrame([body.blood_panel.model_dump()])
        coimbra_dataframe.insert(0, "age", body.clinical_data.age)

    return ucth_dataframe, wisconsin_dataframe, coimbra_dataframe


def run_inference_and_explain(
    request: Request,
    ucth_dataframe: pd.DataFrame,
    wisconsin_dataframe: pd.DataFrame | None,
    coimbra_dataframe: pd.DataFrame | None,
) -> tuple[dict, list[dict] | dict | None]:
    """Run prediction, out-of-distribution checks, and SHAP explanation."""
    ensemble = request.app.state.ensemble
    ood_detector = request.app.state.ood_detector
    explainer = request.app.state.explainer

    out_of_distribution_result = ood_detector.detect(ucth_dataframe)
    prediction_result = ensemble.predict(
        ucth_features=ucth_dataframe,
        wisconsin_features=wisconsin_dataframe,
        coimbra_features=coimbra_dataframe,
    )

    scaled_ucth_features = request.app.state.ucth_preprocessor.transform(ucth_dataframe)
    scaled_wisconsin_features = (
        request.app.state.wisconsin_preprocessor.transform(wisconsin_dataframe)
        if wisconsin_dataframe is not None
        else None
    )
    scaled_coimbra_features = (
        request.app.state.coimbra_preprocessor.transform(coimbra_dataframe)
        if coimbra_dataframe is not None
        else None
    )

    shap_drivers = explainer.explain(
        preprocessed_ucth_features=scaled_ucth_features,
        ucth_feature_names=request.app.state.ucth_feature_names,
        preprocessed_wisconsin_features=scaled_wisconsin_features,
        wisconsin_feature_names=(
            request.app.state.wisconsin_feature_names
            if scaled_wisconsin_features is not None
            else None
        ),
        preprocessed_coimbra_features=scaled_coimbra_features,
        coimbra_feature_names=(
            request.app.state.coimbra_feature_names
            if scaled_coimbra_features is not None
            else None
        ),
    )

    prediction_result["ood_warning"] = out_of_distribution_result
    return prediction_result, shap_drivers


def build_assessment_response_payload(
    prediction_result: dict[str, Any],
    shap_drivers: list[dict] | dict | None,
    patient_external_id: str,
) -> dict[str, Any]:
    """Build the clinician assessment response payload."""
    return {
        "patient_id": patient_external_id,
        "risk_score": prediction_result["final_risk_score"],
        "risk_level": prediction_result["risk_level"],
        "confidence_percent": prediction_result["confidence_percent"],
        "agreement": prediction_result["agreement"],
        "models_used": prediction_result["models_used"],
        "individual_scores": prediction_result["individual_scores"],
        "clinical_guidance": prediction_result["clinical_guidance"],
        "key_risk_drivers": shap_drivers,
        "ood_warning": {
            "has_warning": prediction_result["ood_warning"]["has_warning"],
            "flagged": prediction_result["ood_warning"]["flagged"],
        },
    }


async def parse_batch_csv(file: UploadFile) -> tuple[pd.DataFrame, bytes]:
    """Read one uploaded CSV file and return both the DataFrame and raw bytes."""
    file_bytes = await file.read()
    if not file_bytes:
        raise ValueError("The uploaded CSV file is empty.")

    try:
        batch_dataframe = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError("The uploaded file could not be parsed as CSV.") from exc

    return batch_dataframe, file_bytes


async def parse_batch_xlsx(file: UploadFile) -> tuple[pd.DataFrame, bytes]:
    """Read one uploaded XLSX file and return both the DataFrame and raw bytes."""
    file_bytes = await file.read()
    if not file_bytes:
        raise ValueError("The uploaded XLSX file is empty.")

    try:
        batch_dataframe = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as exc:
        raise ValueError(
            "Could not read the uploaded Excel file. Ensure the file is a valid, unprotected .xlsx workbook."
        ) from exc

    return batch_dataframe, file_bytes
