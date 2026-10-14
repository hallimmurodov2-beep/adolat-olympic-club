# Architecture

## Request and storage boundaries

A single same-origin FastAPI service serves the TypeScript SPA, two translation dictionaries, licensed local rendering libraries, and the authenticated API. Browsers never receive a database credential, storage key, password hash, session token database value, or grading privilege. A closed Pydantic schema rejects unknown mutation fields, including attempted owner/role/score injection.

SQLite/WAL supplies a credential-free local database. SQLAlchemy models and Alembic migrations also target PostgreSQL through psycopg. Use one application worker with SQLite. Persistent private files live below `DATA_DIR/uploads`, outside the static document root. All downloads pass through authenticated authorization checks.

## Data model

`users` and hashed opaque `auth_sessions` define identities. A hashed single-use `invitation` fixes the email, teacher/student role, optional classroom, and expiry before account creation. Administrators are bootstrapped only through the trusted operator command. A student’s subject enrollment is derived from their classroom memberships; no duplicate independent subject-roster state exists.

`subjects → topics` supplies configurable bilingual organization. `classrooms → memberships / announcements / resources / problems / problem_sets` supplies the teacher-owned learning context. Sets are reusable **within the same classroom**; cross-classroom cloning is not implemented.

`activities` unifies assignments, live sessions, and competitions. `activity_items` snapshot statement, translations, examples, protected text, points, rubrics, and the then-existing statement-attachment IDs. Updates to the library do not rewrite these assigned snapshots. Seed data from the migration-era demo has no attachments; ordinary newly created activities freeze their attachment list. Existing snapshot files cannot be removed while referenced by work.

`drafts` hold each student’s current private text and optimistic revision. `submissions` are immutable attempts, with membership snapshots for group submissions and immutable file associations. Grades are versioned separately via `grade_revisions`; student serialization applies the feedback-release gate. No code execution or automatic judge exists.

`groups → group_members / group_documents / document_revisions / group_comments` supplies collaboration. Document writes compare an expected revision in a conditional update. A stale write returns HTTP 409 and the current server version, only after group authorization. The editor preserves the local version, allows comparison/export, and requires an explicit choice before overwriting or restoring. Restoring creates a new revision, not a destructive rollback.

`notifications`, content-free durable `events`, and `audit_logs` support communication and accountability. Progress aggregates actual submissions and manual reviews rather than persisting independent decorative counters.

## Authorization matrix

| Resource | Administrator | Teacher | Student |
| --- | --- | --- | --- |
| Accounts/settings/audit | School-wide management | Own profile; own student invitations | Own profile |
| Classrooms/library | All classrooms | Owned classrooms only | Enrolled classrooms, published/assigned content only |
| Activity controls | All | Owned classrooms | Read eligible/released work; submit only during valid window |
| Draft | No routine draft inspection | No routine draft inspection | Own draft only |
| Submission/grade | All authorized classroom work | Owned classroom work | Own or submission-membership snapshot; only released grades |
| Team workspace | Classroom management | Owned classroom teams | Assigned team; optionally same-class shared read-only view |
| Competition | Manage | Owned classroom competitions | Explicit roster; individual submissions; no group workspace access while active |
| Private file | Its authorized parent or submission | Its authorized parent or submission | Its authorized parent or own submission |

Unauthorized scoped identifiers usually return indistinguishable 404s. Teachers cannot enumerate another teacher’s classroom roster, submissions, or reports. Students cannot supply their group membership or grade. There is **no PostgreSQL RLS policy in this version**: the database is private to the server, and application authorization is centralized in `services/access.py`, backed by relational constraints. A future independent RLS layer would be defense in depth, not an existing feature.

## Real-time and deadline semantics

Every committed relevant mutation writes an invalidation event in the same transaction. `GET /api/events` streams authorized notices through SSE. Notices contain event kind, entity ID, and server time, never solution text or points. Session validity and membership are checked repeatedly; reconnect uses Last-Event-ID. The browser preserves an active editor while refreshing auxiliary state. If SSE is unavailable, it polls every ten seconds. Publication/start/end/release events trigger fresh server-authorized reads.

UTC epoch milliseconds represent all stored timestamps. The school time zone controls display and datetime-local conversion. Countdown clocks derive from server time, but only backend checks authorize writes. A conditional activity-row update checks status, start, and end immediately before accepting a save/submission and serializes it against activity controls. An accepted idempotent submission can be retrieved again after cutoff; a different body with the same idempotency key is rejected. This is replay of an accepted attempt, not a late new submission.

An active eligible competition blocks group access and redacts protected hints/solutions through library, activity, and submission views. It cannot erase material a student already saw or saved outside the platform. Teachers should use fresh unpublished problems and ordinary classroom supervision.

## Internationalization

`locales/en.json` and `locales/ru.json` share keys. Server errors use Babel’s CLDR plural categories; the client uses Intl.PluralRules, Intl.NumberFormat, and Intl.DateTimeFormat. Translation dictionaries are cached locally after load. Language changes persist on the account and rerender the current interface without a page reload or logout. In-flight solutions use the editor recovery mechanism. User-created bilingual content is stored as Unicode JSON with independent `ru`/`en` fields; missing translations receive a visible original-language indicator. Student free-text work, names, filenames, source metadata, and discussion posts are not automatically translated.

The rendering layer escapes text before a small formatting pass. MathJax handles mathematical notation without accepting raw user HTML; Prism highlights Python/C++ text. No remote font, CDN, tracking, or translation service is required.

## API discovery and sources

Development exposes `/api/docs` and `/openapi.json`. Authentication still applies to protected routes. Interactive documentation is disabled in production; the OpenAPI schema itself describes routes but contains no records or credentials.

Framework references: https://fastapi.tiangolo.com/ ; https://docs.sqlalchemy.org/en/20/ ; https://alembic.sqlalchemy.org/ ; https://babel.pocoo.org/en/latest/api/plural.html ; https://docs.mathjax.org/ ; https://prismjs.com/ . These document the underlying libraries, not a certification of this application's security.
