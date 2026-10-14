# Adolat Olympic Club — V2 implementation continuation

**Post-M1.1 source continuation · English / Русский · 14 October 2026**

**Updated development result:** Training Hub mobile/layout repairs; consent-based existing-user classroom enrollment; safe draft activity editing and set/activity cloning; scoped teacher review queues; guarded staff competition preflight and admin-only audited deadline extensions; GPG-encrypted **local SQLite+private-object pilot** recovery. [Read the honest completion report](docs/V2-CONTINUATION-COMPLETION.md) and [recovery limits](docs/RECOVERY-PILOT.md). This is **not** a final V2 release or real cloud backup.


This is an implemented, runnable **early Informatics milestone checkpoint**, built on the supplied OlympiadOS V1 rather than a replacement application. It includes the real application APIs, database models, incremental migration, native TypeScript screens, compiled assets, school logo derivatives, tests and setup configuration. It is **not the completed full V2 release or an approved real-student pilot**. All later approved features remain in scope; see [implementation status](docs/IMPLEMENTATION_STATUS.md) and [release gates](docs/RELEASE-GATES.md).

## What is available now

**Independent Informatics:** private training goals, external problem queues, self-reported outcomes, assistance/reflection/next-step notes, carry-forward, own-data export; student-organized circles, opt-in membership, local facilitators, scheduled individual/collaborative practice, server-enforced debrief gates, reports and school moderation. Private plans are not visible to facilitators or ordinary administrator views. An eligible student needs neither a teacher/classroom nor a Codeforces account to train.

**Codeforces hub:** voluntary handle association, explicit public-metadata consent, administrator school approval and a separate leaderboard opt-in. School-authenticated ranking includes official current/max rating, rank, update time and profile link; unrated accounts are not assigned invented zero ratings. Upcoming regular contests use official public data, cached timestamps, local countdowns and safe links. Shared server-side throttling, caches and failure states keep training usable when Codeforces is unavailable. There are no embedded sample ratings in production routes. Live API access has not been smoke-tested in this environment.

**Protection and preservation:** release-aware group attachments, current-member submission attribution, newest-first comment pagination, durable uncertain-submission recovery, authenticated streaming file access, storage reservations/reconciliation, RU/EN, both themes, existing mathematics/physics workflows and opaque session authentication. No application AI, code execution, judge, scraping or external passwords.

**Cloud preparation:** Supabase PostgreSQL/private Storage configuration and adapter, restricted-role SQL, fail-closed production entrypoint, one-service Render template, private-schema migrations and disposable-PostgreSQL CI configuration. These are implementation deliverables, **not evidence of a successful hosted deployment**. Full school-data import, verified encrypted backup/restore tooling and actual provider verification remain open.

## Run a synthetic local demonstration

Use a **new directory and database**, never the only copy of a V1 school database. Python 3.13 was used for the recorded tests. Package installation needs access to trusted registries. Compiled JavaScript is included; Node is needed only when rebuilding the frontend.

```sh
python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
export DATA_DIR="$PWD/.data-m1-demo"  # Windows PowerShell: $env:DATA_DIR="$PWD/.data-m1-demo"
export APP_ENV=development
export STORAGE_BACKEND=local
python -m server.cli init
python -m server.cli demo
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000**. `demo` prints a freshly generated shared password for synthetic accounts including `admin@demo.school.test`, `teacher@demo.school.test`, `physics@demo.school.test`, `student@demo.school.test`, `teammate@demo.school.test` and `other@demo.school.test`. No account is created merely by starting the server. Demo seeding is forbidden in production. Use the student account for **My Training**, **Training Circles** and the **Competitive Programming Hub**; use the administrator for **Subject participation**, **Codeforces approvals** and **Moderation**.

For a fresh non-demo install, run `python -m server.cli admin --email ... --name ...` after initialization and follow the school invitation workflow. Do not use that fresh install with real student data until the release gates pass. The application does **not** automatically load `.env` files; export variables or use your approved process manager/secret store.

The synthetic demo has real-looking instructional fixtures but no real students. A Codeforces provider outage should produce an honest unavailable state, not fabricated contests. Automated provider fixtures run only under `tests/`. A safe demonstration script is in [M1-PILOT.md](docs/M1-PILOT.md).

## Build and tests

```sh
python -m pip install -r requirements-dev.txt
npm ci --ignore-scripts
npm run typecheck
npm run build
python -m pytest -q --ignore=tests/test_browser.py --ignore=tests/test_v2_browser.py
python -m playwright install chromium
python -m pytest -q tests/test_browser.py tests/test_v2_browser.py
```

The normal browser command uses real navigation/cookies/fetch/CSP. A supplementary, test-only `BROWSER_BRIDGE=1 CHROMIUM_PATH=/usr/bin/chromium` mode exists for restricted environments. It is **not** equivalent to native-browser acceptance. See [the current test report](docs/TEST_REPORT.md) for actual results and unexecuted checks. The repository's original V1 documentation/evidence is explicitly archived under `docs/v1-reference/`.

## Documentation and handoff

[Implemented vs remaining scope](docs/IMPLEMENTATION_STATUS.md) · [Release blockers](docs/RELEASE-GATES.md) · [Architecture](docs/ARCHITECTURE.md) · [Security/privacy](docs/SECURITY.md) · [Deployment](docs/DEPLOYMENT.md) · [Supabase setup](docs/supabase-setup.md) · [Private Storage](docs/storage-setup.md) · [English guide](docs/GUIDE.en.md) · [Русское руководство](docs/GUIDE.ru.md)

The approved blueprint and overriding scope amendment are preserved under `docs/planning/`. Internal package/database identifiers remain `olympiados` to preserve compatibility; the user-facing product name is **Adolat Olympic Club**. The exact supplied RGB school logo is retained in `static/brand/school-logo-original.png`; derivatives and hashes are recorded in `static/brand/manifest.json`.

**No Supabase project, cloud deployment, real-school-data migration or student adoption pilot has been performed.** Do not treat a local green test suite as production authorization.
