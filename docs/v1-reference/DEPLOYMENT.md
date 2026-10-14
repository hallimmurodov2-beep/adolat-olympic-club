# Setup and deployment

## Local SQLite installation

Follow the root README. By default, all private state is in `.data/`; the server generates a persistent local session secret there. Apply migrations with `python -m server.cli init` before starting. Repeating `init` is safe. It initializes subjects/settings but does not create accounts. Do not distribute your populated `.data/` directory with source archives.

Changing `DATA_DIR` changes the default SQLite location and private upload location. To use `.env` in a POSIX shell, explicitly load your trusted file with `set -a; . ./.env; set +a`. The Python application does not silently execute or automatically source an environment file. The quick-start default needs no `.env`.

Use `--host 127.0.0.1` for developer-only access. A classroom pilot over a network should use production settings behind HTTPS, not share an unencrypted development login endpoint. The API and browser application must remain on the same origin.

## PostgreSQL/container configuration

**Configuration supplied; not executed in the delivery sandbox.** Registry access, Docker, a PostgreSQL runtime, hosting credentials, and TLS/domain access were not available for validating this deployment.

1. Install Docker Engine/Compose on your server and configure your domain. Keep TCP 8000 and the database private; expose only the HTTPS proxy.
2. Copy `.env.production.example` to `.env`. Set your real HTTPS APP_ORIGIN. Generate APP_SECRET and POSTGRES_PASSWORD independently with `python -c "import secrets; print(secrets.token_hex(32))"`. The Compose URL interpolation expects a hexadecimal password; URL-encode any custom password containing reserved characters.
3. Run `docker compose up --build -d`. Startup waits for PostgreSQL health, applies Alembic migrations, and starts the application as UID 10001. The build installs declared dependencies and therefore needs registry access.
4. Bootstrap: `docker compose exec app python -m server.cli admin --email admin@your-school.example --name "Club administrator"`.
5. Install/configure a host reverse proxy using `docs/Caddyfile.example` as a starting point. Replace the sample domain; provide DNS and firewall access for certificate issuance. SSE buffering must remain disabled. Configure TRUSTED_PROXY_IPS to the actual peer IP visible to the application. The exact address depends on your host/container network; do not substitute a wildcard.
6. Open the HTTPS origin, choose the school time zone, invite teachers, and perform the staging checks in SECURITY.md before inviting students.

The Compose PostgreSQL service has no host port. Private uploads and PostgreSQL records use separate persistent volumes. Do not use `docker compose down -v` on a live installation: it deletes those volumes. The example uses PostgreSQL 16, not a claim that it is the newest release. Pin container image digests and review updates for your deployment.

For an existing PostgreSQL service, install `requirements-postgres.txt`, set `DATABASE_URL=postgresql+psycopg://...`, DATA_DIR, APP_ENV=production, APP_SECRET, and APP_ORIGIN, then run the same migration/bootstrap commands. Use a separate runtime role with only needed data privileges after migrations; there is no database RLS policy in this version.

## Staging acceptance

Run the automated suite against the delivered local configuration, then adapt the fixture database URL or run an equivalent full workflow on PostgreSQL. Verify invitation redemption, unrelated-teacher/student denials, file access, concurrent document saves, rubric checks, session release through a real SSE connection, browser reconnection, server-side competition cutoffs, and review publication. Test a mobile Russian layout, a native browser upload/download, fullscreen projector mode, and timezone/DST behavior for your configured school location.

The API health endpoint checks database connectivity; it does not certify migrations, file permissions, TLS, or every user workflow. Monitor failures and disk space. Use one migration runner and coordinate schema changes/backups before multiple replicas. SQLite is deliberately the single-worker local mode, not the deployment recommendation for a growing multi-worker installation.

## Backup and recovery

For PostgreSQL, take logical or managed-service database backups together with a consistent private-upload snapshot. Retain necessary secret configuration separately with restricted access. For a local SQLite test deployment, stop the app before copying the database and upload directory, or implement the SQLite online backup API. Verify restores on a separate test installation.

Account recovery is intentionally school-mediated: verify identity, then `python -m server.cli reset-password --email ...`. All existing sessions are revoked. An administrator cannot read passwords and users cannot promote themselves. There is no SMTP/SMS integration to configure.

No public deployment URL is included because none was created.

A GitHub Actions workflow is included for normal-browser tests and a PostgreSQL migration smoke job. The workflow has not been run remotely as part of this delivery.
