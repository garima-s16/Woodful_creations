#!/bin/bash
# Woodful Creations - Start the React frontend dev server

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

if [ ! -f ".env" ]; then
    echo "WARNING: frontend/.env not found. Copying from .env.example."
    cp .env.example .env
fi

# Defect repair: an existing frontend/.env from before this fix (this
# exact line was .env.example's own old default, so anyone who ran the
# "copy .env.example .env" step above prior to this fix has it
# verbatim) silently breaks login - see frontend/src/utils/api.js's
# comment on API_URL for the full SameSite/cross-site explanation.
# Migrated automatically, in place, rather than left for a person to
# notice only after hitting the resulting "logs in, then immediately
# logged out" symptom. Only ever touches this one exact known-stale
# value - never touches a REACT_APP_API_URL a person has deliberately
# set to something else (a real deployment override, a non-default
# port, etc.).
if grep -qx 'REACT_APP_API_URL=http://127.0.0.1:8000' .env 2>/dev/null; then
    echo "Migrating frontend/.env: REACT_APP_API_URL 127.0.0.1 -> localhost (see api.js for why)."
    sed -i.bak 's#^REACT_APP_API_URL=http://127\.0\.0\.1:8000$#REACT_APP_API_URL=http://localhost:8000#' .env
    rm -f .env.bak
fi

exec npm start
