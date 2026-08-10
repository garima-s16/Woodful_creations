#!/bin/bash
# Woodful Creations - Start backend only
set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
    echo "No virtual environment found. Run setup.sh first."
    exit 1
fi

source venv/bin/activate
python main.py
