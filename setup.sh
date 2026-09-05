#!/bin/bash

# Woodful Creations - Development Setup Script
# This script sets up the complete development environment

set -e

echo "======================================"
echo "Woodful Creations - Setup Script"
echo "======================================"
echo ""

# Check if Python is installed
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"
echo ""

# Check if PostgreSQL is installed
echo "Checking PostgreSQL installation..."
if ! command -v psql &> /dev/null; then
    echo "WARNING: PostgreSQL is not installed."
    echo "Please install PostgreSQL 13 or higher from https://www.postgresql.org/download/"
    echo ""
    read -p "Continue without PostgreSQL? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    PG_VERSION=$(psql --version)
    echo "Found $PG_VERSION"
fi
echo ""

# Create virtual environment for backend
echo "Creating Python virtual environment for backend..."
if [ ! -d "backend/venv" ]; then
    cd backend
    python3 -m venv venv
    cd ..
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi
echo ""

# Activate virtual environment and install dependencies
echo "Installing backend dependencies..."
source backend/venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt
deactivate
echo "Backend dependencies installed"
echo ""

# Create logs directory
echo "Creating logs directory..."
mkdir -p backend/logs
echo "Logs directory created"
echo ""

# Create uploads directory
echo "Creating uploads directory..."
mkdir -p backend/uploads
echo "Uploads directory created"
echo ""

# Check .env file
echo "Checking environment configuration..."
if [ ! -f "backend/.env" ]; then
    if [ -f "backend/.env.example" ]; then
        cp backend/.env.example backend/.env
        echo "Created backend/.env from template"
        echo "IMPORTANT: Please edit backend/.env with your configuration"
    fi
else
    echo "backend/.env already exists"
fi
echo ""

# Check frontend node_modules
echo "Checking frontend setup..."
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    if [ -f "frontend/package.json" ]; then
        if ! command -v npm &> /dev/null; then
            echo "WARNING: Node.js/npm is not installed"
            echo "Please install Node.js from https://nodejs.org/"
            echo "Then run: cd frontend && npm install"
        else
            cd frontend
            npm install
            cd ..
            echo "Frontend dependencies installed"
        fi
    fi
else
    echo "Frontend dependencies already installed"
fi
echo ""

echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure database (optional - can use SQLite for testing):"
echo "   - Edit backend/.env with your PostgreSQL credentials"
echo "   - Or leave as-is to use SQLite"
echo ""
echo "2. Start the backend server:"
echo "   ./start_backend.sh"
echo ""
echo "3. In another terminal, start the frontend:"
echo "   ./start_frontend.sh"
echo ""
echo "4. Access the application:"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/api/docs"
echo "   Frontend: http://localhost:3000"
echo ""
