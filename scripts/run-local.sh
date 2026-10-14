#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
python -m server.cli init
exec python -m uvicorn server.app:app --host 127.0.0.1 --port "${PORT:-8000}"
