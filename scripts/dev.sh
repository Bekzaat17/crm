#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
backend_pid=""
frontend_pid=""
worker_pid=""
cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$frontend_pid" ]]; then kill "$frontend_pid" 2>/dev/null || true; fi
  if [[ -n "$backend_pid" ]]; then kill "$backend_pid" 2>/dev/null || true; fi
  if [[ -n "$worker_pid" ]]; then kill "$worker_pid" 2>/dev/null || true; fi
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM
(cd backend && exec ../.venv/bin/python manage.py runserver 127.0.0.1:8100 --noreload) &
backend_pid=$!
(cd web && exec ./node_modules/.bin/next dev --hostname 127.0.0.1 --port 3100) &
frontend_pid=$!
(cd backend && exec ../.venv/bin/python manage.py deliver_admissions) &
worker_pid=$!
printf '%s\n' 'RehubPro CRM: http://127.0.0.1:3100' 'Письма подтверждения и приглашения появятся в этом терминале.'
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null && kill -0 "$worker_pid" 2>/dev/null; do sleep 1; done
exit 1
