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

exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
