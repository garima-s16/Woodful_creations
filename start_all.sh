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

# Start backend in background
echo "Starting backend server on http://localhost:8000"
bash start_backend.sh &
BACKEND_PID=$!

# Give backend time to start
sleep 3

# Start frontend in background
echo "Starting frontend server on http://localhost:3000"
bash start_frontend.sh &
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
