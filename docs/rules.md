## MedSight API Engineering Rules

The law of the `medsight-api` codebase. Every rule in this document is mandatory.

## 1. Project Identity

- Project name: `medsight-api`
- Language: `Python 3.11`
- Package manager: `uv`
- Framework: `FastAPI`
- Windows Git Bash virtual environment activation command:

```bash
source .venv/Scripts/activate
```

- API entry point:

```bash
uvicorn api.main:app --reload
```

- Default API port: `8000`
- Training entry point:

```bash
python train.py
```

## 2. Repository Structure

The repository structure must remain aligned with the current domain split between API code, machine learning code, data, and documentation.

```text
medsight-api/
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── lib/
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── routers/
│   │   ├── __init__.py
│   │   └── predict.py
│   └── schemas/
│       ├── __init__.py
│       └── assessment.py
├── ml/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── wdbc_loader.py
│   │   ├── ucth_loader.py
│   │   ├── coimbra_loader.py
│   │   └── data_loader.py
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── wisconsin_preprocessor.py
│   │   ├── ucth_preprocessor.py
│   │   └── coimbra_preprocessor.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── wisconsin_model.py
│   │   ├── ucth_model.py
│   │   ├── coimbra_model.py
│   │   └── ensemble.py
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── shap_explainer.py
│   │   └── ood_detector.py
│   └── saved_models/
│       ├── wisconsin_model.pkl
│       ├── wisconsin_preprocessor.pkl
│       ├── ucth_model.pkl
│       ├── ucth_preprocessor.pkl
│       ├── coimbra_model.pkl
│       ├── coimbra_preprocessor.pkl
│       ├── shap_explainer.pkl
│       └── ood_detector.pkl
├── data/
│   └── raw/
│       ├── ucth_breast_cancer.csv
│       └── coimbra_breast_cancer.csv
├── docs/
├── train.py
├── test_shap.py
├── pyproject.toml
├── .python-version
├── .env
└── uv.lock
```

## 3. Naming Conventions

### Python General

All Python naming must follow `PEP 8`.

- Variables use `snake_case`.
- Functions use `snake_case`.
- Classes use `PascalCase`.
- Constants use `UPPER_SNAKE_CASE`.
- Private methods use a single leading underscore, for example `_build_payload`.
- Module-level constants use `UPPER_SNAKE_CASE`.

### Descriptive Names

This is the strictest naming rule in the codebase. Names must be explicit and descriptive.

- Never use acronyms in variable names.
- Never use single-letter names except simple loop indices such as `i` or `j` where the meaning is obvious.
- Never abbreviate words when the full word is practical.
- Name variables after what they contain, not what type they are.
- Prefer domain meaning over temporary shorthand.
- If a name could be misunderstood outside the current function, it is not descriptive enough.

Bad examples:

```python
X_train
y
df
scaler
clf
feat
```

Good examples:

```python
wisconsin_training_features
training_labels
ucth_dataframe
standard_scaler
random_forest_model
feature_columns
```

### ML-Specific Naming

Machine learning code must follow stable naming patterns so data flow is obvious.

- Data loaders return `features, labels, metadata`.
- Preprocessor factory functions use the pattern `build_*_preprocessor()`.
- Model trainer functions return `model, preprocessor, scores`.
- Scaled data variables are prefixed with `scaled_`.
- Pandas DataFrame variables are suffixed with `_dataframe`.
- Trained model variables are suffixed with `_model`.

Examples:

```python
scaled_wisconsin_training_features
ucth_dataframe
coimbra_dataframe
wisconsin_model
ucth_model
```

### File Naming

- All Python files use the `snake_case.py` pattern.
- Loader files are split per dataset and must never be consolidated.
- Preprocessor files are split per dataset and must never be consolidated.
- Model files are split per dataset and must never be consolidated.
- Schema files are named by domain, for example `assessment.py` and `auth.py`.

### API-Specific Naming

