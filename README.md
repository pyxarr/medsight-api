# MedSight API

Backend API and machine learning serving layer for MedSight.

![Python 3.11](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688) ![uv](https://img.shields.io/badge/Package%20Manager-uv-6E56CF)

## Overview 🩺

`medsight-api` is the Python backend for the MedSight mobile application. It serves two tightly connected responsibilities in one repository:

- a FastAPI HTTP API for the mobile client
- a scikit-learn machine learning pipeline for breast cancer risk assessment

The repository is split by concern, not by service boundary. The API is a thin inference layer over trained machine learning artefacts, so separating backend and model code into different services would add deployment and coordination overhead without solving a real architectural problem.

The current backend exposes protected assessment endpoints for two roles:

- `member`: simplified, clinical-data-only assessment
- `clinician`: detailed multi-input assessment with explainability and warnings

Persistent application state is managed in Supabase. The codebase verifies Supabase-issued JWTs and persists clinician assessments and user records to a database.

## Quick Start 🚀

After the environment is configured:

```bash
# Windows (Git Bash)
.venv/Scripts/python train.py

# Linux / WSL
python train.py

# Start the API (both platforms)
uvicorn api.main:app --reload
```

Default address:

```text
http://127.0.0.1:8000
```

## Repository Layout 🗂️

```text
medsight-api/
├── api/                  # FastAPI app
│   ├── routers/              # Nested role-based routers (including user.py)
│   ├── schemas/              # Pydantic request schemas (including user.py)
│   └── db/                   # Database access layer
│       └── repositories/     # Data access logic (including user_repository.py)
├── ml/                   # ML pipeline code
├── data/raw/             # Raw CSV datasets
├── docs/                 # Project docs
├── train.py              # Training entry point
├── test_shap.py          # ML verification script
├── test_api.py           # API verification script
├── tests/                # Integration test suite
│   └── test_manual_assessments.py # member and clinician assessment flows
├── pyproject.toml        # Project metadata
└── uv.lock               # Locked dependencies
```

## Runtime Model ⚙️

The backend does not train models during API startup or request handling.

Training happens offline through:

```bash
python train.py
```

That command produces eight persisted artefacts in `ml/saved_models/`:

```text
wisconsin_model.pkl
wisconsin_preprocessor.pkl
ucth_model.pkl
ucth_preprocessor.pkl
coimbra_model.pkl
coimbra_preprocessor.pkl
shap_explainer.pkl
ood_detector.pkl
```

At API startup, `api/main.py` loads those artefacts into `app.state` and keeps them in memory for inference.

## Tech Stack 🧰

| Technology | Purpose |
| --- | --- |
| `Python 3.11` | Runtime |
| `FastAPI` | HTTP API |
| `Uvicorn` | ASGI server |
| `scikit-learn` | Model training and inference |
| `pandas` | DataFrame handling |
| `numpy` | Numerical operations |
| `SHAP` | Explainability |
| `joblib` | Artefact persistence |
| `PyJWT` | JWT verification |
| `python-dotenv` | Environment loading |
| `uv` | Dependency management |

## Local Setup 🛠️

1. Sync the environment.

```bash
uv sync
```

2. Activate the virtual environment in Windows Git Bash.

```bash
# Windows (Git Bash)
source .venv/Scripts/activate

# Linux / WSL
source .venv/bin/activate
```

3. Configure environment variables in a root `.env` file.

```env
SUPABASE_URL=https://your-project-ref.supabase.co
DATABASE_URL=your_postgresql_connection_string
SUPABASE_SECRET_KEY=your_supabase_service_role_key
```

`SUPABASE_JWT_SECRET` is no longer used. Verification now relies on the Supabase public key endpoint.

4. Train artefacts before starting the API.

```bash
python train.py
```

If your terminal has Windows encoding issues during training, run:

```bash
# Windows encoding issues
export PYTHONIOENCODING=utf-8 && .venv/Scripts/python train.py

# Linux / WSL
export PYTHONIOENCODING=utf-8 && python train.py
```
The ml/saved_models/ directory is created automatically by train.py if it does not exist.

5. Start the API.

```bash
uvicorn api.main:app --reload
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Current Endpoints 🔌

### Health

```http
GET /
```

Response:

```json
{
  "message": "Breast Cancer DSS API is running."
}
```

### Member Assessment

```http
POST /api/member/assess
Authorization: Bearer <supabase_jwt>
```

Purpose:

- accepts clinical data only
- uses the UCTH clinical model path
- returns a simplified result without technical model detail

### Clinician Assessment
```http
POST /api/clinician/manual-assess
POST /api/clinician/batch-assess
Authorization: Bearer <supabase_jwt>
```
Purpose:
- Manual: accepts clinical data and optional biopsy/blood data for single patient entry
- Batch: accepts CSV or XLSX upload for bulk processing and session tracking
- returns detailed ensemble output, SHAP drivers, and out-of-distribution warnings


### Clinician History
```http
GET /api/clinician/assessments
GET /api/clinician/assessments/{id}
DELETE /api/clinician/assessments/{id}
Authorization: Bearer <supabase_jwt>
```
Purpose:
- retrieve a paginated list of past assessments
- view detailed records of specific assessments
- soft-delete obsolete assessment records

### User Profile
```http
GET /api/users/me
Authorization: Bearer <supabase_jwt>
```
Purpose: returns the authenticated user's profile, creating a product user record on first request if one does not exist.

## Authentication 🔐

The mobile client authenticates directly with Supabase. The backend never issues tokens and never stores sessions.

For protected requests:

1. the mobile app obtains a JWT from Supabase
2. the JWT is attached as `Authorization: Bearer <token>`
3. FastAPI verifies the token with `PyJWT`
4. the role is read from `user_metadata.role`
5. route access is enforced with `require_role()`

Expected roles:

```text
member
clinician
```

## Machine Learning Summary 🤖

The pipeline uses three separate Random Forest models trained on three separate datasets:

- `WDBC`: biopsy / fine needle aspiration features
- `UCTH`: clinical features
- `Coimbra`: blood biomarker features

The ensemble combines available model probabilities with weighted averaging:

- Wisconsin: `0.4`
- UCTH: `0.4`
- Coimbra: `0.2`

Only UCTH clinical input is required. Wisconsin and Coimbra inputs are optional.

The backend also loads:

- `RiskExplainer` for SHAP-based feature attribution
- `OutOfDistributionDetector` for clinical-feature boundary warnings

## Request Models 🧾

Defined in `api/schemas/assessment.py`.

### `ClinicalData`
Always required. Categorical fields accept both integers and human-readable strings.

Fields:
- `age`
- `menopause`
- `tumor_size_cm`
- `invasive_nodes`
- `breast_side`
- `metastasis`
- `breast_quadrant`
- `breast_disease_history`

### `BiopsyData`

Optional clinician-only fine needle aspiration measurements based on the Wisconsin dataset feature space.

### `BloodPanelData`

Optional clinician-only blood biomarkers based on the Coimbra dataset feature space.

Important detail:

- `age` is not part of `BloodPanelData`
- the backend injects `ClinicalData.age` into the Coimbra DataFrame at runtime

## Verification Workflow ✅

### Training verification

```bash
.venv/Scripts/python test_shap.py
```

This script exercises:

- dataset loading
- model training
- ensemble prediction
- SHAP explanation generation
- out-of-distribution detection

### API verification
Start the API first, then run:

```bash
.venv/Scripts/python tests/test_api.py
```

`test_api.py` exercises the current `/api/member/assess`, `/api/clinician/manual-assess`, and `/api/clinician/batch-assess` routes across five scenarios and requires a valid JWT.

Additionally, `tests/test_manual_assessments.py` provides a comprehensive integration test suite for member and clinician manual assessment flows.

## Current State 📍

Implemented now:

- FastAPI application startup through lifespan
- JWT verification using ES256 JWKS-based verification via Supabase's public key endpoint
- role-based access control for member and clinician routes
- multi-model inference pipeline
- persisted model loading from disk
- SHAP explainability for clinician results
- out-of-distribution warnings on UCTH clinical input
- clinician assessment persistence and history management
- clinician batch upload and storage integration
- Supabase database integration via SQLAlchemy

Not implemented yet:

- profile endpoints
- community endpoints
- notifications
- PDF report generation

## Related Repository 📱

The frontend lives in a separate repository:

```text
medsight
```

That repository contains the Expo React Native mobile application that authenticates with Supabase and consumes this backend.

## Documentation 📚

| Document | Description |
| --- | --- |
| `docs/architecture.md` | System structure and runtime composition |
| `docs/rules.md` | Engineering rules and non-negotiable conventions |
| `docs/api.md` | Endpoint, auth, schema, and response details |
| `docs/ml-pipeline.md` | Datasets, preprocessing, models, ensemble, SHAP, OOD, and training flow |
| `docs/database.md` | Current persistence status and target Supabase data model |
| `docs/plan.md` | Backend delivery plan and implementation phases |
