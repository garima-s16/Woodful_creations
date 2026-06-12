#!/bin/bash

# Woodful Creations - Start Script

echo "=========================================="
echo "Starting Woodful Creations"
echo "=========================================="
echo ""

# Start backend in background
echo "Starting Backend API on port 8000..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start frontend
echo "Starting Frontend on port 3000..."
cd frontend
npm start

# Kill backend process when frontend exits
kill $BACKEND_PID 2>/dev/null
