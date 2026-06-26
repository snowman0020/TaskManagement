#!/usr/bin/env bash
# backend/dev.sh — one-click: create venv (Python 3.12) + install + run backend
set -euo pipefail
cd "$(dirname "$0")"

echo "== TaskFlow backend setup =="

# Pick a compatible interpreter (3.12/3.11) to avoid the Python 3.14 pydantic-core build error
PY=""
for c in python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then echo "No python3 found. Install Python 3.12."; exit 1; fi

if [ ! -d .venv ]; then
  echo "Creating .venv with $PY ..."
  "$PY" -m venv .venv
fi

./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt

[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example"; }

echo
echo "Make sure MongoDB is running (e.g. docker run -d -p 27017:27017 --name tm-mongo mongo:7)"
echo "Starting backend on http://localhost:8000 (docs: /docs)"
echo
exec ./.venv/bin/python -m uvicorn app.main:app --reload
