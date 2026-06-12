#!/bin/bash

# Woodful Creations - Backend Start Script

echo "Starting Woodful Creations Backend..."
echo ""

# Check if virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo "ERROR: Virtual environment not found"
    echo "Please run setup.sh first"
    exit 1
fi

# Activate virtual environment
source backend/venv/bin/activate

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    echo "WARNING: backend/.env not found"
    echo "Using .env.example as template"
    cp backend/.env.example backend/.env
fi

# Start the server
echo "Starting FastAPI server..."
echo "API will be available at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/api/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd backend
python main.py
