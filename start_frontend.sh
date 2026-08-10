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

exec npm start
