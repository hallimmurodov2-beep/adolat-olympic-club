# Adolat Olympic Club — V2 implementation checkpoint

**Version:** `2.0.0-m1.1`
**Date:** 14 October 2026
**Delivery:** runnable early Informatics development increment, not the final V2 release
**Basis:** the supplied V1 archive, the V2 Master Blueprint and the overriding Approved Scope Amendment

## 1. What was implemented

The application was extended in a separate working copy. The native TypeScript frontend, FastAPI backend, SQLAlchemy/Alembic persistence, existing accounts/session/CSRF protections and teacher-led workflows remain the foundation. The original uploaded archive is unchanged. The supplied school-logo image is retained byte-for-byte as the master; the new application uses **Adolat Olympic Club** as its visible name.

This delivery brings the independent Informatics experience forward as requested. It includes functioning backend routes, database models and migrations, bilingual screens, compiled browser assets, deterministic tests and deployment/setup preparation. It does not claim that later teaching improvements, all production migration tooling, operational M1 acceptance or the full V2 release have been completed.

### School branding

The login/register experience, shell, dashboard/presentation naming, browser title, metadata and application manifest use the school identity. Header, login, favicon and padded app-icon derivatives are included with a reproducible asset script and hash manifest. The original is a small RGB image with an opaque white background: the derivatives preserve proportions and use a deliberate white tile/padding rather than claiming vector quality or a transparent source. The original remains unmodified.

### My Training

An eligible Informatics student can create a private training cycle without a classroom, teacher, circle or external account. The workflow covers a goal, bounded queue of external links, self-reported outcome, assistance used, optional reflection, next step, review and carry-forward. Owner-only access, version checks, idempotent creation, bounded export and private-record deletion are implemented. External links are not fetched as arbitrary server-side previews, and a provider outage does not block manual training.

### Training Circles

Students can create bounded circles, request membership and coordinate scheduled practice with local facilitator permissions. Membership approval, consensual facilitator transfer, leaving/removal, archive/lock, reports and school moderation are implemented. Individual practice and collaborative study have distinct rules. All freeform peer discussion is gated by server time before an individual debrief, including text labeled “logistics”; started guidance and links cannot become an alternate spoiler channel. Circle permissions do not grant access to private plans, teacher grading or global administration.

### Codeforces accounts, school leaderboard and contests

The account flow uses explicit consent for public metadata, optional handle association, school-administrator approval and a **separate default-off ranking opt-in**. A school approval records the method, actor and time; it is not represented as automatic Codeforces verification. Handle changes require review again. Only eligible active students with approved, opted-in accounts enter the school-authenticated leaderboard.

The ranking displays handle, current rating, maximum rating, rank/title when present, last successful update and an official profile link. Ordering is deterministic; unrated accounts do not receive an invented zero. The contest section selects upcoming regular contests and shows name, localized start, duration, countdown and safe official links. The backend shares profile/contest caching and request admission; countdown updates do not contact Codeforces each second. Cached-stale and empty-unavailable states are implemented.

Only fixed official public API methods are used by the adapter. No student Codeforces password, source-code scraping, private API, judge or AI service is involved. **Live provider access was not verified here**; deterministic provider fixtures test successful and failed responses. No fixture ratings or contests are embedded as production fallback data.

### Protective fixes and persistence foundation

The audited unreleased-group attachment gap is fixed using shared release-aware checks while retaining legitimate immutable-submission attachment access. New group submissions exclude ineligible current members without rewriting historical authorship. Group comments now show a recent window and support older-page navigation. Uncertain submissions retain their exact retry identity and can retrieve the owner's accepted receipt.

The checkpoint also includes private-schema PostgreSQL configuration and an incremental Alembic revision, restricted-role/bootstrap SQL, readiness checks, local/private-Supabase Storage adapters, authenticated streaming, upload checksums/intents/quotas and reconciliation. Production configuration rejects SQLite/local-storage fallback. Docker, a one-service Render template, environment templates and operator setup instructions are supplied; no runtime startup migration or automatically seeded production account is introduced.

These are implemented foundations, **not proof of a successful Supabase migration or hosted release**. The complete typed school-data importer, canonical production verifier and encrypted database-plus-object backup/restore tooling still need to be built and validated.

## 2. What was actually tested

