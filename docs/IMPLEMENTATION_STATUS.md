> **Historical M1.1 status only.** Later F12/F13/F14/F19/F23 and offline pilot-local recovery changes are documented in [V2 continuation completion](V2-CONTINUATION-COMPLETION.md). Do not use this file alone as the current implementation ledger.

# V2 implementation status — `2.0.0-m1.1`

Date: 14 October 2026. This document supersedes historical V1 delivery-status claims. The scope amendment takes precedence over the original blueprint. **This is a development checkpoint, not final V2 scope completion.**

## Delivery boundary

The early independent/peer Informatics and mandatory Codeforces workflows are implemented end to end and have deterministic API and supplementary browser tests. The original application structure is preserved. Later approved work is not silently deferred to V3. Actual M1 operational acceptance still requires native-browser/provider/staging checks, protected backup/restore, school authorization and the voluntary student pilot.

### Feature-by-feature traceability

| Feature | Current implementation | Remaining acceptance/work |
|---|---|---|
| F01 release-aware files | Centralized group item/release authorization reused by detail, file and event checks; legitimate immutable-submission attachment access retained; regression tests | Hosted private-object and whole-surface review |
| F02 authorship/offboarding | Transactional current group removal; snapshot filters active enrolled students; historical snapshots preserved; negative tests | Real PostgreSQL removal/submit concurrency tests |
| F03 Supabase PostgreSQL | Private schema/search-path, pool/TLS configuration, frozen V1 baseline plus forward migration, runtime/operator separation SQL, readiness checks, disposable-PG full-suite CI configuration | **Actual PostgreSQL full-suite/role/concurrency and Supabase session-pooler/TLS verification not run** |
| F04 private Storage | Local/Supabase adapter; authorized streaming; exact upload retries, checksums, durable intents, target/user/global quotas, failed-delete reconciliation; mocked tests | **Actual bucket/key/stream/restart checks and real-file migration not run**; further failure/concurrency/load coverage |
| F05 migration/backup/restore | Setup and safety boundaries documented; original source preserved | **Full typed school-data importer, canonical migration verifier, encrypted DB-plus-object backup/restore, backup-status UI and verified restore remain to build**. Do not perform cutover with this checkpoint |
| F06 subject participation | Classroom-independent admin-granted participation; derived enrollment for existing classroom students; subject-aware home/navigation | Full My Work/Spaces navigation consolidation, further onboarding usability and hosted checks |
| F07 private training | Cycle/plan/link queue, status, owner-only CRUD, CAS/idempotent creation, carry-forward provenance, bounded own export | More year-scale/history usability and race tests; pilot validation |
| F08 circles | Student create, safe discovery, consent/join approval, local facilitator roles, transfer consent, leave/remove/archive/lock, limits | Real PG concurrent last-facilitator and creation limits; school moderator sign-off |
| F09 gated discussion | Individual versus collaborative mode; server-time gate for all freeform posts, frozen started guidance/links, competition lock, report/hide | Hosted alternative-surface/security review and real usage validation |
| F10 reflection | Outcome/assistance/reflection/next step; self-report labels, private review/counts/export | Longer history UX and school-approved aggregate pilot measures |
| F11 optional evidence refresh | Separate feature flag remains false; reserved data representation/shared provider adapter | **Recent `user.status` observations workflow/UI not implemented**; flag is not a claim that it works. F26–F28 do not depend on it |
| F12 existing-user enrollment invitations | V1 enrollment preserved; subject derivation added | **New email-bound existing-user invitation redemption not implemented** |
| F13 draft editing/cloning | V1 snapshots/publication semantics preserved | **New same-classroom cloning and safe draft-edit feature not implemented** |
| F14 focused review | Existing manual grading, release/history retained and regression-tested | **New cursor/filter-focused review workflow and visibility preview not implemented** |
| F15 uncertain submission recovery | Exact user/task-scoped pending request persisted in session storage; own receipt lookup; exact retries and editor re-entry recovery; cleared on logout/account switch | Native full-page reload/response-loss and real PG group/deadline race matrix; browser storage is not a backup |
| F16 efficient synchronization | Foreground-only background polling; SSE limited to live screens; shared candidate cache; blocking SQL off event loop; reauthorization and cursor reset | Hosted concurrency/reconnect/query/memory measurements; no achieved SLA claimed |
| F17 pagination/performance | Current group comment window with stable older cursor; new domain lists bounded | **Whole-application library/review/progress query budgets and cursor conversion remain** |
| F18 bilingual | New screens/errors/statuses/notifications/audit actions translated RU/EN; inherited bilingual teaching intact | Final whole-scope localization and school terminology review |
| F19 mobile/accessibility | Responsive new hub/plan/circle views, labels, safe external links, focus patterns, mobile tests, both themes | Complete keyboard/screen-reader/zoom/contrast review, unified navigation refinement; no WCAG certification claimed |
| F20 handwritten upload UX | Photo preview/cancel, explicit JPEG option (PNG preserved by default/for alpha), EXIF orientation/metadata handling, quota/status and same-tab retry | Advanced user-controlled resize/quality and progress UX not complete; no automatic legibility claim |
| F21 moderation/privacy | Reports/resolve/hide/lock and audited admin actions; private own-training export/delete | Full school-approved retention/deletion/backup expiry tooling and broader own-data export; no school policy approval assumed |
| F22 notifications | Generic bilingual circle publication/approval/removal/moderation notifications, no gated body payloads | Reminder preferences, comprehensive deduplication and debrief reminders not complete |
| F23 competition recovery | Server timing/results rules preserved; receipt recovery and existing competition UI | **New teacher preflight/interruption workflow and audited extension policy remain** |
| F24 deployment/operations | Multi-stage Docker, `$PORT`, no startup migration/demo, production schema/security check, config templates, explicit Render Free template, TS lock, PG pin, shared expensive-work admission | **Clean image build, full dependency/security audit, admin operational counters/backups, hosted load/restart/restore and operator handoff remain** |
| F25 branding | Supplied original and resized/padded icons, visible Adolat Olympic Club name, login/nav/title/manifest/docs, RU/EN and both themes | Native favicon/app icon and final visual review; higher-resolution logo optional |
| F26 CF handle/approval | Optional metadata consent, public validation, admin evidence method/time/actor, unique approved canonical handle, reapproval on change, disconnect | Controlled live official API smoke, school approver procedure; no automatic ownership certification |
| F27 school leaderboard | Authenticated, active Informatics + approved + explicit opt-in only; real official snapshot fields, null/unrated handling, deterministic ordering, stale state | Controlled live sync and school privacy/pilot approval |
| F28 upcoming contests | Official regular-contest BEFORE/future filter, nearest five, localized start/duration, browser countdown, shared 20-minute cache and outage fallbacks | Controlled live API, clock/timezone/native-browser checks in target deployment |