- Endpoint function names must describe the behaviour clearly.
- Member assessment endpoint function name: `member_assess`.
- Clinician assessment endpoint function name: `clinician_assess`.
- Role strings are always lowercase.

```python
"member"
"clinician"
```

- `patient_id` is a medical record identifier and must never be renamed to `member_id`.
- `patient_value` and `patient_features` are accepted clinical terms in machine learning and out-of-distribution code and must never be renamed for role-consistency reasons.

## 4. File and Module Rules

### Hard Rules

- `ml/data/wdbc_loader.py`, `ml/data/ucth_loader.py`, and `ml/data/coimbra_loader.py` remain separate files and must never be merged.
- `ml/preprocessing/wisconsin_preprocessor.py`, `ml/preprocessing/ucth_preprocessor.py`, and `ml/preprocessing/coimbra_preprocessor.py` remain separate files and must never be merged.
- `ml/models/wisconsin_model.py`, `ml/models/ucth_model.py`, and `ml/models/coimbra_model.py` remain separate files and must never be merged.
- All Pydantic schemas live in `api/schemas/`.
- Schema files are organised by domain, one file per domain.
- All shared API utilities live in `api/lib/`.
- API work and machine learning work are strictly separated. Do not touch `ml/` files during API-only work. Do not touch API files during machine learning-only work.
- `api/routers/predict.py` must never contain schema definitions.
- Every Python package directory must contain an `__init__.py` file.

### `train.py` Rules

`train.py` is the only valid top-level training entry point.

- `train.py` must be the single entry point for all training and artefact persistence.
- `train.py` must load preprocessors and models back from disk after training before fitting SHAP or out-of-distribution components.
- `train.py` must never rely on in-memory return values from trainer functions when fitting SHAP or out-of-distribution logic.
- `train.py` must produce all eight `.pkl` files in `ml/saved_models/`.
- `train.py` must print progress at each major step.
- `train.py` must expose a `main()` function.
- `train.py` must use:

```python
if __name__ == "__main__":
    main()
```

### `api/main.py` Rules

`api/main.py` owns application startup and shared runtime state.

- `api/main.py` must use the lifespan `asynccontextmanager` pattern.
- Never use `@app.on_event` in `api/main.py`.
- `api/main.py` must load all machine learning artefacts from disk on startup.
- `api/main.py` must never train or refit anything on startup.
- `api/main.py` must never import trainer functions.
- Shared machine learning state must be stored in `app.state` using these exact keys:

```python
ensemble
explainer
ood_detector
wisconsin_preprocessor
ucth_preprocessor
coimbra_preprocessor
wisconsin_feature_names
ucth_feature_names
coimbra_feature_names
```

## 5. ML Pipeline Rules

### Dataset Rules

- WDBC labels loaded from `sklearn` must always be flipped so that `1 = malignant` and `0 = benign`.
- UCTH missing values are encoded as `#` and must always be read with:

```python
na_values=["#"]
```

- UCTH `Breast` values contain trailing whitespace and must always be cleaned with:

```python
.str.strip()
```

- Coimbra labels must always be remapped from `1 = healthy` to `0 = benign`, and from `2 = patient` to `1 = malignant`.
- Dataset CSV files must remain separate. Never consolidate `ucth_breast_cancer.csv` and `coimbra_breast_cancer.csv`.
- WDBC is loaded from `sklearn` and must never be loaded from a CSV file.

### Preprocessing Rules

- Wisconsin preprocessing uses `SimpleImputer(strategy="median")` followed by `StandardScaler`.
- UCTH preprocessing uses `ColumnTransformer`.
- In UCTH preprocessing, numeric columns receive median imputation and scaling.
- In UCTH preprocessing, categorical columns receive mode imputation only.
- Never scale categorical columns.
- Coimbra preprocessing applies `log1p` first and `StandardScaler` second.
- Never scale discrete `0/1` categorical values.

### Ensemble Rules

