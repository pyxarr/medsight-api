## MedSight API Reference

## 1. Overview

The current HTTP API is intentionally small. It exposes one public health route and two protected assessment routes. The backend is not a general CRUD platform. Its main job is to validate authenticated requests, convert request bodies into the expected machine learning input shapes, invoke the loaded inference components, and return role-appropriate responses.

All machine learning artefacts are loaded during application startup and accessed through `request.app.state`. No endpoint trains, refits, or persists machine learning state during request handling.

## 2. Base URL

Local development default:

```text
http://127.0.0.1:8000
```

Protected routes are mounted under:

```text
/api
```

## 3. Authentication Model

### 3.1 Token Source

Authentication is client-managed through Supabase.

- the mobile application registers and signs users in through Supabase
- Supabase returns a JWT
- the mobile client stores the token and sends it with API requests
- FastAPI verifies the token locally

The backend does not:

- issue tokens
- refresh tokens
- store sessions
- call Supabase on each request for authentication

### 3.2 Header Format

Protected requests must include:

```http
Authorization: Bearer <supabase_jwt>
```

### 3.3 Verification Rules

JWT verification is handled in `api/lib/auth.py`. Verification now uses ES256 asymmetric signing via the Supabase JWKS endpoint. To account for potential clock skew between the Supabase auth server and this API server, a 60-second leeway is applied during token decoding.

Required environment variable:

```text
SUPABASE_URL
```

