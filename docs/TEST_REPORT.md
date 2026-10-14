> **Historical M1.1 test report.** See [V2 continuation completion](V2-CONTINUATION-COMPLETION.md) for newly executed tests and remaining gates. This report’s original counts are not the updated continuation counts.

# Test report — Adolat Olympic Club `2.0.0-m1.1`

**14 October 2026 · early Informatics development checkpoint · synthetic data only**

This report concerns the delivered V2 working copy, not the original V1 audit. The original V1 report and proof files are retained under `docs/v1-reference/`. This checkpoint does **not** pass the full V2 release gate or the real-student M1 pilot gate merely because the local tests pass. The unexecuted checks below remain explicit blockers.

## Final result ledger

| Check | Recorded result | Evidence and boundary |
|---|---|---|
| Backend/security/domain/storage/readiness/realtime suite | **139 passed, 36.39 s** | `evidence/backend.xml`, `backend.log`. Isolated SQLite; 61 retained baseline cases plus 78 new cases. Codeforces and remote Storage use deterministic mock transports. |
| Combined retained and new browser workflows | **25 passed, 120.73 s** | `evidence/browser-bridge.xml`, `browser.log`. 16 retained V1 cases plus 9 new cases; Chromium through the repository's **test-only browser bridge**, not native navigation. |
| TypeScript strict checks | Passed | `evidence/typecheck.log`; TypeScript 5.8.3. |
| Compiled frontend build | Passed | `evidence/build.log`; generated JavaScript and source maps included. |
| Python syntax/import compilation | Passed | `evidence/python-compilation.log`; behavioral tests remain separate. |
| Forward SQLite schema and preservation rehearsal | Passed | `evidence/sqlite-preservation.json` and `.log`: all 32 original tables' original-column row counts and canonical hashes matched a fresh synthetic V1 source; six subject memberships derived; init repeated twice; FK/integrity checks passed; no Alembic drift. **SQLite to SQLite**, not a PostgreSQL import or a production backup/restore. |
| PostgreSQL offline DDL compilation | Passed | 48 mapped domain tables; 96 DDL statements compiled, **none executed against PostgreSQL**. See `evidence/postgres-offline-ddl.sql`. |
| Original archive and immutable baseline | Preserved | Original ZIP SHA-256 below; frozen V1 Alembic revision compared byte-for-byte with the archive. |
| Official logo master | Preserved exactly | The supplied 181 × 148 RGB image is unchanged; derivative dimensions/hashes are in `static/brand/manifest.json`. |
| Native browser run | **Blocked by environment** | Initial navigation failed with `net::ERR_BLOCKED_BY_ADMINISTRATOR` before reaching the application. `evidence/browser-native-blocked.log`. |
| Real PostgreSQL / Supabase / Docker image / hosted tests | **Not run** | No PostgreSQL server or installed psycopg, Docker, or authorized Supabase/Render environment was available. CI/configuration and adapters are not execution evidence. |
| Live Codeforces or Storage contract smoke | **Not run** | No live metadata/ownership/provider-availability claim follows from mocked tests. |
| Student adoption pilot | **Not conducted** | Screenshots and fixture completions are not student interviews, usage results, or a real school deployment. |

The unique tests are **139 backend plus 25 bridge browser cases**. Focused reruns are not counted again. The latest combined browser run completed without the earlier teardown warning. A final source-branding assertion was separately rerun with the 12 readiness tests; that changes neither suite count nor the native-browser limitation.

## What the added tests cover

The new backend cases exercise owner-only training without a classroom, bounded link queues, private reflection and carry-forward, circle membership/facilitator limits, last-facilitator protection, practice/debrief timing, forbidden pre-gate freeform posts (including “logistics”), competition restrictions, moderation, and retained private-plan ownership after leaving a circle.

Codeforces tests exercise public metadata validation, default-off leaderboard publication, administrator-only school approval, canonical handle conflicts/changes, immediate opt-out, active-subject eligibility, deterministic rating ordering, unrated values, nearest-future contest selection, shared API admission/cache handling and provider failure states. These fixture tests do not certify ownership on Codeforces or prove live network reachability.

Protective tests cover the unreleased group-file path, eligible new submission authorship, historical snapshot preservation, stable recent-comment pagination, own submission-receipt access and exact retry behavior. Private-storage tests cover authenticated reads, exact upload retries, byte verification, reservations, quota/slot failures, failed deletion/reconciliation and authorization loss during an upload. Local tests cannot replace real PostgreSQL locking or real Storage restart/failure verification.

The nine new browser-bridge cases exercise the training loop and private export, circle opt-in and discussion gating, school-admin handle approval and ranking consent, hub/contest presentation, RU/EN, small-screen layout and uncertain-submission recovery on editor re-entry. The retained 16 bridge cases exercise the original teacher/student, mathematics/physics, group, session and competition journeys. The versioned review form no longer remounts on a late general stream-ready event; saving still checks the server version and explicitly refetches state.

