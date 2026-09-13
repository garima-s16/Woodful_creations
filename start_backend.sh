#!/bin/bash
# Woodful Creations - Start the FastAPI backend
# The app object lives at app/main.py (app.main:app), not at top-level main.py.

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
    echo "ERROR: backend/venv not found. Run ./setup.sh first."
    exit 1
fi

source venv/bin/activate

if [ ! -f ".env" ]; then
    echo "WARNING: backend/.env not found. Copying from .env.example - edit it before real use."
    cp .env.example .env
fi

# --reload is a development convenience (it re-imports the app on every file
# change) and must never be used in production - it adds overhead, can mask
# startup errors, and this same reasoning is why docker-entrypoint.sh (the
# production/Docker launch path) never passes it either. Read ENVIRONMENT
# from .env the same way app/platform/config.py does, and default to
# "development" only when it's genuinely absent - never default toward
# reload=True if ENVIRONMENT is set to anything else.
ENVIRONMENT_VALUE="$(grep -E '^ENVIRONMENT=' .env | tail -1 | cut -d '=' -f2- | tr -d '[:space:]')"
ENVIRONMENT_VALUE="${ENVIRONMENT_VALUE:-development}"

# Defect repair: "::" (the IPv6 wildcard), not "0.0.0.0" (the IPv4-only
# wildcard) - a dual-stack bind. On Windows (default since Vista) and
# on virtually every Linux distro (default net.ipv6.bindv6only=0),
# this one socket accepts BOTH ::1 and 127.0.0.1/any-IPv4 connections,
# so it doesn't matter which address family "localhost" happens to
# resolve to first on a given machine - the backend answers
# immediately either way. This is what makes it safe for the frontend
# to default to http://localhost:8000 (see frontend/.env.example and
# frontend/src/utils/api.js) instead of 127.0.0.1: same host on both
# ends keeps every request "same-site" for the SameSite=Lax auth
# cookie, which 127.0.0.1-vs-localhost was silently breaking (see
# those files for the full explanation). If IPv6 is ever genuinely
# disabled at the OS level on a given machine, uvicorn will fail to
# bind here - revert this one flag to --host 0.0.0.0 and set
# REACT_APP_API_URL=http://127.0.0.1:8000 in frontend/.env (a
# supported override, not a default meant for everyone else).
if [ "$ENVIRONMENT_VALUE" = "development" ]; then
    exec uvicorn app.main:app --reload --host :: --port 8000
else
    echo "ENVIRONMENT=$ENVIRONMENT_VALUE - starting without --reload (reload is development-only)."
    exec uvicorn app.main:app --host :: --port 8000
fi
