from pydantic import BaseModel, field_validator
from typing import Optional, Any
from pydantic import ValidationInfo

class ClinicalData(BaseModel):
    """
    Always required — basic clinical records from the UCTH form.
    Every member and clinician must provide these.
    """
    age:                    float
    menopause:              int | str    # 0='premenopausal', 1='postmenopausal'
    tumor_size_cm:          float
    invasive_nodes:         float
    breast_side:            int | str    # 0='left', 1='right'
    metastasis:             int | str    # 0='no', 1='yes'
    breast_quadrant:        int | str    # 0='upper outer', 1='upper inner', 2='lower outer', 3='lower inner'
    breast_disease_history: int | str    # 0='no', 1='yes'

    # Use mode="before" to intercept the input before Pydantic's type coercion attempt.
    # This allows us to handle strings and convert them to integers before the model is instantiated.
    @field_validator("menopause", "breast_side", "metastasis", "breast_quadrant", "breast_disease_history", mode="before")
    @classmethod
    def validate_categorical_clinical_field(cls, v: Any, info: ValidationInfo) -> int:
        if isinstance(v, int):
            return v
        
        if isinstance(v, str):
            stripped_v = v.strip().lower()
            if not stripped_v:
                raise ValueError(f"Field {info.field_name} cannot be empty.")
            
            # Handle string-encoded integers (e.g. "1") first to avoid unnecessary mapping lookups.
            try:
                return int(stripped_v)
            except ValueError:
                pass
            
            # Single validator handles all categorical fields to reduce logic duplication.
            mappings = {
                "menopause": {"premenopausal": 0, "postmenopausal": 1},
                "breast_side": {"left": 0, "right": 1},
                "metastasis": {"no": 0, "yes": 1},
                "breast_quadrant": {
                    "upper outer": 0, "upper inner": 1, "lower outer": 2, "lower inner": 3
                },
                "breast_disease_history": {"no": 0, "yes": 1},
            }
            
            field_map = mappings.get(info.field_name, {})
            if stripped_v in field_map:
                return field_map[stripped_v]
            
            accepted = ", ".join([f"'{k}'" for k in field_map.keys()])
            raise ValueError(f"Invalid value {v} for {info.field_name}. Accepted values: {accepted}")

        raise ValueError(f"Invalid type for {info.field_name}. Expected int or str.")


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


class ClinicianManualAssessRequest(BaseModel):
    """
    Manual entry form — clinical data required, blood panel optional.
    Biopsy data is excluded to prevent lengthy manual input.
    """
    first_name:    str
    last_name:     str
    clinical_data: ClinicalData
    blood_panel:   Optional[BloodPanelData]  = None