| Check | Result | Interpretation |
|---|---|---|
| Backend/security/domain regression | **139 passed** | Isolated SQLite; retained V1 cases and new domain/security/storage tests; external providers mocked. |
| Browser workflows | **25 passed** | 16 retained V1 and 9 new workflows through the repository's supplementary browser bridge. |
| Strict TypeScript and browser build | **Passed** | Compiled assets included. |
| Python compilation | **Passed** | Server and migration modules. |
| Synthetic V1 → V2 SQLite preservation | **Passed** | Original-column counts/hashes for all 32 original tables preserved; repeat initialization and schema drift checks passed. Not PostgreSQL import, real school data or object migration. |
| PostgreSQL offline DDL | **Compiled** | 48 domain tables / 96 statements; not executed on PostgreSQL. |
| Native browser navigation | **Environment-blocked** | Initial navigation denied before reaching the app. |
| Supabase, live Codeforces, real PostgreSQL, Docker/hosted load, student pilot | **Not verified/conducted** | Remain explicit acceptance work. |

The browser bridge exercises real rendered application UI and local APIs but substitutes transport/storage/bootstrap. It does not establish native cookie, CSP, ES-module delivery, full reload, favicon or hosted streaming correctness. Actual interface screenshots are included and clearly labeled **synthetic bridge captures**; their sample contests/ratings are not live Codeforces facts.

Existing compatible installed tools ran the successful checks. Registry/DNS restrictions prevented a clean PostgreSQL driver installation and clean offline npm setup, so declared dependency pins and build configurations must still be validated in a clean environment. Full logs, machine-readable test reports, versions, preservation hashes and earlier development attempts are in the companion evidence archive. The latest passing runs are distinguished from earlier corrected failures.

## 3. What remains in the approved V2 scope

`docs/IMPLEMENTATION_STATUS.md` maps every F01–F28 requirement to implementation and remaining acceptance. No included requirement is silently reassigned to V3.

Before a real Informatics pilot: validate native browsers and actual PostgreSQL/provider permissions, close remaining security/concurrency issues, implement and test pilot-data backup/restore, and establish school privacy, moderation and backup ownership. Then run the voluntary early pilot and measure actual usefulness rather than treating automated fixture completion as adoption evidence.

Subsequent mandatory work includes full school-data/object migration and verified encrypted recovery; existing-user classroom enrollment invitations; safe draft editing and same-classroom cloning; focused review improvements; remaining handwriting/competition readiness workflows; broader list/query optimization; complete accessibility, notifications, retention and operational controls; and the optional bounded submission-observation feature F11. F11 is not implemented merely because a default-off flag/schema exists. The mandatory account, leaderboard and contest features F26–F28 are implemented separately and do not depend on F11.

Final production acceptance still requires a clean image build, hosted permissions/restart/load testing, verified real-data reconciliation and restore, completed remaining features, school sign-off and an approved reversible cutover. **Do not migrate actual school records into this checkpoint.**

## 4. Run a synthetic local demonstration

Extract the source archive and enter `adolat-olympic-club-v2-m1/`. Use a fresh data directory and Python 3.13 with trusted package-index access. Compiled JavaScript is included.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export DATA_DIR="$PWD/.data-m1-demo"
export APP_ENV=development
export STORAGE_BACKEND=local
python -m server.cli init
python -m server.cli demo
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000`. The demo command prints a freshly generated password for synthetic accounts. Use `student@demo.school.test` for training/circles/hub and `admin@demo.school.test` for subject participation, school approval and moderation. No demo account is created on ordinary startup, and demo seeding is forbidden in production. Do not reuse the only copy of a V1 database for this demonstration. See `README.md` for platform notes; `.env` templates are not automatically loaded.

## 5. Package contents and preservation

The source archive includes the modified application, compiled assets, migration, tests, exact logo and derivatives, updated RU/EN guides, setup configuration, actual synthetic screenshots, current test evidence and the supplied planning documents. Historical V1 documentation/screenshots are clearly separated from current evidence. No real student records, provider credentials, local session files, databases or font files are bundled.

Original V1 archive SHA-256:

```text
89cfe734b395bc9be5d8a5c9d7cd5e704b9e8969eb6bb72f7d99623ad01c8d5c
```

The original archive, frozen V1 Alembic baseline and supplied logo master were preserved. No cloud project was created, no application was deployed and no student-data migration or actual student pilot occurred. This delivery is ready for a **synthetic local review and continued V2 engineering**, not for production cutover.
