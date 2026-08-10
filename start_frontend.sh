#!/bin/bash
# Woodful Creations - Start frontend only
set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "node_modules not found. Run setup.sh first (or 'npm install' here)."
    exit 1
fi

npm start
