# Adolat Olympic Club — V2 continuation implementation and acceptance report

**Date:** 14 October 2026  
**Starting point:** supplied `Adolat_Olympic_Club_V2_M1_Development(1).zip`, **M1.1 native TypeScript + FastAPI working checkpoint**.  
**Delivery designation:** post-M1 development continuation, **NOT** V2 general availability, school-data cutover, live-hosted verification, or completed voluntary student pilot.  
**Approved sources:** `docs/planning/OlympiadOS_V2_Master_Blueprint.md` with the approved F25–F28 scope amendment taking precedence. Unchanged session/CSRF, Math/Physics, no-AI and privacy requirements remain active.

## Actual changes in this continuation

| Area | Implemented and tested change | Limits / caveats |
|---|---|---|
| Training Hub spacing / mobile | Refined Codeforces contest card spacing and wrapping, panel inset/footers, compact leaderboard empty state, dark-theme primary-button contrast and enclosed horizontal table scrolling. Private training two-column forms collapse safely on tablets/phones. Hub viewport assertions at **320/360/390/768/1024/1440 px** in **RU and EN**. | Synthetic provider fixtures and test-only browser bridge. Not a real hosted mobile accessibility audit. |
| F12: existing-user invitation | Separate `enrollment_invitations` storage, teacher-owned classroom scoping, email-bound single-use expiring token and authenticated target-user **explicit acceptance**. Unrelated users, wrong account, replay, cross-classroom teacher and revoke tested. Existing new-account invitation stays intact. | No external email sending service; teacher manually shares the protected enrollment link through a school-approved method. |
| F13: safe reuse / drafts | Server-authorized same-classroom activity clone into a new unpublished draft, immutable item snapshots, no historical grades/submissions/rosters copied; versioned **draft metadata** edit with optimistic conflict detection and freeze on publication. Same-classroom problem-set copy creates fresh set/items and never alters original. New UI and RU/EN keys. | Activity clone deliberately excludes competitions; modifying the item list of a created draft is not implemented. Full multi-editor UI conflict comparison still open. |
| F14: teacher review | Staff-only bounded cursor-based review queue with optional status and classroom filters, deterministic tie ordering, server authorization and bilingual frontend filters; feedback publication / sealed competition explanation visible to staff. | Original grade version conflict gate remains; further query-total/projection optimization and comprehensive review preview are open. |
| F23: interruption preflight | Staff-owned session/competition preflight returns server timestamp, release/participation/item/receipt count flags; student denied. **School admin only** may extend a **still-open** session/competition by at most two hours with a minimum-length documented reason, a compare-and-swap original deadline, per-student notice and auditable old/new times. No automatic late reopening; competing staff request conflicts. RU/EN controls. | Not an official school interruption/fairness policy, guarantee of connectivity, or evidence of actual hosted timing/recovery. Operator decision and external contest rules remain authoritative. |
| Recovery | `scripts/recovery.py` provides tested GPG AES-256 encrypted **offline local SQLite + referenced private-local-object** backup, full-manifest/SQLite/object verification, and isolated non-overwriting restore. CLI walkthrough in `docs/RECOVERY-PILOT.md`. | Does **not** support live PostgreSQL / Supabase private Storage, production backup or a full school migration. Cannot satisfy final V2 cutover by itself. |
| Schema | New Alembic revision `d84f103f71aa` **after** retained M1 migration `c16a7f429444`; nullable-free CAS field, enrollment table, bounded review index. Runtime readiness expected revision updated; V1 baseline revision unchanged. | Operator must run migration using approved separate migration credentials; never auto-migrate on runtime startup. Live PostgreSQL DDL/role tests not executed here. |
| Preservation | Existing M1 training, gated circles, Codeforces F25–F28, authorizations, session/CSRF, private Storage adapter and Mathematics/Physics workflows retained. | Existing M1 features are inherited implementation, not newly claimed deployment acceptance. |

## Build, tests, and evidence

