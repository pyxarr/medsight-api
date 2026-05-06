# Agent Instructions — medsight-api

You are working on the backend and machine learning repository for MedSight, an intelligent clinical decision support system for breast cancer risk assessment built for Nigerian and West African patient populations.

## Step 0 — Before touching anything

Read `docs/rules.md` in full before writing any code, creating any file, editing any file, or running any command. Every rule in that document is mandatory and non-negotiable. If a task conflicts with a rule in `docs/rules.md`, the rule wins.

## Repository identity

- Language: Python 3.11
- Package manager: `uv`
- Framework: FastAPI
- ORM: SQLAlchemy 2.0 (async)
- Migrations: Alembic
- Auth: Supabase JWT verification via PyJWT
- Database: Supabase PostgreSQL via SQLAlchemy + asyncpg
- ML: scikit-learn, SHAP, joblib

## Repository structure

```text
api/          FastAPI application — routers, schemas, lib, db, models
ml/           Machine learning pipeline — data, preprocessing, models, inference
alembic/      Database migration scripts
docs/         Project documentation
train.py      ML training entry point — the only valid way to retrain
```

## Domain separation — hard rule

API work and ML work are strictly separate domains.

- When working on API features, never touch anything inside `ml/`
- When working on ML features, never touch anything inside `api/`
- The only exception is `api/main.py` startup loading, which references both

## Naming conventions

- Variables and functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- No acronyms in variable names under any circumstances
- No single-letter names except loop indices
- Names must describe what the variable contains, not its type
- Bad: `X_train`, `y`, `df`, `clf`, `feat`
- Good: `wisconsin_training_features`, `training_labels`, `ucth_dataframe`

## Comment and docstring rules

These rules apply to every file you create or edit. Read `docs/rules.md` section 8 for the full detail. Summary:

- Every class must have a docstring explaining what it represents
- Every function and method must have a docstring in imperative mood
- Comments explain why, not what — the code already shows what
- Never state the obvious — `# import os` above `import os` is forbidden
- Section comments sit flush against the code they introduce — no blank line between the comment and the first line of code under it
- Explain every design decision inline where it was made
- British English throughout — no American spelling
- No filler phrases in comments or docstrings

Docstring style:

```python
# Good
def calculate_risk_score() -> float:
    """Return the weighted ensemble risk score for the current patient."""

# Bad
def calculate_risk_score() -> float:
    """This function calculates and returns the risk score."""
```

## SQLAlchemy rules

- Always use SQLAlchemy 2.0 style — `Mapped`, `mapped_column`, `DeclarativeBase`
- Never use legacy `Column()` or `declarative_base()`
- Always use `server_default=func.now()` for timestamp columns — never `default=func.now()`
- Always comment `ondelete` choices on foreign keys explaining why `CASCADE` or `SET NULL` was chosen
- Import `Base` from `api.db.base` in every model file
- Import `AsyncSessionLocal` from `api.db.session` in route dependencies

## Alembic rules

- Never edit generated migration files unless fixing an obvious autogeneration error
- Never delete migration files
- Always run `alembic revision --autogenerate -m "description"` to generate new migrations
- Always run `alembic upgrade head` to apply migrations
- Migration descriptions must be in plain English describing what tables or columns are affected

## API rules

- All schemas live in `api/schemas/` — one file per domain
- All shared utilities live in `api/lib/`
- All ORM models live in `api/models/` — one file per model
- Database session files live in `api/db/`
- Endpoint functions must be `async`
- Endpoint functions must remain thin — no business logic inside endpoint bodies
- Role strings are always lowercase: `"member"` and `"clinician"`
- Never rename `patient_id` — it is a medical record identifier, not a role name
- Never hardcode secrets or credentials

## ML pipeline rules

- Never consolidate dataset files — one loader per dataset, one preprocessor per dataset, one model per dataset
- WDBC labels must always be flipped — sklearn uses `0=malignant`, this project uses `1=malignant`
- UCTH missing values are `#` — always pass `na_values=["#"]`
- OOD threshold is `3.5` standard deviations — never lower it
- SHAP values must always be indexed with `[0, :, 1]` for the malignant class
- Never use `shap_values[1][0]`
- Always use `TreeExplainer` — never `KernelExplainer`
- Never train or refit anything inside `api/main.py` startup

## Saved model rules

- All 8 artefacts must exist in `ml/saved_models/` before starting the API
- Regenerate artefacts only through `python train.py`
- Never commit `.pkl` files to Git

## Environment rules

- All secrets live in `.env` at the project root
- Never hardcode secrets, tokens, or credentials anywhere
- Always reference `.env.example` when adding new environment variables
- Required variables: `SUPABASE_JWT_SECRET`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`

## Git rules

- Conventional commits always: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`
- Never commit `.env`, `.pkl` files, `.venv/`, `__pycache__/`
- Commit after each meaningful phase

## Working behaviour

- Work one file at a time unless the task explicitly requires multiple files simultaneously
- Never touch files outside the scope of the task
- Never make unsolicited refactoring changes
- Always explain what you are about to do and why before doing it
- After completing a task, state clearly what was done and what the next logical step is
- After completing any task, if the work has not been committed yet, always suggest a conventional commit message covering everything that was done. Never wait to be asked.
- After any task is committed or completed, always check whether any of the following docs need updating and suggest the changes: `docs/rules.md`, `docs/architecture.md`, `docs/api.md`, `docs/ml-pipeline.md`, `docs/database.md`, `docs/plan.md`, `README.md`. Never wait to be asked — flag it proactively after every commit.
- If a task is ambiguous, ask for clarification before proceeding
- If a rule in `docs/rules.md` conflicts with an instruction, follow `docs/rules.md` and flag the conflict
