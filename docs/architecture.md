## MedSight API Architecture

## 1. System Overview

`medsight-api` is the backend and machine learning engine for the MedSight mobile application. It serves two tightly connected concerns: an HTTP API built with FastAPI and a machine learning pipeline built with scikit-learn. Both concerns live in the same repository because the API is only a thin serving layer over the machine learning pipeline. The backend does not expose a broad business platform with independent service boundaries, so separating the API and machine learning code would add coordination overhead without improving maintainability.

The API is stateless. Persistent application data belongs in Supabase, not in backend memory or local server state. The machine learning layer is also static at runtime. Models are trained ahead of time, saved to disk as artefacts, loaded on application startup, and used only for inference in production. The backend never retrains models during normal API operation. The wider MedSight system is split across two repositories: `medsight-api`, which contains the backend and machine learning code, and `medsight`, which contains the Expo React Native mobile client.

## 2. High-Level Architecture Diagram

```text
                         +-----------------------------+
                         |     Expo Mobile App         |
                         |         medsight            |
                         +-------------+---------------+
                                       |
                      Register / Login  |  HTTPS + JWT
                         via SDK        |
                                       v
                 +----------------+    +-----------------------------+
                 | Supabase Auth  |    |    FastAPI Backend          |
                 |   JWT issuer   |    |       medsight-api          |
                 +-------+--------+    +-------------+---------------+
                         ^                           | \
                         |                           |  \
                         |                           |   \
                         |                           v    v
                         |                 +--------------------+   +----------------------+
                         |                 |   ML Pipeline      |   | Supabase PostgreSQL |
                         |                 | inside medsight-api|   |      database       |
                         |                 +--------------------+   +----------------------+
                         |
                         +--------------------------------------------------------------+
```

## 3. Repository Structure

```text
medsight-api/                               # Backend and machine learning repository
├── api/                                    # FastAPI application package
│   ├── __init__.py                         # Marks api as a Python package
│   ├── main.py                             # FastAPI entry point, startup loading, router registration
│   ├── lib/                                # Shared API utilities
│   │   ├── __init__.py                     # Marks api.lib as a Python package
│   │   └── auth.py                         # JWT verification and role enforcement helpers
│   ├── routers/                            # API route modules
│   │   ├── __init__.py                     # Marks api.routers as a Python package
│   │   ├── member/                         # Member domain endpoints
│   │   │   ├── __init__.py                 # Aggregates member routers
│   │   │   └── assess.py                   # Member assessment endpoints
│   │   └── clinician/                      # Clinician domain endpoints
│   │       ├── __init__.py                 # Aggregates clinician routers
│   │       ├── assess.py                   # Clinician assessment endpoints
│   │       └── history.py                  # Clinician assessment history endpoints
│   └── schemas/                            # Pydantic request schema package
│       ├── __init__.py                     # Marks api.schemas as a Python package
│       ├── assessment.py                   # Assessment request models for member and clinician flows
│       └── assessment_history.py           # Response models for assessment history and details
│   └── db/                                 # Database access layer
│       ├── __init__.py                     # Marks api.db as a Python package
│       ├── base.py                         # SQLAlchemy DeclarativeBase
│       ├── session.py                      # Async session configuration
│       ├── models/                         # ORM models
│       │   ├── __init__.py                 # Marks api.db.models as a Python package
│       │   └── assessment.py               # Assessment table definition
│       └── repositories/                   # Data access repositories
│           ├── __init__.py                     # Marks api.db.repositories as a Python package
│           ├── assessment_repository.py    # CRUD operations for assessments
│           └── user_repository.py          # User profile lookup and upsert logic
├── ml/                                     # Machine learning package
│   ├── __init__.py                         # Marks ml as a Python package
│   ├── data/                               # Dataset loading logic
│   │   ├── __init__.py                     # Marks ml.data as a Python package
│   │   ├── wdbc_loader.py                  # Loads the sklearn Wisconsin biopsy dataset
│   │   ├── ucth_loader.py                  # Loads the UCTH clinical dataset from CSV
│   │   ├── coimbra_loader.py               # Loads the Coimbra blood biomarker dataset from CSV
│   │   └── data_loader.py                  # Shared dataset loading orchestration helpers
│   ├── preprocessing/                      # Dataset-specific preprocessing pipelines
│   │   ├── __init__.py                     # Marks ml.preprocessing as a Python package
│   │   ├── wisconsin_preprocessor.py       # Wisconsin imputation and scaling pipeline
│   │   ├── ucth_preprocessor.py            # UCTH mixed-type preprocessing pipeline
│   │   └── coimbra_preprocessor.py         # Coimbra log transform and scaling pipeline
│   ├── models/                             # Dataset-specific model training and ensemble logic
│   │   ├── __init__.py                     # Marks ml.models as a Python package
│   │   ├── wisconsin_model.py              # Trains and persists the Wisconsin model
│   │   ├── ucth_model.py                   # Trains and persists the UCTH model
│   │   ├── coimbra_model.py                # Trains and persists the Coimbra model
│   │   └── ensemble.py                     # Combines model outputs into one risk score
│   ├── inference/                          # Explainability and distribution-checking components
│   │   ├── __init__.py                     # Marks ml.inference as a Python package
│   │   ├── shap_explainer.py               # SHAP explainability wrapper and persistence
│   │   └── ood_detector.py                 # Out-of-distribution detection and persistence
│   └── saved_models/                       # Persisted trained artefacts loaded by the API
│       ├── wisconsin_model.pkl             # Trained Wisconsin Random Forest model
│       ├── wisconsin_preprocessor.pkl      # Wisconsin preprocessing pipeline
│       ├── ucth_model.pkl                  # Trained UCTH Random Forest model
│       ├── ucth_preprocessor.pkl           # UCTH preprocessing pipeline
│       ├── coimbra_model.pkl               # Trained Coimbra Random Forest model
│       ├── coimbra_preprocessor.pkl        # Coimbra preprocessing pipeline
│       ├── shap_explainer.pkl              # Persisted SHAP explainer bundle
│       └── ood_detector.pkl                # Persisted out-of-distribution detector
├── data/                                   # Raw source data directory
│   └── raw/                                # Raw dataset storage
│       ├── ucth_breast_cancer.csv          # Raw UCTH dataset file
│       └── coimbra_breast_cancer.csv       # Raw Coimbra dataset file
├── docs/                                   # Project documentation directory
├── train.py                                # Training and artefact generation entry point
├── test_shap.py                            # SHAP and training verification script
├── pyproject.toml                          # Project metadata and dependency configuration
├── .python-version                         # Python version pinning file
├── .env                                    # Local environment variables and secrets
└── uv.lock                                 # Locked dependency graph for uv
```