- **API/security/schema suite: 147 passed in 40.26 seconds (SQLite)**; see `docs/evidence-continuation/backend-147-passed.log` and the companion `continuation-tests/` output and this source archive's `tests/`. Includes new tests for opt-in classroom invitations, invitation cancellation, copy/draft CAS + non-regression, scoped review queue, GPG backup/verify/restore and unreopenable audited competition extension. `pytest` runs against disposable **SQLite**, with official API and cloud storage **mocked**. The V1/M1 baseline has not been rewritten.
- **TypeScript:** `npm run typecheck` passed and `npm run build` regenerated compiled modules in `static/assets`.
- **Browser: all 12 Informatics V2 bridge tests passed in 36.21 seconds** (`docs/evidence-continuation/informatics-browser-bridge-12-passed.log`). The target Training Hub RU/EN width/no-overflow test passed for 320–1440 px; the F23 preflight/reschedule path passed using **system Chromium through the repository's test-only browser bridge**. Previously supplied M1 evidence covers its own baseline but is not a retest of this continuation.
- **Screenshots:** `docs/screenshots-continuation/` contains browser-rendered *synthetic* images, not a deployed/real-school service. Tests/fixtures explicitly label invented Codeforces contest data.
- **Retained V1 Math/Physics teaching browser tests: all 16 passed in 87.42 seconds**, also through the browser bridge (`docs/evidence-continuation/retained-teaching-browser-bridge-16-passed.log`). This confirms compatibility under the test harness, not native hosted-browser acceptance.
- **Original archive:** preserved unchanged outside this delivery. Historical `CHECKPOINT_MANIFEST_M1.json` tracks the original checkpoint; the current `CHECKPOINT_MANIFEST.json` belongs to the updated delivery.

## Feature traceability: important remaining approved V2 work

**Implemented in retained M1:** F01–F04 scaffolding/protection and storage adapter, F06–F10 independent training/circles/gate/private reflection, F15 pending-submission recovery, portions of F16–F22 and F24, and mandatory F25–F28 branding, optional handle/approval, private opt-in leaderboard and upcoming Codeforces contests. These inherit the technical/operational limitations in the M1.1 status document.

**Added/advanced now:** F12 existing-account consent enrollment, F13 activities/sets copying and draft metadata editing, F14 filtered staff review queue/feedback explanation, F19 Training Hub responsive fixes, F23 preflight/interruption procedure, and a bounded **pilot-local part of F05** (encrypted restore).

**Still incomplete or operationally unverified (do not mark complete):**

1. **F05 P0 cutover:** full typed V1 school-data/attachment importer and verifier, live Supabase PostgreSQL + private Storage **consistent encrypted backup and restore**, school-owned credential/custodian process, rehearsal after V2 writes, reversible signed-off cutover. **Release blocker.**
2. **F11 optional P2:** student-consented recent `user.status` observations attached to selected practice items with full UI/cache/rate-limit flow; intentionally disabled, not misrepresented as finished. F26–F28 remain independent and mandatory.
3. **F13/F14:** full mutable draft problem-set composition/editing and richer per-student release visibility previews/queue totals, staff UX and concurrency tests.
4. **F16/F17/F19:** app-wide query budgets/cursor migration of large V1 lists, cloud load/reconnect/performance measurements, final keyboard/screen-reader/zoom checks and native responsive testing. Bridge screenshots are not WCAG certification.
5. **F20/F21/F22:** broader photo-quality controls, school-approved deletion/retention/backup-expiry handling, training notification preferences and scheduled-on-use reminder dedupe.
6. **F23/F24:** school-approved exception policy, true outage rehearsal with persisted submission receipts, reproducible clean Docker/package build, real restricted runtime-role Postgres checks, Supabase TLS/storage, Render hosting and all security/operational acceptance tests.
7. **M1/Phase 7 human acceptance:** actual moderated 10–12-volunteer Informatics pilot, staff ownership approval and privacy consent, adoption findings and native-browser/real-provider staging sign-off. **Never conducted in this development environment.**

## Acceptance boundary / next operator steps

1. In a throwaway database, run `python -m server.cli init` to upgrade to the new revision (or the approved operator `alembic upgrade head` path); never run this on the only copy of school data. Verify runtime revision `d84f103f71aa` and data-preservation tests.
2. Use the synthetic demo and the current RU/EN UI with student/teacher/admin sessions; confirm classroom invite handoff, draft CAS, review authorization, Training Hub and preflight.
3. Run `python -m pytest -q --ignore=tests/test_browser.py --ignore=tests/test_v2_browser.py`, `npm run typecheck`, `npm run build`; run browser tests in a **real allowed origin** and document any environment limitations. For supplemental CI-like bridge tests: `CHROMIUM_PATH=/usr/bin/chromium BROWSER_BRIDGE=1 python -m pytest tests/test_v2_browser.py -k 'hub_phone or breakpoints or admin_reschedule'`.
4. Demonstrate encrypted pilot-local restore from `docs/RECOVERY-PILOT.md` without modifying the working source. Then build/verify the *separate* PostgreSQL-plus-Storage backup and school-data cutover tooling; do not substitute the local recovery script.
5. Obtain designated school approver, backup custodian, student privacy/consent and moderator approvals; run actual staging/provider tests and school-authorized pilot. **No real students, production URLs, migrations or live services were used for this continuation.**

**Release judgment:** a working development continuation with significant implemented work and regression evidence, **not** the complete approved V2 release. Do not deploy with real student information or cut over V1 until the above required gates are satisfied.
