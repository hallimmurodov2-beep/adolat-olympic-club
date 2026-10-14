# Adolat Olympic Club — checkpoint architecture

## One retained application, two training models

The browser remains strict TypeScript ES modules and hash navigation. FastAPI serves the same-origin JSON API and compiled assets. SQLAlchemy/Alembic, V1 password hashes, database-backed opaque sessions, CSRF/origin checks, manual assessment and immutable activity/submission snapshots are retained. No frontend framework, external authentication system or judge was introduced.

Teacher-owned classrooms/activities/groups/submissions continue to serve Mathematics and Physics. Independent Informatics uses explicit `subject_memberships`, `training_circles`, `circle_members`, `training_cycles`, `training_plans`, `training_items`, `practice_entries`, `peer_posts` and `moderation_reports`. Circle ownership does not confer teacher powers. Plans remain owner-only even inside a circle; shared posts copy only explicitly chosen text. Leaving a circle does not grant access to current circle content through a retained plan.

A cycle is either privately owned or circle-owned, enforced by an XOR constraint. Circle posts require current membership, an open server-side discussion gate and absence of the retained internal-competition restriction. Started individual-cycle instructions and problem links are frozen; all freeform categories, including logistics, share the gate.

## Provider boundaries

Codeforces uses `external_accounts`, `codeforces_profile_cache`, `codeforces_contest_cache` and shared `operation_leases`. All external calls come from the backend to documented public methods on the fixed official host, with a single aggregate throttle, deduplication, failure cooldown and bounded response. Account existence is not ownership: the administrator records an out-of-band evidence method, and ranking requires a second, voluntary publication decision. Minimum public fields only are published inside this single-school deployment. `external_observations` reserves F11's optional later evidence feature, which is not implemented yet.

Supabase PostgreSQL is the production configuration; SQLite is for isolated local review/tests. A dedicated private schema is selected on every database connection, `public` is excluded, and production configuration requires verify-full TLS. The initial session-pooler path is deliberate; a transaction pooler is not interchangeable with session `search_path` settings.

RLS is **backend-oriented**: no browser-role schema grants, explicit limited runtime-role DML and separate operator ownership. `USING(true)` for the backend is not per-student isolation. FastAPI's contextual checks remain the per-user/classroom/circle boundary. This application does not use Supabase Auth and does not send a Supabase browser key.

## Files and failures

Private storage uses a local/Supabase adapter with opaque keys, authorized FastAPI streaming and no public/signed user URLs. `storage_budget` and `upload_intents` serialize quota/target-slot reservations, retain exact retry identity, reauthorize after external I/O, and reconcile failed cleanup. Accepted normalized bytes have hashes. Deleting an object referenced by an immutable submission remains forbidden. A failed delete does not immediately free quota.

User file bytes cannot be kept solely on an ephemeral production disk. Temporary upload/image processing is bounded and uses shared expensive-work admission. A single Python process is the current operating target; provider leases survive process restarts, but multi-worker resource/memory budgets still require testing.

V1 SSE invalidation semantics remain: a bounded shared cache contains only candidate event metadata, and each delivery is reauthorized. Database work is off the async event loop and connections are released before waits. Idle dashboards use foreground polling, and hidden tabs pause. No Supabase Realtime or separate worker was added.

The submission editor stores the exact uncertain request ID/payload per account/task in tab session recovery. An owner-only receipt endpoint distinguishes an accepted attempt from an unsent draft after re-entry. Native full-reload/deadline/group race testing remains a release gate.

## Deployment and schema versions

The original baseline Alembic revision is untouched. Incremental revision `c16a7f429444` adds 16 tables and scoped extensions (48 domain tables total). Production startup checks the expected revision and runtime boundary without running DDL or demo seeding. Docker/Render configuration is supplied but not built/deployed here. The SQLite migration checks are not proof of PostgreSQL execution.

See [implementation status](IMPLEMENTATION_STATUS.md) for incomplete migration/backup, later teaching features and acceptance work. No production data importer, encrypted restore or live cloud environment should be inferred from this architecture description.
