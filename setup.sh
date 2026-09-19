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
        # SECRET_KEY ships empty in .env.example (never a real secret in a
        # committed file) - but app/platform/config.py requires a real
        # 32+ char value just to import the app at all, which the
        # migration step immediately below does. Left empty, "alembic
        # upgrade head" below fails on every fresh setup before a user
        # ever gets a chance to edit the file. Auto-generate a real
        # local-dev-only secret now, the same way .env.example's own
        # comment tells a person to by hand - never touches an existing
        # backend/.env (this whole block is inside the "doesn't exist yet"
        # branch), so it can never overwrite a value someone already set.
        GENERATED_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
        # macOS/BSD sed requires an argument to -i (even if empty); GNU
        # sed accepts -i alone. The portable form below works on both.
        sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=${GENERATED_SECRET_KEY}|" backend/.env && rm -f backend/.env.bak
        echo "Generated a local-development SECRET_KEY in backend/.env"
        echo "IMPORTANT: Please review backend/.env - the SECRET_KEY above is fine for local dev only; every other value (database, email, AI keys) still needs your own configuration"
    fi
else
    echo "backend/.env already exists"
fi
echo ""

# Run database migrations - without this, a fresh clone has a venv,
# dependencies, and a .env file, but no database tables at all, and the
# app fails with confusing errors the moment it's actually run (SQLite
# by default; uses whatever DATABASE_URL is configured in backend/.env
# above). Only meaningful once .env exists, hence run after the check
# above rather than immediately after dependency install.
echo "Running database migrations..."
source backend/venv/bin/activate
cd backend
# Previously `alembic upgrade head && echo ... || echo "WARNING: ..."` -
# that `A && B || C` form always ends on a successful `echo` (C), so its
# own exit status is 0 regardless of whether the migration itself
# failed. Combined with `set -e` at the top of this script, a genuinely
# failed migration was silently swallowed and setup carried on all the
# way to a misleading "Setup Complete!". A real if/else instead, which
# does not mask alembic's exit status - a failed migration now stops
# setup here, with a non-zero exit code, and never reaches "Setup
# Complete!" below.
if alembic upgrade head; then
    echo "Migrations applied"
else
    echo ""
    echo "ERROR: Database migration failed. Check backend/.env's DATABASE_URL and SECRET_KEY, then run 'cd backend && alembic upgrade head' manually to see the full error." >&2
    cd ..
    deactivate
    exit 1
fi
cd ..
deactivate
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
echo "2. Start both servers:"
echo "   ./start_all.sh"
echo ""
echo "3. Access the application:"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Frontend: http://localhost:3000"
echo ""
