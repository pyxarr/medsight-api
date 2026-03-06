import pandas as pd
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional


router = APIRouter()


# ── Input schemas ─────────────────────────────────────────────────────────────
# These define exactly what data the API accepts for each form type.
# Optional fields mean the doctor did not provide that data.

class ClinicalData(BaseModel):
    """
    Always required — basic clinical records from the UCTH form.
    Every patient and doctor must provide these.
    """
    age:                    float
    menopause:              int    # 0 = premenopausal, 1 = postmenopausal
    tumor_size_cm:          float
    invasive_nodes:         float
    breast_side:            int    # 0 = left, 1 = right
    metastasis:             int    # 0 = no, 1 = yes
    breast_quadrant:        int    # 0=upper outer, 1=upper inner, 2=lower outer, 3=lower inner
    breast_disease_history: int    # 0 = no, 1 = yes


class BiopsyData(BaseModel):
    """
    Optional — FNA biopsy measurements (Wisconsin features).
    Only available if the patient had a biopsy.
    """
    mean_radius:             float
    mean_texture:            float
    mean_perimeter:          float
    mean_area:               float
    mean_smoothness:         float
    mean_compactness:        float
    mean_concavity:          float
    mean_concave_points:     float
    mean_symmetry:           float
    mean_fractal_dimension:  float
    radius_error:            float
    texture_error:           float
    perimeter_error:         float
    area_error:              float
    smoothness_error:        float
    compactness_error:       float
    concavity_error:         float
    concave_points_error:    float
    symmetry_error:          float
    fractal_dimension_error: float
    worst_radius:            float
    worst_texture:           float
    worst_perimeter:         float
    worst_area:              float
    worst_smoothness:        float
    worst_compactness:       float
    worst_concavity:         float
    worst_concave_points:    float
    worst_symmetry:          float
    worst_fractal_dimension: float


class BloodPanelData(BaseModel):
    """
    Optional — blood biomarker panel (Coimbra features).
    Only available if the patient had blood tests.
    """
    age:             float
    body_mass_index: float
    glucose:         float
    insulin:         float
    homeostasis_model_assessment:    float
    leptin:          float
    adiponectin:     float
    resistin:        float
    monocyte_chemoattractant_protein: float


class PatientPredictionRequest(BaseModel):
    """
    Patient form — only clinical data required.
    This is what the patient submits from the mobile app.
    """
    patient_id:    str
    clinical_data: ClinicalData


class DoctorPredictionRequest(BaseModel):
    """
    Doctor form — clinical data required, biopsy and blood panel optional.
    This is what the doctor submits for a full detailed report.
    """
    patient_id:    str
    clinical_data: ClinicalData
    biopsy_data:   Optional[BiopsyData]      = None
    blood_panel:   Optional[BloodPanelData]  = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/patient/assess")
async def patient_assess(request: Request, body: PatientPredictionRequest):
    """
    Patient endpoint — accepts clinical data only.
    Returns a simple result: risk level, guidance, and warnings.
    No technical details — designed for patients.
    """
    ensemble     = request.app.state.ensemble
    ood_detector = request.app.state.ood_detector
    ucth_preprocessor = request.app.state.ucth_preprocessor

    # Convert clinical data to DataFrame
    ucth_dataframe = pd.DataFrame([body.clinical_data.model_dump()])

    # Run OOD check
    ood_result = ood_detector.detect(ucth_dataframe)

    # Run prediction
    result = ensemble.predict(ucth_features=ucth_dataframe)

    # Simple warning message for patients
    warning_message = None
    if ood_result["has_warning"]:
        warning_message = (
            "Some of your values were outside the expected range. "
            "Please consult your doctor for a more accurate assessment."
        )

    return {
        "patient_id":      body.patient_id,
        "risk_level":      result["risk_level"],
        "guidance":        result["clinical_guidance"],
        "has_warning":     ood_result["has_warning"],
        "warning_message": warning_message,
    }


@router.post("/doctor/assess")
async def doctor_assess(request: Request, body: DoctorPredictionRequest):
    """
    Doctor endpoint — accepts clinical + optional biopsy + optional blood panel.
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

    # ── Build DataFrames from request ─────────────────────────────────────
    ucth_dataframe = pd.DataFrame([body.clinical_data.model_dump()])

    wisconsin_dataframe = None
    if body.biopsy_data is not None:
        wisconsin_dataframe = pd.DataFrame([body.biopsy_data.model_dump()])
        # Rename to match WDBC feature names
        wisconsin_dataframe.columns = wisconsin_feature_names

    coimbra_dataframe = None
    if body.blood_panel is not None:
        coimbra_dataframe = pd.DataFrame([body.blood_panel.model_dump()])

    # ── OOD check ─────────────────────────────────────────────────────────
    ood_result = ood_detector.detect(ucth_dataframe)

    # ── Ensemble prediction ───────────────────────────────────────────────
    result = ensemble.predict(
        ucth_features=ucth_dataframe,
        wisconsin_features=wisconsin_dataframe,
        coimbra_features=coimbra_dataframe,
    )

    # ── SHAP explanations ─────────────────────────────────────────────────
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