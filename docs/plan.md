## MedSight API Delivery Plan

## 1. Purpose

This plan turns the current backend architecture into a staged delivery sequence. It is grounded in what already exists in the repository and extends it in the order that makes the fewest architectural reversals likely.

## 2. Current Baseline

Already implemented:

- FastAPI application with lifespan startup
- persisted machine learning artefact loading
- member and clinician assessment endpoints
- Supabase JWT verification
- role-based access control
- optional patient_id on ClinicianManualAssessRequest — links to existing patient or creates new one
- weighted multi-model inference
- SHAP explainability for clinician output
- out-of-distribution warnings for UCTH clinical features
- database persistence for clinician assessments
- clinician assessment history (list, detail, soft-delete)
- nested role-based router architecture (Module pattern)

Not yet implemented:

- community endpoints
- notifications
- profile endpoints
- PDF report generation

## 3. Delivery Principles

- keep the API stateless
- keep machine learning artefacts pre-trained and startup-loaded
- avoid changing request contracts without strong need
- add database-backed workflows around the existing prediction core rather than rewriting the prediction core first
- preserve strict separation between API-layer work and machine learning-layer work unless a feature genuinely spans both

## 4. Phase 1: Stabilise the Existing Assessment Core

Goal:
- make the current prediction surface reliable enough to build persistence and product flows around it

Work items:
1. [completed] update `test_api.py` to the live `/member/assess` and `/clinician/assess` routes
2. [completed] adapt API verification to include valid JWT-backed requests
3. [completed] confirm member and clinician payload examples match `api/schemas/assessment.py`
4. [completed] verify blood panel documentation and client payloads do not send a duplicate `age` field
5. [completed] standardise documented response contracts for both assessment routes


Definition of done:

- the live API contract is fully documented and testable
- local verification scripts reflect the actual routes and auth model

## 5. Phase 2: Introduce Database Integration

Goal:

- add persistent storage without disturbing the current inference pipeline

Work items:

1. add Supabase database client configuration to the backend [completed]
2. define environment variables for database access [completed]
3. create the initial `users` table [completed]
4. create the initial `assessments` table [completed]
5. create the initial `notifications` table [completed]
6. put ORM models in place for `users`, `assessments`, and `notifications` [completed]
7. introduce a minimal persistence layer for assessment writes [completed]
8. persist clinician assessment results after successful prediction [completed]
9. decide whether member self-assessments should be stored from the first release or only clinician-submitted records initially

Definition of done:

- successful assessment requests can be written to Supabase
- backend restart does not affect assessment history availability

## 6. Phase 3: Clinician Assessment History

Goal:

- unlock the first database-backed workflow that directly depends on persistence

Work items:

1. add endpoint for listing assessments by clinician [completed]
2. support filtering by patient id, date, and risk level [completed]
3. support retrieval of a single stored assessment detail record [completed]
4. support delete or soft-delete behaviour for obsolete records [completed]
5. shape the returned history payload so it matches the clinician product requirements [completed]

Definition of done:

- clinicians can retrieve, inspect, and remove historical assessments through the API

## 7. Phase 4: Batch Upload for Clinicians
Goal:
- support higher-volume clinician and research workflows

Work items:
1. [completed] define the CSV contract for all supported input columns
2. [completed] create a downloadable template format and document it
3. [completed] add a batch upload endpoint
4. [completed] parse CSV rows into the existing request schema equivalents
5. [completed] run inference row by row using the current ensemble and explainer pipeline
6. [completed] return structured row-level success and failure output
7. [completed] decide whether batch uploads persist each row as a normal assessment record

Definition of done:
- clinicians can submit a CSV and receive machine-readable per-row results


## 8. Phase 5: Profile and Verification Workflows

Goal:

- support user identity and clinician credibility inside the product domain

Work items:

1. [completed] persist profile records in `users` — implemented via the `get_or_create_from_auth_user` upsert pattern called from the clinician assessment pipeline and the `GET /api/users/me` bootstrap endpoint
2. add clinician profile read and update endpoints
3. add member profile endpoints once frontend design is settled
4. add clinician verification submission flow
5. support licence document storage references
6. expose clinician verification badge state to downstream product features

Definition of done:

- clinician and member profiles exist as product records rather than JWT-only runtime identities

## 9. Phase 6: Community API

Goal:

- support the shared awareness and peer-support feed described by the product requirements

Work items:

1. define post and reply persistence model
2. add create post endpoint
3. add create reply endpoint
4. add feed retrieval endpoint
5. include clinician verification badge metadata in feed responses
6. decide whether reactions, reposts, and threads belong in the first implementation or a later iteration

Definition of done:

- members and clinicians can participate in one shared backend-supported feed

## 10. Phase 7: Notifications

Goal:

- deliver account, community, and workflow events to users reliably

Work items:

1. create `notifications` table
2. add notification creation helpers in backend workflows
3. add list notifications endpoint
4. add mark-as-read behaviour
5. integrate Expo Notifications for push delivery where appropriate

Definition of done:

- the backend can persist notifications and expose them to the mobile client

## 11. Phase 8: Report Export

Goal:

- support clinician-facing output beyond on-screen responses

Work items:

1. define the export format for clinician assessment reports
2. create a report generation service from persisted assessment records
3. support PDF generation
4. decide whether reports are generated on demand or stored after creation

Definition of done:

- clinicians can export a formal assessment report from backend data

## 12. Cross-Cutting Workstreams

These workstreams should run alongside the feature phases rather than waiting until the end.

### 12.1 Testing

- keep machine learning verification scripts working after every change
- add database integration tests once persistence exists
- add route-level tests for role enforcement and validation behaviour
- keep endpoint examples in docs aligned with request schemas

### 12.2 Documentation

- update `docs/api.md` whenever route contracts change
- update `docs/database.md` once real table definitions replace proposed ones
- update `docs/architecture.md` when Supabase data access is implemented
- update `README.md` when setup or environment variables change

### 12.3 Security

- never hardcode secrets
- keep `.env` out of version control
- ensure role checks remain explicit at route boundaries
- add database row-level access rules that match API role behaviour

### 12.4 Operational Discipline

- retrain machine learning artefacts only through `train.py`
- never add runtime retraining in API request flow
- keep startup loading deterministic and fail loudly when artefacts are missing

## 13. Suggested Execution Order

Recommended sequence:

1. stabilise tests and contracts
2. implement database integration
3. add clinician history
4. add batch upload
5. add profiles and verification
6. add community
7. add notifications
8. add report export

This order builds around the current strength of the repository: prediction already works, but the product workflows around prediction do not yet persist or scale.

## 14. Risks and Dependencies

### Key dependencies

- Supabase project configuration
- valid JWT role claims from the mobile auth flow
- stable machine learning artefacts in `ml/saved_models/`
- agreed frontend payload contracts for batch upload and profile flows

### Key risks

- database schema drift if persistence is added before contracts are documented clearly
- stale client payloads if schema changes are not synchronised with the `medsight` repository
- growing route bodies if business logic is not extracted as persistence features expand
- outdated verification scripts masking API regressions

## 15. Immediate Next Steps
The next highest-value backend actions are:
1. update local API verification scripts (`test_api.py`) to cover manual and batch assessment flows
2. implement patient profile and verification endpoints

