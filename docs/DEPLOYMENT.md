# Deployment and local review — V2 checkpoint

**No image was built and no hosting account was provisioned in this environment.** Supabase/PostgreSQL/native-browser/restore gates remain open. The supported action now is local synthetic review; the files below prepare later authorized staging rather than authorize school rollout.

## Local SQLite review

Follow the fresh `DATA_DIR` instructions in the README. `scripts/run-local.sh` explicitly runs operator initialization and then binds to loopback; use it only for a disposable local workspace, not a production launcher. `server.cli demo` is always an explicit action and is disabled under `APP_ENV=production`. The application does not automatically read `.env`.

The local DB and uploads persist in the chosen directory. Do not delete or overwrite an existing school workspace. Keep it out of source archives. Tests create isolated synthetic fixtures and do not use the default workspace.

## Optional disposable PostgreSQL Compose demonstration

`compose.yaml` is **development-only**: private Docker-network PostgreSQL, local upload volume, loopback HTTP, and a database owner used for local initialization. This is not the restricted Supabase production identity. It has not been executed here because Docker/PostgreSQL were unavailable.

Use two new, different random hexadecimal secrets in your terminal. Hexadecimal avoids URL-encoding ambiguity in this development template; real Supabase passwords must be correctly percent-encoded.

```sh
export POSTGRES_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(24))')"
export APP_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
docker compose build
docker compose up -d database
docker compose exec database psql -U olympiados -d olympiados -v ON_ERROR_STOP=1 \
  -c 'CREATE SCHEMA IF NOT EXISTS olympiados AUTHORIZATION olympiados;'
docker compose run --rm --no-deps app python -m server.cli init
docker compose run --rm --no-deps app python -m server.cli demo
docker compose up -d app
```

Keep the generated secrets privately to reopen the same volumes. Do not run `docker compose down -v` on data you need to retain. To inspect rather than seed demo, run `server.cli admin` interactively after init. This local owner-role setup must never be copied into production environment values.

## Intended same-origin Supabase + Render staging

The selected topology is one Docker web service serving FastAPI and static assets plus Supabase PostgreSQL/private Storage. `render.yaml` explicitly requests `plan: free`, manual deployment (`autoDeployTrigger: off`), `/api/ready`, no disk/worker/cron/database resource and one Uvicorn process. Verify current provider eligibility, quotas and limitations before authorizing resources. No always-on or zero-operating-effort promise is made.

First use [supabase-setup.md](supabase-setup.md) and [storage-setup.md](storage-setup.md) on an authorized, empty/synthetic staging target. Then set the runtime-only environment values from `.env.production.example` using the provider secret store. Copy the exact HTTPS service origin. Provide the real certificate CA as a secret file at the path referenced by `sslrootcert`; `render.yaml` cannot invent or download a trusted CA for you. Set only the verified ingress-proxy addresses in `TRUSTED_PROXY_IPS`; never fix a proxy issue by blindly trusting every internet address.

Production launch is `sh scripts/container-start.sh`. It rejects `MIGRATION_DATABASE_URL`, runs `python -m server.cli check` and only then starts Uvicorn on `$PORT` (8000 fallback for local containers). It does not initialize/migrate/seed. The Docker image runs as UID 10001; its only local data path in production is temporary processing space. `GET /api/health` is cheap liveness; `/api/ready` checks DB/schema reachability, not Codeforces or Storage on each probe.

The runtime URL must use the restricted role; the operator role never belongs in the hosted runtime. Do not add Supabase Auth, anonymous/service browser keys, artificial keep-alive traffic or scheduled jobs to make the setup appear complete.

## Operators, migrations and rollback

The original Alembic baseline is retained. Only an authorized operator applies migrations, then re-applies/reviews policies before app startup. For an existing development SQLite copy, the forward migration was tested; that is **not a school-data cutover rehearsal**. The production relational/object importer, canonical verifier, encrypted backup/restore and migration ledger remain Phase 4 implementation work. Do not use a SQLite SQL dump as PostgreSQL import or point this app at the only V1 copy.

Before any real data, verify a database-plus-object restore, scoped permissions, native browser flow and operator handoff. Before reopening V1 after V2 has accepted writes, preserve/reconcile those writes; never switch back to a stale frozen DB. Prefer a compatible build/forward repair over destructive schema downgrade. Do not use Alembic `downgrade` as a live student-data rollback.

Primary provider references checked during implementation (documentation, not deployment evidence):
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/platform/backups
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free