- Ensemble weights are fixed at `40%` Wisconsin, `40%` UCTH, and `20%` Coimbra.
- UCTH clinical data is always required.
- Wisconsin inputs are optional.
- Coimbra inputs are optional.
- Dynamic weight normalisation applies when fewer than three datasets are provided.

### SHAP Rules

- Always use `TreeExplainer`.
- Never use `KernelExplainer`.
- Never use alternative SHAP explainers unless a new formal decision replaces this rule.
- SHAP value shape is expected to be `(1, n_features, 2)`.
- For the malignant class, indexing must always use:

```python
shap_values[0, :, 1]
```

- Never use:

```python
shap_values[1][0]
```

- Always use this masker configuration:

```python
shap.maskers.Independent(data, max_samples=100)
```

### OOD Rules

- The out-of-distribution threshold is `3.5` standard deviations.
- Never lower the threshold to `3.0`.
- Severity mapping is fixed:

```text
Minor: 3.5-5 standard deviations
Major: >5 standard deviations
```

- Out-of-distribution detection runs on UCTH clinical features only.
- Never run out-of-distribution detection on biopsy features.
- Never run out-of-distribution detection on blood panel features.
- Out-of-distribution fitting must use raw, unscaled UCTH training features.

### Saved Model Rules

- All eight saved artefacts must exist in `ml/saved_models/` before starting the API.
- Regenerate artefacts only through:

```bash
python train.py
```

- Never commit `.pkl` files to Git.
- Saved artefact filenames are fixed and must remain exactly:

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

## 6. API Rules

### Auth Rules

- JWT verification uses `PyJWT`.
- JWT verification must use:

```python
algorithms=["ES256"]
audience="authenticated"
```

- The Supabase JWT secret is loaded from the `SUPABASE_JWT_SECRET` environment variable.
- Role information is extracted from `user_metadata.role` in the JWT payload.
- `get_current_user` handles token extraction and verification.
- `require_role(role)` handles role enforcement through a dependency factory.
- Never hardcode secrets, tokens, or credentials.

### Endpoint Rules

- All API endpoints are prefixed with `/api` through router inclusion in `main.py`.
- Member endpoints live under `/api/member/*`.
- Member endpoints require `role == "member"`.
- Clinician endpoints live under `/api/clinician/*`.
- Clinician endpoints require `role == "clinician"`.
- Endpoint functions must always be `async`.
- Endpoint functions must remain thin.
- Business logic must not be embedded directly in endpoint bodies.

### Schema Rules

- All Pydantic schemas live in `api/schemas/`.
- New schema domains get their own file, for example `auth.py` or `notifications.py`.
- Schema class names use `PascalCase`.
- Never import unused schemas into router files.
- `age` must never be duplicated across schemas.
- `age` lives in `ClinicalData` only.
- Coimbra age is injected into the Coimbra DataFrame at runtime from `ClinicalData`.

### Error Handling Rules

- Missing JWT returns `HTTP 401`.
- Invalid JWT returns `HTTP 401`.
- Valid JWT with the wrong role returns `HTTP 403`.
- Invalid request bodies return `HTTP 422` through FastAPI and Pydantic validation.
- Missing machine learning artefacts on startup must fail loudly with a clear error.
- Never fail silently when required artefacts are missing.

## 7. Environment and Secrets

- All secrets and environment-specific values live in `.env` at the project root.
- `.env` must always be ignored by Git.
- `.env` must never be committed.
- A `.env.example` file must always exist at the project root.
- `.env.example` must use placeholder values only.
- Never place realistic-looking secrets, tokens, or identifiers in `.env.example`.
- `python-dotenv` must always be used.
- `load_dotenv()` must appear at the top of `main.py` before any other imports.
- Required environment variables:

```text
SUPABASE_JWT_SECRET
```

## 8. Code Style

### PEP 8 Compliance

- Follow `PEP 8` throughout the codebase.
- Use two blank lines between top-level definitions.
- Use one blank line between methods inside a class.
- Use one blank line inside functions to separate logical blocks.
- Never use two blank lines inside a function body.
- Maximum line length is `88` characters.
- Group imports in this order:

