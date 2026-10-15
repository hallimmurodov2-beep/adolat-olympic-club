"""Vercel ASGI entrypoint with strict, bundled Supabase CA verification."""
import os
from pathlib import Path

if os.environ.get("APP_ENV") == "production":
    certificate = Path(__file__).resolve().with_name("prod-ca-2021.crt")
    if not certificate.is_file():
        raise RuntimeError("Bundled Supabase CA certificate is missing; refusing DB connection.")
    # psycopg/libpq respects PGSSLROOTCERT when DATABASE_URL sets sslmode=verify-full.
    # Avoid guessing Vercel's absolute deployment directory in the secret URL.
    os.environ["PGSSLROOTCERT"] = str(certificate)

from server.app import app  # Vercel serverless Python ASGI entrypoint