The JWKS URL is `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. `PyJWKClient` fetches and caches the public key at module level.

### 3.4 Expected JWT Claims

The backend expects these Supabase claims:

- `sub`: user identifier
- `email`: email address
- `user_metadata.role`: application role

If any of these values are missing, the backend returns `401`.

### 3.5 Roles

Supported roles:

```text
member
clinician
```

Role enforcement is implemented through:

```python
require_role("member")
require_role("clinician")
```

## 4. Route Summary

| Method | Path | Auth | Role | Purpose |
| --- | --- | --- | --- | --- |
| `GET` | `/` | No | None | Health check |
| `GET` | `/api/users/me` | Yes | Any | Return/bootstrap product user profile |
| `POST` | `/api/member/assess` | Yes | `member` | Simplified clinical assessment |
| `POST` | `/api/clinician/manual-assess` | Yes | `clinician` | Manual diagnostic entry (Clinical + Blood) |
| `POST` | `/api/clinician/batch-assess` | Yes | `clinician` | Batch CSV upload for assessments |
| `GET` | `/api/clinician/assessments` | Yes | `clinician` | Paginated assessment history list |
| `GET` | `/api/clinician/assessments/{id}` | Yes | `clinician` | Full assessment detail record |
| `DELETE` | `/api/clinician/assessments/{id}` | Yes | `clinician` | Soft delete assessment record |


## 5. Health Route

### `GET /`

Purpose:

- confirms that the FastAPI application is running
- does not verify model quality or database connectivity

Response:

```json
{
  "message": "Breast Cancer DSS API is running."
}
```

### `GET /api/users/me`

Required role: any authenticated user

Purpose: returns the authenticated user's product profile; creates the profile record on first request using JWT claims if it does not exist in the `users` table.

Response fields: `id`, `email`, `role`, `display_name`, `username`, `first_name`, `last_name`, `is_verified`, `created_at`

## 6. Shared Request Schemas

Defined in:

```text
api/schemas/assessment.py
```

### 6.1 `ClinicalData`

Always required for both member and clinician assessments.

| Field | Type | Meaning |
| --- | --- | --- |
| `age` | `float` | Patient age |
| `menopause` | `int` | `0 = premenopausal`, `1 = postmenopausal` |
| `tumor_size_cm` | `float` | Tumour size in centimetres |
| `invasive_nodes` | `float` | Invasive lymph node count or value |
| `breast_side` | `int` | `0 = left`, `1 = right` |
| `metastasis` | `int` | `0 = no`, `1 = yes` |
| `breast_quadrant` | `int` | `0 = upper outer`, `1 = upper inner`, `2 = lower outer`, `3 = lower inner` |
| `breast_disease_history` | `int` | `0 = no`, `1 = yes` |

### 6.2 `BiopsyData`

Optional clinician-only payload representing the Wisconsin fine needle aspiration feature space.

Fields:

```text
mean_radius
mean_texture
mean_perimeter
mean_area
mean_smoothness
mean_compactness
mean_concavity
mean_concave_points
mean_symmetry
mean_fractal_dimension
radius_error
texture_error
perimeter_error
area_error
smoothness_error
compactness_error
concavity_error
concave_points_error
symmetry_error
fractal_dimension_error
worst_radius
worst_texture
worst_perimeter
worst_area
worst_smoothness
worst_compactness
worst_concavity
worst_concave_points
worst_symmetry
worst_fractal_dimension
```

### 6.3 `BloodPanelData`

Optional clinician-only payload representing the Coimbra blood biomarker feature space.

Fields:

```text
body_mass_index
glucose
insulin
homeostasis_model_assessment
leptin
adiponectin
resistin
monocyte_chemoattractant_protein
```

Important runtime rule:

- `age` is excluded from `BloodPanelData`
- `ClinicalData.age` is injected into the Coimbra DataFrame inside the route handler

### 6.4 `MemberPredictionRequest`

```json
{
  "patient_id": "P-2024-0001",
  "clinical_data": {
    "age": 45,
    "menopause": 1,
    "tumor_size_cm": 3.0,
    "invasive_nodes": 1,
    "breast_side": 0,
    "metastasis": 0,
    "breast_quadrant": 1,
    "breast_disease_history": 0
  }
}
```

### 6.5 `ClinicianPredictionRequest`

```json
{
  "patient_id": "P-2024-0002",
  "clinical_data": {
    "age": 58,
    "menopause": 1,
    "tumor_size_cm": 4.5,
    "invasive_nodes": 2,
    "breast_side": 1,
    "metastasis": 1,
    "breast_quadrant": 0,
    "breast_disease_history": 1
  },
  "biopsy_data": {
    "mean_radius": 20.57,
    "mean_texture": 17.77,
    "mean_perimeter": 132.9,
    "mean_area": 1326.0,
    "mean_smoothness": 0.08474,
    "mean_compactness": 0.07864,
    "mean_concavity": 0.0869,
    "mean_concave_points": 0.07017,
    "mean_symmetry": 0.1812,
    "mean_fractal_dimension": 0.05667,
    "radius_error": 0.5435,
    "texture_error": 0.7339,
    "perimeter_error": 3.398,
    "area_error": 74.08,
    "smoothness_error": 0.005225,
    "compactness_error": 0.01308,
    "concavity_error": 0.01860,
    "concave_points_error": 0.01340,
    "symmetry_error": 0.01389,
    "fractal_dimension_error": 0.003532,
    "worst_radius": 24.99,
    "worst_texture": 23.41,
    "worst_perimeter": 158.8,
    "worst_area": 1956.0,
    "worst_smoothness": 0.1238,
    "worst_compactness": 0.1866,
    "worst_concavity": 0.2416,
    "worst_concave_points": 0.1860,
    "worst_symmetry": 0.2750,
    "worst_fractal_dimension": 0.08902
  },
  "blood_panel": {
    "body_mass_index": 27.5,
    "glucose": 102.0,
    "insulin": 8.5,
    "homeostasis_model_assessment": 2.1,
    "leptin": 25.0,
    "adiponectin": 8.0,
    "resistin": 12.0,
    "monocyte_chemoattractant_protein": 450.0
  }
}
```

### 6.6 `UserProfileResponse`

Response schema for user profile retrieval.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | `UUID` | Product user identifier |
| `email` | `string` | Registered email address |
| `role` | `string` | Application role (`member` or `clinician`) |
| `display_name` | `string` | Formatted name for UI display |
| `username` | `string` | Unique programmatic handle |
| `first_name` | `string | null` | Given name |
| `last_name` | `string | null` | Family name |
| `is_verified` | `boolean` | Identity verification status |
| `created_at` | `datetime` | Record creation timestamp |

## 7. Member Assessment Endpoint

### `POST /api/member/assess`

Required role:

```text
member
```

### 7.1 Purpose

This endpoint provides a simplified assessment flow for members. It only accepts clinical data. The endpoint does not expose technical model internals such as raw probability breakdowns or SHAP feature attribution.

### 7.2 Processing Flow

Inside `api/routers/predict.py`, the route performs these steps:

1. load `ensemble` and `ood_detector` from `request.app.state`
2. convert `body.clinical_data.model_dump()` into `ucth_dataframe`
3. run out-of-distribution detection on the clinical DataFrame
4. call `ensemble.predict(ucth_features=ucth_dataframe)`
5. convert any warning into member-friendly text
6. return a simplified payload

### 7.3 Response Shape

```json
{
  "patient_id": "P-2024-0001",
  "risk_level": "Low",
  "guidance": "Routine screening schedule. No immediate concerns identified.",
  "has_warning": false,
  "warning_message": null
}
```

### 7.4 Response Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `patient_id` | `string` | Echoed request identifier |
| `risk_level` | `string` | `Low`, `Medium`, or `High` |
| `guidance` | `string` | Guidance text from the ensemble |
| `has_warning` | `boolean` | Whether clinical values fell outside the expected training range |
| `warning_message` | `string | null` | Member-friendly warning text |

### 7.5 Member Scope Deliberately Excluded

The current member response does not expose:

- raw risk score
- confidence percentage
- individual dataset scores
- cross-dataset agreement
- SHAP drivers
- raw flagged feature detail

## 8. Clinician Assessment Endpoint

### `POST /api/clinician/assess`

Required role:

```text
clinician
```

### 8.1 Purpose

This endpoint provides the detailed clinical assessment flow. Clinical data is mandatory. Biopsy and blood panel data are optional. When optional inputs are provided, the ensemble expands to use more model paths and the explainer incorporates more datasets into the returned risk drivers.

### 8.2 Processing Flow

Inside `api/routers/predict.py`, the route performs these steps:

1. load `ensemble`, `ood_detector`, `explainer`, preprocessors, and feature-name lists from `request.app.state`
2. convert clinical data into `ucth_dataframe`
3. if biopsy data is present, convert it into `wisconsin_dataframe`
4. rename biopsy columns to the live Wisconsin feature-name order
5. if blood panel data is present, convert it into `coimbra_dataframe`
6. inject `body.clinical_data.age` into `coimbra_dataframe`
7. run out-of-distribution detection on `ucth_dataframe`
8. call the ensemble with all available DataFrames
9. preprocess the available DataFrames again for SHAP explanation
10. call `explainer.explain(...)`
11. persist the result bundle to the `assessments` table
12. return the detailed report

### 8.3 Response Shape

```json
{
  "patient_id": "P-2024-0002",
  "risk_score": 0.82,
  "risk_level": "High",
  "confidence_percent": 91,
  "agreement": "High",
  "models_used": 3,
  "individual_scores": {
    "ucth": 0.86,
    "wisconsin": 0.91,
    "coimbra": 0.62
  },
  "clinical_guidance": "Priority follow-up recommended. Specialist consultation warranted.",
  "key_risk_drivers": [
    {
      "feature": "worst_perimeter",
      "dataset": "biopsy",
      "contribution": 0.35,
      "direction": "increases_risk",
      "percent": 35
    }
  ],
  "ood_warning": {
    "has_warning": false,
    "flagged": []
  }
}
```

### 8.4 Response Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `patient_id` | `string` | Echoed request identifier |
| `risk_score` | `number` | Rounded final ensemble risk score |
| `risk_level` | `string` | `Low`, `Medium`, or `High` |
| `confidence_percent` | `integer` | Rounded confidence percentage |
| `agreement` | `string` | `Single Model`, `High`, `Mixed`, or `Low` |
| `models_used` | `integer` | Count of models that contributed to the final score |
| `individual_scores` | `object` | Per-dataset malignant probabilities for the models that ran |
| `clinical_guidance` | `string` | Guidance text generated by the ensemble |
| `key_risk_drivers` | `array` | Top SHAP contributions across available datasets |
| `ood_warning` | `object` | Out-of-distribution warning result for clinical features |

### 8.5 `key_risk_drivers` Structure

Each driver contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `feature` | `string` | Feature name |
| `dataset` | `string` | `clinical`, `biopsy`, or `blood_panel` |
| `contribution` | `number` | Raw SHAP contribution value |
| `direction` | `string` | `increases_risk` or `decreases_risk` |
| `percent` | `integer` | Absolute rounded SHAP contribution scaled to percentage form |

### 8.6 `ood_warning` Structure

```json
{
  "has_warning": true,
  "flagged": [
    {
      "feature": "tumor_size_cm",
      "patient_value": 9.2,
      "standard_deviations_away": 4.18,
      "severity": "Minor"
    }
  ]
}
```

Flagged feature detail includes:

- feature name
- observed patient value
- number of standard deviations from the UCTH training mean
- severity label

## 8.7 Batch Assessment Endpoint

### `POST /api/clinician/batch-assess`

Required role:
```text
clinician
```

#### 8.7.1 Purpose
Allows clinicians to upload a CSV file containing multiple patient records. The API processes each row independently; successful rows are persisted as assessments, while failed rows are reported in the response without aborting the entire batch.

#### 8.7.2 Request Format
The endpoint expects a `multipart/form-data` request with a single file field named `file`. The CSV must contain the following mandatory columns:
- `patient_name`
- `cli_age`
- `cli_menopause`
- `cli_tumor_size_cm`
- `cli_invasive_nodes`
- `cli_breast_side`
- `cli_metastasis`
- `cli_breast_quadrant`
- `cli_breast_disease_history`
- `patient_id` (optional)
  - if provided, it must match an existing patient record in the database — rows with an unrecognised `patient_id` are failed, not created
  - if omitted, a new patient record is created automatically using the `patient_name` column

Optional columns starting with `bio_` or `blood_` are accepted and processed according to the standard clinician assessment logic.

#### 8.7.3 Response Shape
```json
{
  "batch_id": "UUID",
  "summary": {
    "total": 10,
    "success": 8,
    "failed": 2
  },
  "results": [
    {
      "row_index": 1,
      "patient_id": "P-101",
      "patient_name": "Jane Doe",
      "status": "success",
      "result": { ... detailed assessment payload ... }
    },
    {
      "row_index": 2,
      "patient_id": "P-102",
      "patient_name": "Invalid User",
      "status": "failed",
      "error": "Missing mandatory clinical field: cli_age"
    }
  ]
}
```

#### 8.7.4 Error Behaviour
- **Empty CSV**: Returns `HTTP 400` if the CSV contains only headers and no data rows.
- **Invalid File Type**: Returns `HTTP 400` if the uploaded file is not a `.csv`.
- **Missing Columns**: Returns `HTTP 400` if any mandatory clinical columns are missing.
- **Unknown Patient ID**: If a `patient_id` value is provided but does not match any existing patient record, that row is marked as failed with the message `"Patient {id} not found. Register the patient before submitting a batch assessment."` The rest of the batch continues processing normally.

## 9. Runtime Components Used by the Routes

Loaded on startup in `api/main.py`:

```text
app.state.ensemble
app.state.explainer
app.state.ood_detector
app.state.wisconsin_preprocessor
app.state.ucth_preprocessor
app.state.coimbra_preprocessor
app.state.wisconsin_feature_names
app.state.ucth_feature_names
app.state.coimbra_feature_names
```

These are treated as application-scoped runtime dependencies. Routes do not create them dynamically.

## 10. Error Behaviour

### 10.1 Authentication Errors

| Condition | Status | Behaviour |
| --- | --- | --- |
| Missing or invalid token | `401` | Raised by JWT verification logic |
| Token missing required claims | `401` | Raised when `sub`, `email`, or `user_metadata.role` is missing |
| Valid token but wrong role | `403` | Raised by `require_role()` |

### 10.2 Validation Errors
...
### 10.3 Persistence Errors
When a database write fails during an assessment, the API returns `HTTP 500` with a structured error body to prevent silent data loss of clinical audit trails.

### 10.4 Startup Errors
...


If required artefacts are missing from `ml/saved_models/`, application startup fails during the lifespan initialisation sequence. The backend does not silently retrain or continue with partial machine learning state.

## 11. Implementation Notes That Affect Consumers

- route paths are `/member/assess` and `/clinician/assess`, not the older `/patient/assess` and `/doctor/assess`
- all protected requests require valid Supabase JWTs
- clinician blood panel payloads must not include `age`; the backend derives it from `clinical_data.age`
- UCTH clinical data is always required because the ensemble always depends on that pathway

## 12. Planned API Expansion

The current API surface only covers prediction. The repository structure and documentation anticipate future routes for:

- community features
- notifications
- profile management

Those routes do not exist in the current codebase and should be documented separately once implemented.
