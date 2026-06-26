#!/usr/bin/env bash
# backend/test.sh — run smoke + HTTP integration tests (no MongoDB needed)
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ./.venv/bin/python ]; then
  echo "No .venv found. Run ./dev.sh first."; exit 1
fi

./.venv/bin/python -m pip install -q -r requirements-dev.txt
echo; echo "== smoke_test =="
./.venv/bin/python tests/smoke_test.py
echo; echo "== http_test =="
./.venv/bin/python tests/http_test.py
