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
# from .env the same way app/platform/configuration/config.py does, and default to
# "development" only when it's genuinely absent - never default toward
# reload=True if ENVIRONMENT is set to anything else.
ENVIRONMENT_VALUE="$(grep -E '^ENVIRONMENT=' .env | tail -1 | cut -d '=' -f2- | tr -d '[:space:]')"
ENVIRONMENT_VALUE="${ENVIRONMENT_VALUE:-development}"

if [ "$ENVIRONMENT_VALUE" = "development" ]; then
    exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
    echo "ENVIRONMENT=$ENVIRONMENT_VALUE - starting without --reload (reload is development-only)."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