## 4. API Layer

### 4.1 Entry Point (`api/main.py`)

`api/main.py` initialises the FastAPI application using the lifespan `asynccontextmanager` pattern. Startup is responsible for loading every machine learning artefact required for inference into `app.state`. The startup sequence loads all eight persisted artefacts from disk rather than training or refitting anything in memory.

`load_dotenv()` is called before any other imports so environment variables are available during the rest of module initialisation. The application includes the prediction router with an `/api` prefix so all public assessment endpoints are grouped under one API namespace.

`app.state` uses fixed keys so router code can rely on stable runtime names:

- `ensemble`: the `BreastCancerEnsemble` object used to combine model outputs
- `explainer`: the `RiskExplainer` instance used for SHAP feature attribution
- `ood_detector`: the `OutOfDistributionDetector` instance used for clinical feature boundary checks
- `wisconsin_preprocessor`: the persisted Wisconsin preprocessing pipeline
- `ucth_preprocessor`: the persisted UCTH preprocessing pipeline
- `coimbra_preprocessor`: the persisted Coimbra preprocessing pipeline
- `wisconsin_feature_names`: the ordered feature names for Wisconsin biopsy inference
- `ucth_feature_names`: the ordered feature names for UCTH clinical inference
- `coimbra_feature_names`: the ordered feature names for Coimbra blood-panel inference

### 4.2 Authentication (`api/lib/auth.py`)

Authentication is performed on the mobile client through Supabase. The backend does not create sessions and does not issue tokens. FastAPI only verifies the JWT presented by the client.

`api/lib/auth.py` uses `PyJWT` with ES256 asymmetric signing. `PyJWKClient` is initialised at module level and fetches the public key from the Supabase JWKS endpoint. `SUPABASE_JWT_SECRET` is no longer used.

