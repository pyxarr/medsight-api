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

Persistent application state is planned for Supabase. The current codebase already verifies Supabase-issued JWTs but does not yet persist assessments or user records to a database.

## Quick Start 🚀

After the environment is configured:

```bash
.venv/Scripts/python train.py
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
├── ml/                   # ML pipeline code
├── data/raw/             # Raw CSV datasets
├── docs/                 # Project docs
├── train.py              # Training entry point
├── test_shap.py          # ML verification script
├── test_api.py           # API verification script
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
source .venv/Scripts/activate
```

3. Configure environment variables in a root `.env` file.

```env
SUPABASE_JWT_SECRET=your_supabase_jwt_secret_here
```

`SUPABASE_JWT_SECRET` is required because every protected endpoint verifies Supabase-issued JWTs locally.

4. Train artefacts before starting the API.

```bash
python train.py
```

If your terminal has Windows encoding issues during training, run:

```bash
export PYTHONIOENCODING=utf-8 && .venv/Scripts/python train.py
```

5. Start the API.

```bash
uvicorn api.main:app --reload
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
POST /api/clinician/assess
Authorization: Bearer <supabase_jwt>
```

Purpose:

- requires clinical data
- accepts optional biopsy data
- accepts optional blood panel data
- returns detailed ensemble output, SHAP drivers, and out-of-distribution warnings

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

Always required.

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
.venv/Scripts/python test_api.py
```

`test_api.py` exercises the current `/api/member/assess` and `/api/clinician/assess` routes across five scenarios and requires a valid JWT.

## Current State 📍

Implemented now:

- FastAPI application startup through lifespan
- JWT verification against Supabase secret
- role-based access control for member and clinician routes
- multi-model inference pipeline
- persisted model loading from disk
- SHAP explainability for clinician results
- out-of-distribution warnings on UCTH clinical input

Not implemented yet:

- Supabase database reads and writes
- assessment history persistence
- batch CSV upload endpoint
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