## Concrete code map

- Retained: native `frontend/*.ts`, FastAPI `server/routes`, SQLAlchemy models, opaque session/CSRF authentication, original Alembic baseline and assessment semantics.
- New domain: `server/routes/training.py`, `server/schemas_training.py`, `server/services/training.py`, `frontend/pages-training.ts`, `frontend/types-training.ts`.
- Codeforces: `server/routes/codeforces.py`, `server/services/codeforces.py`, `server/services/leases.py`, `frontend/pages-codeforces.ts`.
- Persistence/delivery: `server/services/storage.py`, `uploads.py`, `readiness.py`, `resources.py`, `event_feed.py`, `pagination.py`; file and realtime routes; config/DB/Alembic/startup.
- Migration: `migrations/versions/c16a7f429444_v2_independent_training_codeforces_and_.py`, adding 16 tables plus narrowly scoped existing-table fields. The V1 revision is unchanged.
- Brand: `static/brand/`, `static/manifest.webmanifest`, `scripts/brand-assets.py`.
- New tests: `test_v2_training.py`, `test_v2_codeforces.py`, `test_v2_protective.py`, `test_v2_storage.py`, `test_v2_readiness.py`, `test_v2_browser.py`.

## Next dependency-ordered implementation work

1. Close remaining M1 native browser/real PostgreSQL/provider and security acceptance gaps with synthetic fixtures; repair anything they uncover. Finish the safe pilot-data backup/restore path and obtain school privacy/moderation/custodian approvals **before** a real student pilot.
2. Run the voluntary early Informatics pilot and iterate on measured friction; do not invent adoption results from automated tests.
3. Complete Phase 4 typed data/object migration, canonical verification, encrypted backup/restore and rollback rehearsal; then Phase 5 teaching enhancements F12–F14/F20/F23.
4. Finish cross-cutting query budgets, accessibility, lifecycle/notifications/operations and optional F11; execute whole-app hosted acceptance before a separately authorized reversible cutover.

Unexecuted tests remain open even when configuration files exist. No production school data was supplied, migrated, or deleted in this implementation checkpoint.
