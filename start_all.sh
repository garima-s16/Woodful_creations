#!/bin/bash

# Woodful Creations - Complete Development Environment Setup

echo "======================================"
echo "Woodful Creations - Quick Start"
echo "======================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Run setup if not already done
if [ ! -d "backend/venv" ] || [ ! -d "frontend/node_modules" ]; then
    echo "Running initial setup..."
    bash setup.sh
    if [ $? -ne 0 ]; then
        echo "Setup failed!"
        exit 1
    fi
fi

echo ""
echo "Starting Woodful Creations in development mode..."
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down services..."
    pkill -P $$ 2>/dev/null
    wait
}

trap cleanup EXIT

# Start backend in background (inlined rather than a separate
# start_backend.sh, so this one script is the sole source of truth for
# how the dev servers are actually launched).
# Host is "::" (IPv6 wildcard), not "0.0.0.0" (IPv4-only): on Windows
# in particular, "localhost" often resolves to ::1 (IPv6) first, and a
# server bound only to 0.0.0.0 never accepts that connection attempt -
# producing exactly the "Unable to connect to Woodful server" symptom.
# "::" is a dual-stack bind (accepts both ::1 and 127.0.0.1 traffic on
# Windows/Linux by default), so localhost resolves correctly either way.
# The frontend's API_URL stays http://localhost:8000 unchanged.
echo "Starting backend server on http://localhost:8000"
(
    cd "$SCRIPT_DIR/backend"
    source venv/bin/activate
    exec uvicorn app.main:app --host :: --port 8000 --reload
) &
BACKEND_PID=$!

# Give backend time to start
sleep 3

# Start frontend in background (inlined, same reasoning as backend above)
echo "Starting frontend server on http://localhost:3000"
(
    cd "$SCRIPT_DIR/frontend"
    exec npm start
) &
FRONTEND_PID=$!

echo ""
echo "======================================"
echo "Both servers are running!"
echo "======================================"
echo ""
echo "Access points:"
echo "  Backend API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

wait