The module defines a `CurrentUser` Pydantic model containing `id`, `email`, and `role`. The `get_current_user` dependency extracts the Bearer token from the incoming request, decodes and verifies the JWT (with a 60-second leeway to handle clock skew between servers), then returns a populated `CurrentUser`. The `require_role(role)` dependency factory wraps `get_current_user` and raises `HTTP 403` when the authenticated user's role does not match the route requirement.

To bridge the gap between Supabase Auth identity and the product's own user records, the API implements an "upsert on first request" pattern. When a clinician submits an assessment or requests their profile via `GET /api/users/me`, the `UserRepository.get_or_create_from_auth_user` method is called. This ensures a product-level user record exists in the `users` table before any assessment persistence occurs.

The backend expects the Supabase JWT payload structure to provide:

- `sub` as the user identifier
- `email` as the user email address
- `user_metadata.role` as the application role

### 4.3 Routers (Role-Based Module Pattern)

The API uses a nested module pattern to separate concerns by user role and feature. Each role has its own package in `api/routers/` that aggregates feature-specific routers.

#### Member Domain (`api/routers/member/`)
- `assess.py`: Handles the simplified member assessment flow.

#### Clinician Domain (`api/routers/clinician/`)
- `assess.py`: Handles clinician assessments via manual entry or bulk CSV upload. Both paths persist results to the database.
- `history.py`: Handles paginated history lists, detailed record retrieval, and soft-deletion of assessments.
- `inference_service.py`: Decouples the ML inference, OOD checking, and SHAP explanation logic from the route handlers.

This structure ensures that as the API expands, files remain small and dependencies remain isolated. For example, the history router does not need to load machine learning artefacts, while the assessment router does not need to manage pagination logic.

### 4.4 Schemas (`api/schemas/assessment.py`)

`api/schemas/assessment.py` defines the request contracts for the assessment flows.

- `ClinicalData`: 8 required clinical fields
- `BiopsyData`: 30 biopsy fields
- `BloodPanelData`: 8 blood-panel fields, with age excluded and injected from `ClinicalData` at runtime
- `MemberPredictionRequest`: wraps `patient_id` and `ClinicalData`
- `ClinicianPredictionRequest`: wraps `patient_id`, `ClinicalData`, optional `BiopsyData`, and optional `BloodPanelData`

The schema split keeps validation separate from routing and prevents request model definitions from leaking into route modules.

## 5. ML Pipeline Layer

### 5.1 Overview

The machine learning pipeline is built from three independent models trained on three different datasets with different feature spaces. Because the input modalities are not interchangeable, each dataset has its own loader, preprocessor, and model. A weighted ensemble combines the available model probabilities into one final risk score. SHAP adds feature-level explainability so prediction outputs can be inspected rather than treated as black-box results. Out-of-distribution detection checks whether a patient's clinical values are unusually far from the training distribution, which helps flag weak generalisation cases.

All pipeline components are created through `train.py`, persisted to disk, and then loaded by the API for inference. The API never retrains models and never rebuilds explainers at runtime.

### 5.2 Datasets

| Dataset | Source | Samples | Features | Modality | Label Convention |
| --- | --- | --- | --- | --- | --- |
| WDBC | sklearn built-in | 569 | 30 continuous FNA measurements | Biopsy | sklearn `0=malignant` flipped to `1=malignant` |
| UCTH | Mendeley Data / Kaggle | 213 | 8 mixed clinical features | Clinical records | `Malignant=1`, `Benign=0` |
| Coimbra | UCI Repository | 116 | 9 continuous blood biomarkers | Blood panel | `1=healthy -> 0`, `2=patient -> 1` |

### 5.3 Preprocessing

#### Wisconsin

Wisconsin preprocessing applies `SimpleImputer(strategy="median")` followed by `StandardScaler`. Median imputation is used because fine needle aspiration measurements can contain outliers, and the median is more robust than the mean for this kind of continuous feature space.

#### UCTH

UCTH preprocessing uses a `ColumnTransformer`. Numeric columns receive median imputation followed by `StandardScaler`. Categorical columns receive mode imputation only. Categorical values are not scaled because discrete values such as `0` and `1` carry category meaning that is distorted when converted into scaled continuous magnitudes.

#### Coimbra

Coimbra preprocessing applies `log1p` before `StandardScaler`. The `log1p` step is used because several blood biomarkers, including insulin, leptin, and resistin, are strongly right-skewed. Log transformation compresses large values while safely handling zero values.

