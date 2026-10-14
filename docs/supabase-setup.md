# Supabase PostgreSQL setup — authorized staging runbook

**Status: configuration/SQL supplied, not executed against Supabase here.** Do not migrate real students or declare the cloud boundary verified until [RELEASE-GATES.md](RELEASE-GATES.md) is satisfied. The full F05 data-import/backup/restore tooling is not yet implemented.

## 1. Ownership and environment

The school must own/recover provider access, approve the region and appoint a successor and backup custodian. Confirm actual Free-project eligibility/current limits without enabling paid resources by accident. Create a project only under that separate authorization. Record PostgreSQL version and exact connection information; do not assume it matches local CI PostgreSQL 16.

Use the dashboard's copied **session pooler** endpoint for an IPv4-compatible persistent backend. This code sets session `search_path`, so the transaction pooler is not interchangeable. Direct connections are an alternative only with actual supported networking and tested TLS. Require `sslmode=verify-full` plus the appropriate trusted CA; `sslmode=require` alone is not treated as equivalent hostname verification. Do not invent pooler hosts or certificate paths.

The application retains V1 authentication; do not configure Supabase Auth user import or put a Supabase anonymous key in the frontend. Keep the `olympiados` schema out of exposed Data API schemas and disable unused exposure where supported.

## 2. Bootstrap with a separate operator connection

Install trusted PostgreSQL client tools and Python dependencies on the operator workstation. Use the real operator connection in a protected libpq service/passfile or secret store, not pasted into tickets/source. The following `psql` invocations assume a privately configured service named `adolat_operator`:

```sh
psql 'service=adolat_operator' -v ON_ERROR_STOP=1 -f supabase/bootstrap.sql
```

The SQL creates `olympiados` and an initially NOLOGIN `olympiados_app`, with no superuser/replication/BYPASSRLS/role/database creation powers and no assumable memberships. It fails rather than silently accepting a pre-existing privileged runtime identity. It excludes browser roles from schema usage and revokes PUBLIC creation in `public`. **Use only a dedicated application project**; do not apply it to unrelated workloads without reviewing its grants.

The operator needs the role/schema creation privileges appropriate to the actual managed PostgreSQL version. It is not necessarily a cluster superuser. Bootstrap deliberately checks existing sensitive attributes rather than unconditionally trying to alter SUPERUSER/REPLICATION on a managed role. If a permission check fails, stop and resolve it through authorized administration; do not grant the web runtime more power.

Set a strong unique runtime password in an interactive private operator session using `\password olympiados_app`, then enable `ALTER ROLE olympiados_app LOGIN;`. Keep operator and runtime credentials distinct. Confirm the managed pooler supports your actual role-qualified username before continuing.

## 3. Apply the frozen baseline and forward migration

On the **operator workstation only**, export the operator SQLAlchemy URL as `DATABASE_URL`, set `DB_SCHEMA=olympiados`, and use `APP_ENV=development` for this CLI-only setup (not an externally served web instance). Set a separate temporary local `DATA_DIR`; no Storage operation occurs during schema initialization. Password characters in the URL must be percent-encoded.

```sh
python -m pip install -r requirements-postgres.txt
# DATABASE_URL, DATA_DIR and DB_SCHEMA are supplied privately by the operator.
APP_ENV=development python -m server.cli init
APP_ENV=development python -m server.cli init
APP_ENV=development python -m alembic check
psql 'service=adolat_operator' -v ON_ERROR_STOP=1 -f supabase/apply_policies.sql
```

The CLI `init` uses its explicit `DATABASE_URL`. Direct Alembic can alternatively use `MIGRATION_DATABASE_URL`; never send this value to a web service. Initialization is idempotent on fixtures, creates subjects/settings but no accounts, and expects the private schema to exist. `current_schema()` is asserted; there is no creation fallback into `public`. The expected head is `d84f103f71aa`. Do not edit the original V1 baseline or copy SQLite's Alembic marker as proof that PostgreSQL is correct.

Policies must be applied by the **same operator identity that owns the tables**. Every table receives RLS/FORCE RLS, explicit backend DML, operator policy and no browser-role grants. `alembic_version` is read-only to runtime. New tables do not silently inherit DML grants; repeat the policy step after future migrations.

The scripts use the normative schema name `olympiados`. Do not change `DB_SCHEMA` in production without separately adapting/reviewing the SQL. Random private schema names are used only by disposable CI fixtures.

## 4. Verify the restricted runtime directly

Switch to the **runtime** URL and production-only environment template, including durable Storage settings and exact HTTPS origin. `python -m server.cli check` checks revision, role capabilities/memberships, schema ownership/creation, public/database creation, forced table RLS and browser-role schema denial. It must pass before container startup.

Independently verify on the actual target, not just through the app:

```sql
SELECT current_user, current_schema();
SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
FROM pg_roles WHERE rolname = current_user;
SELECT has_schema_privilege(current_user, 'olympiados', 'CREATE');
SELECT has_schema_privilege(current_user, 'public', 'CREATE');
SELECT has_database_privilege(current_user, current_database(), 'CREATE');
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='olympiados' AND c.relkind='r';
```

All privileged-role flags and persistent CREATE grants must be false; application tables must be in the correct schema with RLS forced. In isolated transactions, prove that runtime cannot create/alter application tables, update `alembic_version`, or assume an operator role. Prove anonymous/authenticated Data API roles have no application access and verify actual unauthorized HTTP calls. Roll back each attempted denial test. Never use a real student table as destructive test material.

**Important:** backend RLS `USING(true)` is a backend allowance, not per-user privacy. The V1 cookie is not `auth.uid()`. FastAPI resource/membership/time checks enforce learner privacy, so the full negative API suite is required even after SQL roles pass.

## 5. Disposable PostgreSQL automated tests

Only on a disposable database whose name starts with `adolat_test`:

```sh
export TEST_DATABASE_CONFIRM=disposable
# Export TEST_DATABASE_URL privately, pointing to that disposable local database.
python -m pytest -q --ignore=tests/test_browser.py --ignore=tests/test_v2_browser.py
```

Each test creates/drops its own random private schema and never targets a school database. The supplied GitHub Actions service config defines such a database. This workflow has **not run in the present environment**, and the fixture's owner connection is not a substitute for separate restricted-role/Supabase tests or real concurrency tests.

Primary references: https://supabase.com/docs/guides/database/connecting-to-postgres ; https://supabase.com/docs/guides/database/postgres/roles ; https://supabase.com/docs/guides/database/postgres/row-level-security ; https://www.postgresql.org/docs/current/sql-createrole.html ; https://www.postgresql.org/docs/current/sql-alterrole.html . These documented mechanisms must still be verified against your project's actual version/permissions.
