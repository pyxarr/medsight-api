## MedSight API Database Architecture

## 1. Current State

The current `medsight-api` codebase does not yet read from or write to a database. There are no database clients, no repository layer, no persistence models, and no SQL migrations in the repository at this stage.

What exists today is the authentication boundary for a database-backed system:

- the mobile client authenticates with Supabase
- the backend verifies Supabase-issued JWTs
- user identity and role information are extracted from the token

This means database architecture must be described in two parts:

1. the present implementation boundary
2. the target persistence model the backend is designed to grow into

## 2. Architectural Position of the Database

The backend is designed to remain stateless at the application layer.

- request-scoped data lives in request bodies
- machine learning runtime state lives in memory after startup loading
- durable business state belongs in Supabase PostgreSQL

This separation matters because the API process may restart at any time without losing product data. Trained machine learning artefacts are filesystem-based deployment assets, not user-generated records. Everything user-facing and persistent should eventually be stored in the database.

## 3. Why Supabase

Supabase is the chosen persistence platform for two linked reasons:

1. it provides authentication for the mobile client
2. it provides PostgreSQL storage under the same platform boundary

The broader project requirement is data sovereignty. Medical and user data must remain in the product's own database rather than being fragmented across external identity platforms and separate third-party data silos.

## 4. What the Backend Knows About Users Today

The backend currently reconstructs a minimal authenticated user object from the JWT in `api/lib/auth.py`.

Current runtime user shape:

```python
CurrentUser(
    id: str,
    email: str,
    role: str,
)
```

JWT claim mapping:

- `sub` -> user id
- `email` -> email
- `user_metadata.role` -> role

This is not persisted by the backend today. It is only used for request authorisation.

## 5. Persistence Domains Planned for the Product

Based on the existing product and architecture documents, the backend is expected to persist at least five domains.

### 5.1 Users

The database will need to store application-level user records beyond the basic identity data inside Supabase Auth.

Likely responsibilities:

- role-aware profile data
- verification state for clinicians
- display metadata for community features
- links between auth identity and product records

### 5.2 Assessments

Assessment persistence is central to the clinician workflow.

Likely responsibilities:

- storing each submitted assessment request
- storing the machine learning output returned at assessment time
- allowing clinicians to view assessment history
- enabling deletion or archival of past assessments
- supporting later PDF report generation and export

### 5.3 Notifications

Notifications are planned for product workflows such as:

- clinician verification updates
- assessment follow-up reminders
- community interaction alerts
- push notification delivery state

### 5.4 Community

If community features are stored in Supabase, the database will also need records for:

- posts
- replies
- reactions or interaction primitives
- moderation state
- clinician verification badge display data

### 5.5 Audit and Safety Data

Because the product deals with clinical decision support, the backend will likely need a clear record of:

- who submitted an assessment
- when it was submitted
- what inputs were used
- what result bundle was produced
- whether an out-of-distribution warning was raised

This matters for traceability and safety review even if it is not yet implemented.

## 6. Proposed Core Tables

The following tables are the minimum practical database shape implied by the existing product requirements.

### 6.1 `users`

Purpose:

- product-level user profile data keyed to Supabase auth identity

Suggested columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Matches Supabase auth user id where possible |
| `email` | `text` | Cached application email |
| `role` | `text` | `member` or `clinician` |
| `display_name` | `text` | Public-facing name |
| `username` | `text` | Unique public handle |
| `avatar_url` | `text` | Optional profile image |
| `institution` | `text` | Clinician-only professional context |
| `specialisation` | `text` | Clinician-only field |
| `experience_years` | `integer` | Clinician-only field |
| `location` | `text` | Region or institution location |
| `medical_licence_number` | `text` | Clinician verification data |
| `licence_document_url` | `text` | Stored file reference |
| `is_verified` | `boolean` | Clinician verification badge state |
| `created_at` | `timestamp with time zone` | Record creation time |
| `updated_at` | `timestamp with time zone` | Last update time |

### 6.2 `assessments`

Purpose:

- persist completed assessment requests and responses for history and retrieval

Suggested columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Internal assessment identifier |
| `clinician_user_id` | `uuid` | Nullable for member self-assessments |
| `member_user_id` | `uuid` | Nullable if not linked to a registered member profile |
| `patient_id` | `text` | Domain identifier from the request payload |
| `assessment_role` | `text` | `member` or `clinician` submission context |
| `clinical_data` | `jsonb` | Raw submitted clinical fields |
| `biopsy_data` | `jsonb` | Nullable raw biopsy input |
| `blood_panel_data` | `jsonb` | Nullable raw blood biomarker input |
| `risk_score` | `numeric` | Final ensemble score |
| `risk_level` | `text` | `Low`, `Medium`, or `High` |
| `confidence_percent` | `integer` | Rounded confidence output |
| `agreement` | `text` | Ensemble agreement label |
| `models_used` | `integer` | Number of contributing models |
| `individual_scores` | `jsonb` | Per-dataset probabilities |
| `clinical_guidance` | `text` | Guidance returned by the ensemble |
| `key_risk_drivers` | `jsonb` | SHAP output persisted as returned |
| `ood_warning` | `jsonb` | Out-of-distribution result bundle |
| `created_at` | `timestamp with time zone` | Assessment timestamp |
| `deleted_at` | `timestamp with time zone` | Nullable soft-delete support |

Why `jsonb` fits here:

- assessment inputs and outputs are structured but nested
- the machine learning response shape may evolve over time
- storing a faithful copy of the submitted and returned payloads improves traceability

### 6.3 `notifications`

Purpose:

- persist system-generated user notifications

Suggested columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Notification identifier |
| `user_id` | `uuid` | Recipient |
| `type` | `text` | Notification category |
| `title` | `text` | Short user-facing heading |
| `body` | `text` | Detailed message |
| `is_read` | `boolean` | Read status |
| `metadata` | `jsonb` | Optional structured context |
| `created_at` | `timestamp with time zone` | Delivery creation time |

## 7. Proposed Supporting Tables

The planned product surface implies several supporting tables even though they are not yet required by the running backend.

### 7.1 `community_posts`

Purpose:

- shared feed items posted by members and clinicians

Suggested columns:

- `id`
- `author_user_id`
- `content`
- `parent_post_id` for replies
- `created_at`
- `updated_at`
- `deleted_at`

### 7.2 `community_reactions`

Purpose:

- interaction tracking if likes or similar mechanics are introduced

### 7.3 `assessment_files`

Purpose:

- file references for batch uploads, generated reports, or clinician attachments

### 7.4 `verification_requests`

Purpose:

- store clinician verification submissions and review state separately if the workflow becomes more complex than a boolean profile flag

## 8. Relationship Model

The target relationship shape is straightforward.

```text
users
  ├── one-to-many assessments
  ├── one-to-many notifications
  └── one-to-many community_posts

community_posts
  └── self-referencing parent_post_id for reply threads

assessments
  └── optional links to member and clinician users
```

This keeps the machine learning result record central while allowing product features to grow around it.

## 9. Database Responsibilities by Feature

### 9.1 Member Assessment

If persisted, a member self-assessment should store:

- member identity if logged in
- patient identifier from the payload
- clinical input
- final output summary
- out-of-distribution warnings

### 9.2 Clinician Assessment

If persisted, a clinician assessment should store:

- clinician identity
- patient identifier
- clinical input
- optional biopsy input
- optional blood panel input
- ensemble scores and model agreement
- SHAP driver output
- out-of-distribution warnings

### 9.3 Assessment History

The clinician history feature will depend on the database being able to filter and sort by:

- clinician user id
- patient id
- date
- risk level
- risk score
- confidence percent

That means indexes will eventually matter.

## 10. Suggested Indexes

When persistence is added, these indexes will likely be required early.

### `users`

- unique index on `email`
- unique index on `username`
- index on `role`
- index on `is_verified`

### `assessments`

- index on `clinician_user_id`
- index on `member_user_id`
- index on `patient_id`
- index on `created_at`
- index on `risk_level`
- partial index on `deleted_at is null` if soft deletion is used heavily

### `notifications`

- index on `user_id`
- index on `is_read`
- index on `created_at`

## 11. Access Control Considerations

The repository already enforces role-based route access at the API layer. When database integration is added, the same role model must carry through to row-level data access.

Expected access model:

- members can access only their own user-facing records
- clinicians can access only the assessment records they created or are authorised to review
- verification fields should only be writable through controlled backend flows
- administrative moderation or review capabilities, if added later, should not reuse member or clinician roles implicitly

If Supabase Row Level Security is adopted, those policies must mirror the API's role rules rather than contradict them.

## 12. Data Retention and Safety Considerations

Because the product handles breast cancer risk assessment data, the persistence model should preserve clinical traceability.

Important principles:

- preserve the exact assessment output shown to the user at the time of submission
- avoid recomputing historical reports on read unless explicitly required
- keep a record of out-of-distribution warnings because they are part of the safety context
- distinguish clearly between auth identity data and product profile data
- treat uploaded verification documents and future batch files as controlled assets rather than loose attachments

## 13. What Is Not in the Codebase Yet

The following do not currently exist in `medsight-api`:

- repository or service layer for persistence
- assessment storage on successful prediction
- retrieval endpoints for historical records
- notification storage and delivery

This document is therefore partly architectural target state and partly implementation boundary record.

## 14. Recommended Integration Order

When database work begins, the most sensible order is:

1. introduce a Supabase database access layer
2. create `users` and `assessments` tables
3. persist clinician assessment results first
4. add history retrieval for clinicians
5. add member-linked assessment persistence where appropriate
6. introduce `notifications`
7. expand into community tables and related endpoints

This sequence aligns with the current backend, where assessment generation already exists but persistence does not.
