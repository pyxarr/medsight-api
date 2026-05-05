from pydantic import BaseModel
from typing import Optional

class ClinicalData(BaseModel):
    """
    Always required — basic clinical records from the UCTH form.
    Every member and clinician must provide these.
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
    Only available if the member had a biopsy.
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
    Only available if the member had blood tests.
    """
    body_mass_index: float
    glucose:         float
    insulin:         float
    homeostasis_model_assessment:    float
    leptin:          float
    adiponectin:     float
    resistin:        float
    monocyte_chemoattractant_protein: float


class MemberPredictionRequest(BaseModel):
    """
    Member form — only clinical data required.
    This is what the member submits from the mobile app.
    """
    patient_id:    str
    clinical_data: ClinicalData


class ClinicianPredictionRequest(BaseModel):
    """
    Clinician form — clinical data required, biopsy and blood panel optional.
    This is what the clinician submits for a full detailed report.
    """
    patient_id:    str
    clinical_data: ClinicalData
    biopsy_data:   Optional[BiopsyData]      = None
    blood_panel:   Optional[BloodPanelData]  = None