```text
standard library
third-party
local
```

- Separate import groups with one blank line.

### Comments

- Section comments sit flush against the code they introduce.
- Do not leave a blank line between a section comment and the first line under it.
- Comments explain why, not what.
- Remove stale comments immediately when code changes.
- Use inline comments only for non-obvious logic.
- Docstrings must follow `PEP 257`.
- Use triple double quotes for docstrings.
- Write docstrings in the imperative mood.
- Every class must have a docstring explaining what it represents.
- Every function and method must have a docstring in imperative mood explaining what it does.
- Never state the obvious.
- A comment above `import os` saying `# import os` is forbidden.
- Where a design decision was made, explain it in a comment.
- Explain decisions such as why `expire_on_commit=False`, why `NullPool`, and why a column is named differently from its Python attribute.
- Always use `server_default` for timestamps so the database clock is authoritative regardless of what process inserts the row.
- Always comment whether `ondelete="CASCADE"` or `ondelete="SET NULL"` was chosen and why at the point of the foreign key definition.
- Use British English in all comments and docstrings.
- Do not use filler phrases in comments.

Good docstring example:

```python
"""Return the weighted malignant risk score."""
```

Bad docstring example:

```python
"""Returns the weighted malignant risk score."""
```

### Imports

- Never import unused modules.
- Never import unused names.
- Never use wildcard imports.

```python
from module import *
```

- Use `from x import y` for specific imported names.
- Use `import x` when the module is used as a namespace.

## 9. Git Rules

- Use Conventional Commits for every commit.
- Allowed commit prefixes include:

```text
feat:
fix:
refactor:
chore:
docs:
test:
```

- Commit after each meaningful phase of work.
- Never combine unrelated work into one giant commit.
- Never commit any of the following:

```text
.env
.pkl files
.venv/
__pycache__/
*.pyc
```

- Branch names must follow these patterns:

```text
feat/description
fix/description
chore/description
```

## 10. Testing Rules

- Test files live in the `tests/` directory at the project root.
- Current test files are:

```text
tests/test_manual_assessments.py
tests/test_shap.py
tests/test_api.py
tests/test_batch_assessments.py
```

- Run both test files after any change to machine learning files.
- Run both test files after any change to API files.
- Never use multi-line `python -c "..."` commands on Windows Git Bash.
- Use test script files instead.
- The API must be running before `tests/test_api.py` is executed.
- All five API scenarios must pass:

```bash
.venv/Scripts/python tests/test_manual_assessments.py
.venv/Scripts/python tests/test_shap.py
.venv/Scripts/python tests/test_api.py
.venv/Scripts/python tests/test_batch_assessments.py
```

```text
member low risk
member high risk
clinician clinical only
clinician clinical + biopsy
clinician all 3 datasets
```

## 11. Decisions Already Made - Never Revisit

| Decision | Choice | Reason |
| --- | --- | --- |
| Auth service | `Supabase` | Medical data must stay in the product's own database, so `Clerk` was rejected |
| JWT library | `PyJWT` | `python-jose` is effectively abandoned and had no release for three years |
| ML algorithm | `Random Forest` | Works well on small datasets, provides calibrated probabilities, and is compatible with SHAP |
| Separate models per dataset | `Yes` | Each dataset has a different feature space and requires independent modelling |
| Ensemble weights | `WDBC 40% / UCTH 40% / Coimbra 20%` | Based on dataset size and recall performance |
| OOD threshold | `3.5 standard deviations` | `3.0` caused false positives on normal patients |
| Label convention | `1 = malignant, 0 = benign` | Keeps all three datasets aligned under one classification convention |
| Package manager | `uv` | Standard package management choice for this repository |
| UCTH always required | `Yes` | It is the base clinical input and the supervisor is a creator of the dataset |
| API startup pattern | `lifespan asynccontextmanager` | `on_event` is deprecated in FastAPI |
| Shared utilities location | `api/lib/` | Mirrors established JavaScript and TypeScript community convention |
