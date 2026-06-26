#!/usr/bin/env bash
# dev.sh — one-click local dev: start MongoDB (Docker) + backend + frontend
# Backend and frontend run in the background; Ctrl+C stops both.
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"

echo "== TaskFlow — local dev =="

# 1. Ensure MongoDB is up (via Docker, if available)
if command -v docker >/dev/null 2>&1; then
  if [ "$(docker ps --filter 'name=tm-mongo' --format '{{.Names}}')" != "tm-mongo" ]; then
    echo "Starting MongoDB container 'tm-mongo'..."
    docker start tm-mongo 2>/dev/null || docker run -d -p 27017:27017 --name tm-mongo mongo:7 >/dev/null
  else
    echo "MongoDB container already running."
  fi
else
  echo "Docker not found — make sure MongoDB is running on localhost:27017."
fi

# 2. Start backend + frontend, stop both on exit
pids=()
cleanup() { echo; echo "Stopping..."; for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

bash "$root/backend/dev.sh" &  pids+=($!)
bash "$root/frontend/dev.sh" & pids+=($!)

echo
echo "Backend  -> http://localhost:8000"
echo "Frontend -> http://localhost:5173  (login: admin / admin1234)"
echo "Press Ctrl+C to stop."
wait
