#!/bin/sh
set -eu
umask 077
# No migrations, demo data or privileged operator URL at web startup.
if [ -n "${MIGRATION_DATABASE_URL:-}" ]; then
  echo 'Remove MIGRATION_DATABASE_URL from the web runtime environment.' >&2
  exit 1
fi
python -m server.cli check
exec python -m uvicorn server.app:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips="${TRUSTED_PROXY_IPS:-127.0.0.1}"
