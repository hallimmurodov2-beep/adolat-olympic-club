# Release gates — no real-student rollout from this checkpoint alone

The implementation is suitable for **local review with synthetic data**. A passing browser bridge is not a native-hosted-browser pass. A forward Alembic migration and Storage adapter are not a verified school-data migration.

## Before a real-student M1 pilot

- [ ] Appoint the school privacy owner, adult moderator, Codeforces ownership approver, backup custodian and successor; approve data region, notices/consent, retention and incident route.
- [ ] Run normal browser tests without `BROWSER_BRIDGE`, including cookies, CSRF, CSP, ES modules, file downloads, actual page reload and SSE. Verify supported desktop and mobile browser engines.
- [ ] Run the full backend suite and genuine multi-transaction races on disposable PostgreSQL; execute restricted-role SQL and directly prove DDL/browser-role denial. Current CI configuration has **not** been executed here.
- [ ] Verify actual Supabase session-pooler TLS, private schema/roles, bucket privacy and server-key behavior. Confirm unrelated/removed users cannot fetch files or private plans.
- [ ] Complete and **restore-test** a protected pilot database-plus-object backup path; identify who performs it and how missed backups are detected. The full F05 tooling is not included as complete in this checkpoint.
- [ ] Run a controlled, authorized official Codeforces API smoke; verify cache/throttle/timestamp/failure behavior from the selected host. An upstream outage must not disable My Training or Circles.
- [ ] Measure startup, ordinary interactions, hash/image memory, database connections and expected cohort load. Narrow the supported pilot load if necessary; do not invent a free-host SLA.
- [ ] Demonstrate independent training, circle debrief integrity, ownership approval, opt-in withdrawal, moderation and school-account disable/recovery operationally with synthetic accounts.

Only then invite a small voluntary cohort. The planned 10–12 students/four weeks are **targets**, not participants or results already observed. A demonstration using synthetic data is not a student adoption study.

## Additional final V2 release blockers

- [ ] Complete every remaining approved F01–F28 contract or obtain a separate explicit scope amendment. This checkpoint does not defer required teaching enhancements to V3.
- [ ] Inventory the real V1 source DB/uploads from a school-approved frozen backup; validate foreign keys, all authoritative row counts/canonical hashes and every file checksum. Preserve IDs, hashes, snapshots and histories; invalidate cutover sessions/invitations deliberately.
- [ ] Execute and verify a clean database **and object** restore; demonstrate successor-operator recovery. No silent stale-SQLite fallback after V2 accepts writes.
- [ ] Rehearse rollback before/after opening writes, retained-object accounting and interrupted uploads/submissions on the actual infrastructure.
- [ ] Complete keyboard, screen-reader, 320px/zoom/contrast and full RU/EN acceptance across all approved workflows; retain Mathematics/Physics regression.
- [ ] Finish current dependency/security/license review and reproducible clean Docker build, secret scan and intended proxy/header configuration.
- [ ] Obtain school sign-off on pilot findings, best-effort hosting constraints, backup responsibilities, supported cohort and final cutover.

Any unresolved disclosure, lost acknowledged work, migration mismatch, missing verified restore or exposed credential blocks rollout. Do not downgrade a not-run gate to a documentation footnote and call the release complete.