### 5.4 Models

| Model | Algorithm | Config | Accuracy | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Wisconsin | Random Forest | `n_estimators=100, class_weight=balanced` | 0.974 | 1.000 | 0.929 | 0.963 |
| UCTH | Random Forest | `n_estimators=100, class_weight=balanced` | 0.884 | 0.889 | 0.842 | 0.865 |
| Coimbra | Random Forest | `n_estimators=100, class_weight=balanced` | 0.708 | 0.800 | 0.615 | 0.696 |

Random Forest was chosen because it performs well on small datasets, handles mixed feature types naturally, provides probability outputs suitable for risk scoring, supports `class_weight=balanced` for class imbalance, and works directly with SHAP `TreeExplainer`.

### 5.5 Ensemble

The ensemble combines the three dataset-specific model probabilities into a single final risk score.

- Weights are fixed at Wisconsin `40%`, UCTH `40%`, and Coimbra `20%`.
- The weighting reflects three factors: WDBC is the largest and most accurate dataset, UCTH is clinically central for Nigerian patients, and Coimbra is the smallest with the weakest recall.
- Dynamic weight normalisation is applied when fewer than three datasets are present.
- UCTH is always required.
- Wisconsin is optional.
- Coimbra is optional.
- The final risk score is the weighted average of the available model probabilities.
- Risk level thresholds are:

```text
High   >= 0.7
Medium >= 0.3
Low    < 0.3
```

- Cross-dataset agreement is derived from prediction spread:

```text
High        spread <= 0.2
Mixed       spread <= 0.4
Low         spread > 0.4
Single Model when only one model is available
```

- Confidence is calculated as:

```text
abs(final_risk_score - 0.5) * 2
+ 0.05 for each additional model
capped at 1.0
```

### 5.6 SHAP Explainability

Explainability is implemented through the `RiskExplainer` class in `ml/inference/shap_explainer.py`. The class uses `shap.TreeExplainer` together with:

```python
shap.maskers.Independent(data, max_samples=100)
```

One explainer is created per dataset model. SHAP values are expected in the shape `(1, n_features, 2)`, and the malignant class is always indexed with:

```python
shap_values[0, :, 1]
```

The explainer returns the top N drivers sorted by absolute SHAP magnitude. Each driver includes the feature name, dataset source, direction (`increases_risk` or `decreases_risk`), and contribution percentage. The persisted explainer is stored at:

```text
ml/saved_models/shap_explainer.pkl
```

### 5.7 Out-of-Distribution Detection

Out-of-distribution detection is implemented through the `OutOfDistributionDetector` class in `ml/inference/ood_detector.py`. It is fitted on raw, unscaled UCTH training features so the detector measures deviation in the original clinical value space rather than transformed feature space.

- Threshold: `3.5` standard deviations from the training mean
- Severity `Minor`: `3.5-5` standard deviations
- Severity `Major`: `>5` standard deviations
- Scope: clinical features only
- Never applied to biopsy features
- Never applied to blood-panel features

The persisted detector is stored at:

```text
ml/saved_models/ood_detector.pkl
```

### 5.8 Training Pipeline (`train.py`)

`train.py` runs the full artefact build pipeline in this exact sequence:

1. Load all three datasets.
2. Train all three models, which saves six `.pkl` files automatically.
3. Load the saved preprocessors back from disk.
4. Scale or transform the full training feature sets using the loaded preprocessors.
5. Load the saved models from disk.
6. Fit `RiskExplainer` on the three loaded models and the transformed training features, then save it to disk.
7. Fit `OutOfDistributionDetector` on raw UCTH training features, then save it to disk.

This sequence guarantees that downstream explainability and distribution-checking components are fitted against the persisted preprocessing and model artefacts rather than temporary in-memory training return values.

### 5.9 Startup Loading (`api/main.py` lifespan)

The application startup sequence follows this exact order:

1. `load_dotenv()`
2. Load `BreastCancerEnsemble` through `ensemble.load()`
3. Load `RiskExplainer` through `RiskExplainer.load()`
4. Load `OutOfDistributionDetector` through `OutOfDistributionDetector.load()`
5. Load the three preprocessors through `joblib.load()`
6. Load the three datasets for feature names only
7. Store all runtime objects in `app.state`

## 6. Authentication Architecture

