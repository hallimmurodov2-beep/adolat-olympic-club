# Verification report

## Executed results

| Check | Result | Evidence |
| --- | --- | --- |
| Backend, authorization, workflows, localization, migrations, native HTTP/SSE | **61 passed, 0 failed, 0 skipped** | `test-results-api.xml` |
| Multi-user browser workflows, Russian and English | **16 passed, 0 failed, 0 skipped** | `test-results-browser.xml` |
| Strict TypeScript analysis and browser build | **Passed** | `tsc --noEmit` and `tsc`; compiled modules in `static/assets/` |
| Python module compilation | **Passed** | `python -m compileall -q server` |
| SQLite migration upgrade/downgrade/re-upgrade and model parity | **Passed** | Automated migration test using an empty temporary database |
| PostgreSQL migration dialect compilation | **Passed offline only** | `schema.postgresql.sql`; no PostgreSQL connection was made |

The passing test results above are the final regression runs after correcting defects found during implementation. They are not counts of unexecuted test definitions. JUnit files contain the individual cases and execution metadata. There is no claim of exhaustive coverage or an independent security audit.

## Backend scenarios covered

Unauthorized and unrelated-classroom access; self-promotion attempts and closed input schemas; fixed invitation role and single-use redemption; CSRF and hostile origins; private session cookies/cache headers; password change and account revocation; private student grades, submissions, files, and team documents; MIME/size/image validation; event recipient filtering; persistent drafts and stale revisions; immutable attempts and idempotent submission receipts; rubric bounds/sums and review-version conflicts; explicit feedback release; live problem release, help requests, and ending sessions; group document history and saved-server-snapshot submission; actual simultaneous group saves; server-side submission/draft cutoffs; competition eligibility, hint/solution/collaboration restrictions, and publication gates; bilingual search and frozen problem snapshots/attachment lists; source-code storage without execution; dictionary parity, literal keys, validation translations, and Russian plural categories; migration/schema roundtrip.

Native HTTP/SSE tests additionally check Last-Event-ID replay/reconnection, private event filtering, content-free change messages, and expiration of an open stream after logout. Those tests do not use the browser transport adapter.

## Browser scenarios covered

Each of these eight scenarios runs in **both Russian and English** with separate user sessions and an actual local API/database:

1. Student autosave and submission; teacher rubric grading and feedback release; student score/feedback and mathematical rendering.
2. Teacher problem creation and attachment upload; assignment creation/publication; private invitation and student registration.
3. Teacher starts a live session and releases a problem; student page updates without navigation/manual refresh; assistance request and resolution; ending disables submission.
4. Two teammates edit simultaneously; stale save conflicts without overwriting the local copy; explicit conflict resolution, discussion, and shared final submission.
5. Mobile layout, theme switching, in-app locale switching, and explicit menu dismissal.
6. Essential student/teacher routes and administrator settings render without application or missing-translation errors.
7. Individual competition UI, saved draft and submission, real server cutoff, withheld review, and teacher results publication.
8. A deliberately injected transport failure preserves the student's text; actual retry after reconnection saves it in the database.

## Execution boundary

The sandbox's Chromium has a managed navigation block. Executed browser tests therefore used the **test-only DOM/HTTP/SSE bridge**, not native page navigation. The real application modules, CSS, MathJax, and Prism render in Chromium. Requests are forwarded to a real local Uvicorn server through httpx; event streams carry real persisted server events. Separate clients retain separate authenticated sessions. No API data, grades, assignments, or live updates are fabricated by the harness. The network-recovery test deliberately rejects one class of outbound draft requests to simulate a fault, then restores real transport.

The bridge is never served by the application and does not alter browser policy. It cannot validate browser-native cookies/CSP/network reconnection, file-download behavior, or fullscreen permission behavior. Run the default Playwright mode against the deployed environment for those checks. Safari, Firefox, real mobile hardware, screen readers, load tests, TLS/proxy behavior, antivirus, penetration tests, and a PostgreSQL runtime were not exercised here.

The workflow file under `.github/workflows/ci.yml` is supplied for later use, including a PostgreSQL migration smoke job. **No remote CI run has been claimed or performed.**

## Reproduce

```sh
pip install -r requirements-dev.txt
npm install --ignore-scripts
npm run typecheck
npm run build
python -m compileall -q server
python -m pytest -q tests/test_security.py tests/test_workflows.py tests/test_i18n_and_schema.py tests/test_realtime.py
python -m playwright install chromium
python -m pytest -q tests/test_browser.py
```

Only for a navigation-restricted sandbox with the supplied Chromium executable:

```sh
BROWSER_BRIDGE=1 CHROMIUM_PATH=/usr/bin/chromium python -m pytest -q tests/test_browser.py
```

Tests use temporary databases created by Alembic and a clearly identified test-only demo password. They do not modify a real school's database. Dependency installation requires registry access; the already-installed dependencies were used for this environment's runs.

## Clean archive check

See `release-check.txt` for the independent clean-directory validation of the packaged source. This check uses a newly initialized database and freshly generated demo password, not the development workspace. It is not a fresh operating-system installation or a test of downloading packages from a registry.
