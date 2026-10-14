#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if command -v tsc >/dev/null 2>&1; then tsc --noEmit; else npx --no-install tsc --noEmit; fi
python -m compileall -q server
python -m pytest -q --ignore=tests/test_browser.py --ignore=tests/test_v2_browser.py