Authentication starts and ends with Supabase on the client side. The Expo application calls the Supabase SDK directly for registration, login, and Google OAuth. Supabase returns the JWT and session data. The Expo client stores the JWT in `SecureStore` and attaches it to every protected backend request in the `Authorization: Bearer <token>` header.

On the backend, the `get_current_user` dependency verifies the JWT on every protected request. The user's role is extracted from the token payload, and route access is enforced through `require_role()`. The backend never issues tokens, never stores sessions, and never needs to contact Supabase for request-time authentication because verification is local using the public key fetched from the JWKS endpoint.

```text
Register / Login / Google OAuth
  -> Expo calls Supabase SDK directly
  -> Supabase returns JWT + session
  -> Expo stores JWT in SecureStore

Every protected API request:
  -> Expo attaches JWT in Authorization header
  -> FastAPI get_current_user extracts + verifies JWT
  -> Role checked by require_role()
  -> Request proceeds or raises 401/403
```

## 7. Data Flow

### 7.1 Member Assessment Request

1. A member submits the clinical assessment form in the Expo application.
2. The Expo client sends `POST /api/member/assess` with a JWT and a `MemberPredictionRequest` body.
3. FastAPI verifies the JWT and checks that `role == "member"`.
4. `ClinicalData` is converted into `ucth_dataframe`.
5. The out-of-distribution detector checks `ucth_dataframe` against the training distribution.
6. The ensemble predicts using `ucth_dataframe` only.
7. The API returns a simplified response containing `risk_level`, `guidance`, `has_warning`, and `warning_message`.

### 7.2 Clinician Assessment Request
1. A clinician submits a form (Manual) or a CSV file (Batch) in the Expo application.
2. The Expo client sends `POST /api/clinician/manual-assess` or `POST /api/clinician/batch-assess` with a JWT.
3. FastAPI verifies the JWT and checks that `role == "clinician"`.
4. For Manual entry: `PatientRepository` creates or retrieves the patient identity.
5. For Batch entry: The CSV is uploaded to Supabase Storage, a `Batch` record is created, and the file is parsed row-by-row.
6. For each assessment:
    - `ClinicalData` is converted into `ucth_dataframe`.
    - `BiopsyData`, when present, is converted into `wisconsin_dataframe`.
    - `BloodPanelData`, when present, is converted into `coimbra_dataframe`.
    - The out-of-distribution detector checks `ucth_dataframe`.
    - The ensemble predicts using all available DataFrames.
    - The SHAP explainer generates feature-level explanations.
7. The `AssessmentRepository` persists the patient ID, input features, final risk score, and SHAP drivers to the `assessments` table.
8. The API returns the full clinician report (or a batch summary).


## 8. Technology Stack

| Component | Technology | Version | Purpose |
| --- | --- | --- | --- |
| API framework | FastAPI | latest | HTTP API, dependency injection, request validation |
| ML framework | scikit-learn | latest | Random Forest models, preprocessing pipelines |
| Explainability | SHAP | latest | TreeExplainer for feature attribution |
| Data processing | pandas + numpy | latest | DataFrame operations |
| Model persistence | joblib | latest | Serialising and loading ML artefacts |
| JWT verification | PyJWT | latest | Verifying Supabase-issued JWTs |
| Auth + Database | Supabase | latest | User identity and PostgreSQL database |
| Environment | python-dotenv | latest | Loading `.env` variables |
| Package manager | uv | latest | Dependency management and virtual environments |
| Python version | Python | 3.11 | Runtime |
| ASGI server | Uvicorn | latest | Serving the FastAPI application |

## 9. Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `SUPABASE_URL` | Yes | Base URL for Supabase API services (used for JWKS and Storage) |
| `DATABASE_URL` | Yes | Connection string for the Supabase PostgreSQL database |
| `SUPABASE_SECRET_KEY` | Yes | Service role key for privileged Supabase operations (used for Storage) |

More variables will be added as Supabase database integration is implemented.

## 10. Planned Additions

The current architecture is designed to expand into persistent product workflows without changing the core machine learning serving model. Planned additions include `users` table and `notifications` table. The API surface will expand beyond prediction and history to cover batch upload, community, notifications, and profile flows. Clinician assessment output is also expected to grow into PDF report generation for export and sharing. Research workflows will require a dedicated batch CSV processing endpoint. Mobile engagement flows are expected to add push notifications through Expo Notifications.
