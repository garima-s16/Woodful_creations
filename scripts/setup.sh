#!/bin/bash

# Woodful Creations - Setup Script
# This script sets up the entire project environment

set -e

echo "============================================"
echo "Woodful Creations - Project Setup"
echo "============================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print success messages
success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

# Function to print error messages
error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

# Function to print info messages
info() {
    echo -e "${YELLOW}[INFO] $1${NC}"
}

# Check if Python is installed
info "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 is not installed. Please install Python 3.8 or higher."
fi
success "Python 3 is installed: $(python3 --version)"
echo ""

# Check if Node.js is installed
info "Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    error "Node.js is not installed. Please install Node.js 16 or higher."
fi
success "Node.js is installed: $(node --version)"
echo ""

# Check if npm is installed
info "Checking npm installation..."
if ! command -v npm &> /dev/null; then
    error "npm is not installed. Please install npm."
fi
success "npm is installed: $(npm --version)"
echo ""

# Create virtual environment for backend
info "Setting up Python virtual environment..."
if [ -d "backend/venv" ]; then
    info "Virtual environment already exists."
else
    python3 -m venv backend/venv
    success "Virtual environment created"
fi
echo ""

# Activate virtual environment
info "Activating virtual environment..."
source backend/venv/bin/activate
success "Virtual environment activated"
echo ""

# Install backend dependencies
info "Installing backend dependencies..."
pip install --upgrade pip
pip install -r backend/requirements.txt
success "Backend dependencies installed"
echo ""

# Install frontend dependencies
info "Installing frontend dependencies..."
cd frontend || error "Frontend directory not found"
npm install
success "Frontend dependencies installed"
cd ..
echo ""

# Create environment files
info "Creating environment configuration files..."

# Create backend .env file
if [ ! -f "backend/.env" ]; then
    cat > backend/.env << EOF
# Backend Configuration
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production
DATABASE_URL=postgresql://user:password@localhost:5432/woodful_db
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# AI Configuration (Optional)
OPENAI_API_KEY=your-openai-api-key
EOF
    success "Backend .env file created"
else
    info ".env file already exists"
fi
echo ""

# Create frontend .env file
if [ ! -f "frontend/.env" ]; then
    cat > frontend/.env << EOF
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_ENVIRONMENT=development
EOF
    success "Frontend .env file created"
else
    info "Frontend .env file already exists"
fi
echo ""

# Create necessary directories
info "Creating project directories..."
mkdir -p backend/app/routes
mkdir -p backend/app/models
mkdir -p backend/app/schemas
mkdir -p backend/app/services
mkdir -p backend/app/utils
mkdir -p backend/app/database
mkdir -p backend/migrations
mkdir -p frontend/src/components
mkdir -p frontend/src/screens
mkdir -p frontend/src/redux
mkdir -p frontend/src/services
mkdir -p frontend/src/utils
mkdir -p frontend/src/assets/images
mkdir -p frontend/src/assets/fonts
mkdir -p desktop/src
mkdir -p logs
success "Project directories created"
echo ""

# Initialize git hooks (optional)
info "Setting up git hooks..."
if [ -d ".git" ]; then
    # Create pre-commit hook
    mkdir -p .git/hooks
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
echo "Running linters..."
npm run lint --prefix frontend
EOF
    chmod +x .git/hooks/pre-commit
    success "Git hooks configured"
else
    info "Git repository not initialized"
fi
echo ""

# Database setup instructions
echo ""
info "=========================================="
info "PostgreSQL Setup Instructions"
info "=========================================="
info "Please ensure PostgreSQL is installed and running."
info "Create the database:"
echo "  psql -U postgres -c \"CREATE DATABASE woodful_db;\""
info ""
info "Then run migrations:"
echo "  cd backend && alembic upgrade head"
echo ""

# Final summary
echo ""
echo -e "${GREEN}=========================================="
echo "Setup completed successfully"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Backend:"
echo "   - Update backend/.env with your configuration"
echo "   - Activate virtual environment: source backend/venv/bin/activate"
echo "   - Run migrations: cd backend && alembic upgrade head"
echo "   - Start server: python -m uvicorn app.main:app --reload"
echo ""
echo "2. Frontend:"
echo "   - Update frontend/.env with your API URL"
echo "   - Start dev server: cd frontend && npm start"
echo ""
echo "3. Desktop (PyQt5):"
echo "   - Install desktop dependencies: pip install -r desktop/requirements.txt"
echo "   - Run desktop app: python desktop/main.py"
echo ""
echo "Application will be available at:"
echo "  - Frontend (Web): http://localhost:3000"
echo "  - Backend API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo ""