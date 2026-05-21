## MedSight API Database Architecture

## 1. Current State
The `medsight-api` codebase includes a database access layer and persistence for clinician assessments, patient identity, batch sessions, and community features. The repository layer, persistence models, and associated SQL migrations are implemented.

What exists today:
- a Supabase PostgreSQL connection via SQLAlchemy (asyncpg)
- a repository layer for assessment, patient, batch, and community CRUD operations
- automatic persistence of clinician assessment results
- patient identity management with `P-YYYY-SEQ` generation
- batch session tracking for CSV uploads
- retrieval and soft-deletion endpoints for clinician assessment history
- community posts, replies, reactions, and follows with paginated feeds
- authentication boundary verified via Supabase JWTs


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

The backend reconstructs a minimal authenticated user object from the JWT in `api/lib/auth.py` and persists a corresponding product-level record in the `users` table via an "upsert on first request" pattern, triggered during profile retrieval or clinician assessment submissions (manual or batch).

## 5. Persistence Domains Planned for the Product

Based on the existing product and architecture documents, the backend is expected to persist at least five domains.

### 5.1 Users

The database stores application-level user records in the `users` table, which holds product-level profile data separate from the identity data stored in Supabase Auth. A row is created automatically on the user's first authenticated request (e.g., during manual or batch assessment submission or profile retrieval) via the `UserRepository.get_or_create_from_auth_user` upsert pattern.

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

### 5.4 Community (Implemented)

The community feature stores posts, replies, reactions, and follow relationships. Posts and replies share the same `community_posts` table via a self-referencing foreign key. Reactions are tracked per user per post per type with a unique constraint preventing duplicates. Follow relationships link pairs of users with a unique constraint preventing duplicate follows.

Implemented responsibilities:

- posts and replies via self-referencing `parent_post_id`
- reaction tracking (like, repost, bookmark) with toggle semantics
- follow/unfollow relationships between users
- soft deletion of posts
- view count tracking
- paginated feed and following feed queries
- bookmark retrieval
- keyword search across posts and users

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

### 6.1 `patients` (Implemented)
Purpose:
- manage patient identity as a stable anchor for all assessment records
- generate medical record identifiers in the `P-YYYY-SEQ` format

Suggested columns:
| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key (Supabase gen_random_uuid) |
| `patient_id` | `text` | Immutable medical record ID (e.g., P-2024-001) |
| `first_name` | `text` | Patient given name |
| `last_name` | `text` | Patient family name |
| `created_at` | `timestamp with time zone` | Record creation time |

### 6.2 `batches` (Implemented)
Purpose:
- group multiple assessments from a single CSV upload session
- track storage paths for audit and reprocessing

Suggested columns:
| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key (Supabase gen_random_uuid) |
| `clinician_user_id` | `uuid` | Clinician who performed the upload |
| `filename` | `text` | Original name of the uploaded CSV |
| `file_path` | `text` | Path to the file in Supabase Storage |
| `total_records` | `integer` | Total number of rows in the CSV |
| `created_at` | `timestamp with time zone` | Upload timestamp |

### 6.3 `assessments` (Implemented)
Purpose:
- persist completed assessment requests and responses for history and retrieval


Suggested columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Internal assessment identifier (server_default=gen_random_uuid()) |
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

## 7. Implemented Supporting Tables

### 7.1 `community_posts` (Implemented)

Purpose:

- shared feed items posted by members and clinicians
- replies to posts via self-referencing `parent_post_id`

Columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key (server_default=gen_random_uuid()) |
| `author_user_id` | `uuid` | Foreign key to `users.id`, ondelete=CASCADE |
| `content` | `text` | Post or reply text, not nullable |
| `image_url` | `text` | Nullable Supabase Storage URL for attached images |
| `parent_post_id` | `uuid` | Nullable self-reference to `community_posts.id`, ondelete=CASCADE |
| `view_count` | `integer` | Default 0, incremented on post view |
| `created_at` | `timestamp with time zone` | server_default=now() |
| `deleted_at` | `timestamp with time zone` | Nullable soft-delete support |

Design decisions:

- `parent_post_id` uses CASCADE delete because replies are meaningless without their parent post
- `author_user_id` uses CASCADE delete because posts are owned by their author
- `view_count` has a server-side default so the database maintains the counter even for direct SQL inserts

### 7.2 `community_reactions` (Implemented)

Purpose:

- interaction tracking for likes, reposts, and bookmarks
- one row per user per post per reaction type

Columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key (server_default=gen_random_uuid()) |
| `post_id` | `uuid` | Foreign key to `community_posts.id`, ondelete=CASCADE |
| `user_id` | `uuid` | Foreign key to `users.id`, ondelete=CASCADE |
| `reaction_type` | `text` | Valid values: `like`, `repost`, `bookmark` |
| `created_at` | `timestamp with time zone` | server_default=now() |

Constraints:

- unique constraint on (`post_id`, `user_id`, `reaction_type`) prevents duplicate reactions

Design decisions:

- both foreign keys use CASCADE delete because reactions have no meaning without the post or user
- reaction type is stored as text rather than an enum to allow future extension without schema changes

### 7.3 `follows` (Implemented)

Purpose:

- follower-following relationships between users

Columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key (server_default=gen_random_uuid()) |
| `follower_id` | `uuid` | Foreign key to `users.id`, ondelete=CASCADE |
| `following_id` | `uuid` | Foreign key to `users.id`, ondelete=CASCADE |
| `created_at` | `timestamp with time zone` | server_default=now() |

Constraints:

- unique constraint on (`follower_id`, `following_id`) prevents duplicate follows

Design decisions:

- both foreign keys use CASCADE delete so the relationship is removed when either user account is deleted

### 7.4 `assessment_files`

Purpose:

- file references for batch uploads, generated reports, or clinician attachments

### 7.5 `verification_requests`

Purpose:

- store clinician verification submissions and review state separately if the workflow becomes more complex than a boolean profile flag

## 8. Relationship Model

The target relationship shape is straightforward.

```text
users
  ├── one-to-many patients
  ├── one-to-many batches
  ├── one-to-many notifications
  ├── one-to-many community_posts (as author)
  ├── one-to-many community_reactions
  ├── one-to-many follows (as follower)
  └── one-to-many follows (as following)

patients
  └── one-to-many assessments

batches
  └── one-to-many assessments

community_posts
  ├── self-referencing parent_post_id for reply threads
  └── one-to-many community_reactions
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

### `community_posts`

- index on `author_user_id`
- index on `parent_post_id`
- index on `created_at`
- partial index on `deleted_at is null` for active post queries
- composite index on (`parent_post_id`, `created_at`) for reply ordering

### `community_reactions`

- index on `post_id`
- index on `user_id`
- composite index on (`post_id`, `reaction_type`) for reaction count queries
- composite index on (`user_id`, `reaction_type`) for bookmark retrieval

### `follows`

- composite index on (`follower_id`, `following_id`) for follow lookups
- index on `follower_id` for following feed queries
- index on `following_id` for follower list queries

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

- notification storage and delivery
- application-level user profile management (the `users` table exists but is not yet actively managed by the API beyond the upsert-on-first-request pattern)
- assessment file references
- clinician verification request workflows

This document is therefore partly architectural target state and partly implementation boundary record.

## 14. Recommended Integration Order

When database work begins, the most sensible order is:

1. [completed] introduce a Supabase database access layer
2. [completed] create `users`, `patients`, and `batches` tables
3. [completed] persist clinician assessment results first
4. [completed] add history retrieval for clinicians
5. [completed] implement clinician batch upload flow
6. add member-linked assessment persistence where appropriate
7. [completed] implement community tables and related endpoints
8. introduce `notifications`

This sequence aligns with the current backend, where assessment generation already exists but persistence does not.