## The browser boundary

The normal suite uses real browser navigation, ES modules, cookies, fetch, EventSource and CSP. That initial navigation was denied by the execution environment. The fallback `BROWSER_BRIDGE=1` runs the application's actual rendered DOM and calls local application APIs/database, but substitutes browser transport/storage/module bootstrap. The harness embeds exact public logo image bytes for its originless document. It is test infrastructure, not a production route or a way around the deployment origin policy.

The bridge does **not** validate hosted cookies, true full-page reload, public asset delivery, native favicon behavior, actual CSP/module loading, network reconnection or hosted SSE. Those must be rerun normally on a permitted local/staging origin. Screenshots in `screenshots-m1/` explicitly identify this boundary and use synthetic accounts and mocked contest/rating data. They are not mockups, but neither are they a live school deployment.

## Reproduction

From a disposable working copy with the documented dependencies installed:

```sh
npm run typecheck
npm run build
python -m compileall -q server migrations
python -m pytest -q --ignore=tests/test_browser.py --ignore=tests/test_v2_browser.py \
  --junitxml=backend.xml

# Required normal browser verification; blocked in the recorded environment.
CI=1 CHROMIUM_PATH=/usr/bin/chromium python -m pytest -q \
  tests/test_browser.py tests/test_v2_browser.py

# Supplementary restricted-environment test only.
CI=1 CHROMIUM_PATH=/usr/bin/chromium BROWSER_BRIDGE=1 python -m pytest -q \
  tests/test_browser.py tests/test_v2_browser.py --junitxml=browser-bridge.xml
```

The PostgreSQL CI fixture deliberately requires an explicitly confirmed disposable database and isolates tests in temporary schemas. Never point it at school data. See the CI file and `supabase-setup.md`. Restricted-runtime-role, anonymous-role and live provider permissions still require additional actual staging checks; running tests as a disposable database owner does not establish those policies.

## Environment and dependency limits

Python 3.13.5, Node 22.16.0, TypeScript 5.8.3 and Chromium 144.0.7559.96 were available. Actual installed runtime/test packages are recorded in `evidence/environment.json`. Package-index DNS prevented installing psycopg; the offline npm cache did not contain the required registry response for clean lock generation. Existing compatible installed tools were used for the successful checks.

`package-lock.json` records TypeScript 5.8.3 with its official registry integrity metadata. The PostgreSQL requirement pins psycopg 3.2.13 from official package metadata. **Neither a clean `npm ci`, a clean dependency installation, a Docker build, nor the actual psycopg/PostgreSQL path was demonstrated here.** The failure logs are included rather than treating a declared dependency as tested.

## Preservation and migration interpretation

Original archive SHA-256:

```text
89cfe734b395bc9be5d8a5c9d7cd5e704b9e8969eb6bb72f7d99623ad01c8d5c
```

A separate synthetic preservation probe created a fresh V1 demo from that exact source, copied it consistently into a disposable SQLite target and applied the V2 incremental revision `c16a7f429444`. It compared all original columns for every original table, not just a few sample rows. Some source tables are empty in that demo; their empty checksums do not establish preservation of complex production histories. The report lists per-table counts to make that limitation visible.

This probe is not the approved production importer, attachment-transfer verifier, encrypted backup/restore tool or rollback procedure. Those F05 deliverables remain to build and validate. No actual school database, upload corpus, Supabase project or production deployment was changed.

## Earlier failures and corrections

The companion evidence archive preserves earlier attempts in a separate directory. A combined browser run initially exposed a duplicate session-scoped Playwright fixture; it was consolidated. A retained review case exposed an unsolicited remote refresh of the open grading form; the form now remains stable and relies on its existing version check. A screenshot assertion incorrectly expected an immediately fresh contest response during the legitimate shared Codeforces cooldown; the independent screenshot capture now uses the appropriate already-loaded fixture view without bypassing throttling. A bridge teardown race was also cleaned up. The final combined 25-case run above is the current outcome, not those earlier attempts.

## Remaining release gates

Real PostgreSQL constraints/concurrency and least-privilege roles; Supabase pooler/TLS and private Storage; controlled official Codeforces smoke; clean image/dependency build; native desktop/mobile browser and accessibility checks; hosted cold/warm load/reconnect; typed school-data/object migration and verified encrypted restore; moderation/privacy/backup ownership; real voluntary Informatics pilot; and all later approved feature acceptance remain open. See `IMPLEMENTATION_STATUS.md` for F01–F28 individually and `RELEASE-GATES.md` for conditions before any student data or cutover.
