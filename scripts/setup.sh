#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================"
echo "WOODFUL CREATIONS - Complete Setup"
echo "======================================"
echo ""

# Detect operating system
OS_TYPE=$(uname -s)
case "$OS_TYPE" in
    Darwin*)
        OS_NAME="macOS"
        VENV_ACTIVATE="source venv/bin/activate"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        OS_NAME="Windows"
        VENV_ACTIVATE="venv\Scripts\activate"
        ;;
    Linux*)
        OS_NAME="Linux"
        VENV_ACTIVATE="source venv/bin/activate"
        ;;
    *)
        OS_NAME="Unknown"
        ;;
esac

echo "Detected OS: $OS_NAME"
echo ""

# VALIDATION CHECKS

# Check Python installation
echo "[1/11] Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if (( PYTHON_MAJOR > 3 )) || (( PYTHON_MAJOR == 3 && PYTHON_MINOR >= 9 )); then
        echo "Python $PYTHON_VERSION found (required: 3.9+)"
    else
        echo "Python version $PYTHON_VERSION is too old. Please install Python 3.9 or higher."
        exit 1
    fi
else
    echo "Python is not installed. Please install Python 3.9 or higher."
    echo "Visit: https://www.python.org/downloads/"
    exit 1
fi

# Check Node.js installation
echo ""
echo "[2/11] Checking Node.js installation..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "Node.js $NODE_VERSION found"
else
    echo "Node.js is not installed. Please install Node.js 16 or higher."
    echo "Visit: https://nodejs.org/en/download/"
    exit 1
fi

# Check npm installation
echo ""
echo "[3/11] Checking npm installation..."
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo "npm $NPM_VERSION found"
else
    echo "npm is not installed. Please install npm."
    exit 1
fi

# Check PostgreSQL installation
echo ""
echo "[4/11] Checking PostgreSQL installation..."
if command -v psql &> /dev/null; then
    POSTGRES_VERSION=$(psql --version)
    echo "$POSTGRES_VERSION found"
else
    echo "PostgreSQL is not installed or not in PATH."
    echo "Visit: https://www.postgresql.org/download/"
    echo "Note: You can continue and configure PostgreSQL later."
fi

# BACKEND SETUP

# Create Python virtual environment for FastAPI
echo ""
echo "[5/11] Creating Python virtual environment for FastAPI..."
if [ -d "backend/venv" ]; then
    echo "Virtual environment already exists. Skipping..."
else
    cd backend
    python3 -m venv venv
    
    if [ "$OS_NAME" = "Windows" ]; then
        call venv\Scripts\activate.bat
    else
        source venv/bin/activate
    fi
    
    echo "Virtual environment created"
    
    # Install Python dependencies
    echo ""
    echo "Installing FastAPI and dependencies..."
    pip install --upgrade pip setuptools wheel > /dev/null 2>&1
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        echo "Python dependencies installed"
    else
        echo "requirements.txt not found. Creating template..."
        cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.4.2
pydantic-settings==2.0.3

sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1

python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
PyJWT==2.8.1

python-dotenv==1.0.0
aiosmtplib==3.0.1
email-validator==2.1.0

openai==1.3.5
langchain==0.1.0
langchain-community==0.0.8

reportlab==4.0.7
openpyxl==3.1.2
python-docx==0.8.11
PyPDF2==3.0.1

pandas==2.1.2
numpy==1.26.2

requests==2.31.0
httpx==0.25.2
Pillow==10.1.0

pytest==7.4.3
pytest-asyncio==0.21.1
black==23.11.0
flake8==6.1.0

structlog==23.2.0
EOF
        pip install -r requirements.txt
        echo "Python dependencies installed"
    fi
    
    cd ..
fi

# BACKEND CONFIGURATION

echo ""
echo "[6/11] Creating backend configuration files..."

# Create .env file if it doesn't exist
if [ ! -f "backend/.env" ]; then
    cat > backend/.env << 'EOF'
DATABASE_URL=postgresql://woodful_user:your-secure-password@localhost:5432/woodful_creations
DATABASE_ECHO=false

SECRET_KEY=your-super-secret-key-change-this-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=7

DEBUG=False
ENVIRONMENT=development

HOST=0.0.0.0
PORT=8000
RELOAD=true
WORKERS=4

ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000

SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SENDER_EMAIL=noreply@woodful-creations.com

MASTER_USER_1_EMAIL=nikhil@woodful.com
MASTER_USER_1_NAME=Nikhil
MASTER_USER_2_EMAIL=garima@woodful.com
MASTER_USER_2_NAME=Garima

OPENAI_API_KEY=sk-your-openai-api-key-here
LANGCHAIN_API_KEY=your-langchain-api-key-here
LANGCHAIN_PROJECT=woodful-creations

ALERT_LOW_STOCK_THRESHOLD=10
ALERT_ETA_DAYS_BEFORE=7
ENABLE_EMAIL_ALERTS=true
ENABLE_DASHBOARD_ALERTS=true

MAX_FILE_SIZE_MB=50
ALLOWED_FILE_TYPES=pdf,png,jpg,jpeg,xlsx,docx,csv

LOG_LEVEL=INFO
LOG_FILE=woodful.log

MAX_REORDER_LEVEL=1000
MIN_STOCK_ALERT_THRESHOLD=10
FORECAST_DAYS=30

PDF_LOGO_PATH=assets/woodful_logo.png
PDF_HEADER_COLOR=#2E7D32

TIMEZONE=Asia/Kolkata

CURRENCY=INR
CURRENCY_SYMBOL=₹
EOF
    echo "backend/.env created"
else
    echo "backend/.env already exists. Skipping..."
fi

# Create .env.example for reference
if [ ! -f "backend/.env.example" ]; then
    cat > backend/.env.example << 'EOF'
DATABASE_URL=postgresql://woodful_user:password@localhost:5432/woodful_creations
DATABASE_ECHO=false

SECRET_KEY=your-super-secret-key-change-this-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=7

DEBUG=False
ENVIRONMENT=development

HOST=0.0.0.0
PORT=8000
RELOAD=true
WORKERS=4

ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000

SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SENDER_EMAIL=noreply@woodful-creations.com

MASTER_USER_1_EMAIL=nikhil@woodful.com
MASTER_USER_1_NAME=Nikhil
MASTER_USER_2_EMAIL=garima@woodful.com
MASTER_USER_2_NAME=Garima

OPENAI_API_KEY=sk-your-api-key
LANGCHAIN_API_KEY=your-api-key
LANGCHAIN_PROJECT=woodful-creations

ALERT_LOW_STOCK_THRESHOLD=10
ALERT_ETA_DAYS_BEFORE=7
ENABLE_EMAIL_ALERTS=true
ENABLE_DASHBOARD_ALERTS=true

MAX_FILE_SIZE_MB=50
ALLOWED_FILE_TYPES=pdf,png,jpg,jpeg,xlsx,docx,csv

LOG_LEVEL=INFO
LOG_FILE=woodful.log

MAX_REORDER_LEVEL=1000
MIN_STOCK_ALERT_THRESHOLD=10
FORECAST_DAYS=30

PDF_LOGO_PATH=assets/woodful_logo.png
PDF_HEADER_COLOR=#2E7D32

TIMEZONE=Asia/Kolkata
CURRENCY=INR
CURRENCY_SYMBOL=₹
EOF
    echo "backend/.env.example created"
else
    echo "backend/.env.example already exists. Skipping..."
fi

# FRONTEND SETUP

echo ""
echo "[7/11] Creating React/React Native frontend configuration..."

# Create frontend .env.local
if [ ! -f ".env.local" ]; then
    cat > .env.local << 'EOF'
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Woodful Creations
NEXT_PUBLIC_LOGO_PATH=/assets/woodful_logo.png
NEXT_PUBLIC_ENABLE_ANALYTICS=true
NEXT_PUBLIC_ENABLE_CHAT=true
NEXT_PUBLIC_ENABLE_EMAIL=true
EOF
    echo ".env.local created"
else
    echo ".env.local already exists. Skipping..."
fi

if [ ! -f ".env.example" ]; then
    cat > .env.example << 'EOF'
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Woodful Creations
NEXT_PUBLIC_LOGO_PATH=/assets/woodful_logo.png
NEXT_PUBLIC_ENABLE_ANALYTICS=true
NEXT_PUBLIC_ENABLE_CHAT=true
NEXT_PUBLIC_ENABLE_EMAIL=true
EOF
    echo ".env.example created"
else
    echo ".env.example already exists. Skipping..."
fi

# NODE DEPENDENCIES

echo ""
echo "[8/11] Installing Node.js dependencies..."
if [ -f "package.json" ]; then
    npm install
    echo "Node.js dependencies installed"
else
    echo "package.json not found. Skipping npm install..."
fi

# PYQT5 SETUP

echo ""
echo "[9/11] Setting up PyQt5 for Desktop Application..."
if [ -d "desktop/venv" ]; then
    echo "Desktop virtual environment already exists. Skipping..."
else
    if [ -d "desktop" ]; then
        cd desktop
        python3 -m venv venv
        
        if [ "$OS_NAME" = "Windows" ]; then
            call venv\Scripts\activate.bat
        else
            source venv/bin/activate
        fi
        
        pip install --upgrade pip setuptools wheel > /dev/null 2>&1
        
        if [ -f "requirements.txt" ]; then
            pip install -r requirements.txt
        else
            cat > requirements.txt << 'EOF'
PyQt5==5.15.9
PyQt5-sip==12.13.0

requests==2.31.0

pandas==2.1.2

python-dotenv==1.0.0
EOF
            pip install -r requirements.txt
        fi
        
        echo "PyQt5 environment configured"
        cd ..
    else
        echo "desktop directory not found. Skipping PyQt5 setup..."
    fi
fi

# DIRECTORY STRUCTURE

echo ""
echo "[10/11] Creating project directory structure..."

# Create necessary directories
mkdir -p backend/app/{api,models,schemas,services,utils,core,migrations}
mkdir -p frontend/{components,pages,public/assets,styles,utils,context}
mkdir -p desktop/ui
mkdir -p shared/constants
mkdir -p logs
mkdir -p uploads/{products,estimates,documents,avatars}

# Create assets directory for logo
mkdir -p public/assets

echo "Directory structure created"

# DATABASE SETUP

echo ""
echo "[11/11] Database Setup Instructions..."

echo ""
echo "PostgreSQL Setup:"
echo "1. Install PostgreSQL if not already installed"
echo "2. Create database and user:"
echo ""
echo "   psql -U postgres"
echo "   CREATE USER woodful_user WITH PASSWORD 'your-secure-password';"
echo "   CREATE DATABASE woodful_creations OWNER woodful_user;"
echo "   ALTER ROLE woodful_user CREATEDB;"
echo ""
echo "3. Update DATABASE_URL in backend/.env with your credentials"
echo "4. Run migrations (once backend is set up):"
echo "   cd backend"
echo "   alembic upgrade head"
echo ""

# SETUP SUMMARY

echo ""
echo "======================================"
echo "WOODFUL CREATIONS SETUP COMPLETE"
echo "======================================"
echo ""

echo "PROJECT MODULES:"
echo "  Stock Inventory Management"
echo "  Cost Estimates and PDF Generation"
echo "  Employee Attendance and Salary Management"
echo "  Interview Tracking"
echo "  Client Management Portal"
echo "  Payment Management (Admin Only)"
echo "  AI Chat Features"
echo "  Advanced Analytics"
echo "  Alert System"
echo ""

echo "CONFIGURATION FILES CREATED:"
echo "  backend/.env (FastAPI configuration)"
echo "  backend/.env.example (reference template)"
echo "  .env.local (frontend configuration)"
echo "  .env.example (frontend reference)"
echo ""

echo "MASTER USERS (ADMIN ACCESS):"
echo "  Email: nikhil@woodful.com (Nikhil)"
echo "  Email: garima@woodful.com (Garima)"
echo ""

echo "NEXT STEPS:"
echo ""
echo "1. Configure Backend:"
echo "   Edit backend/.env with your actual values"
echo "   Set up PostgreSQL database (see instructions above)"
echo "   Configure SMTP for email alerts"
echo "   Add OpenAI API key for AI features"
if [ "$OS_NAME" = "Windows" ]; then
    echo "   notepad backend\.env"
else
    echo "   nano backend/.env"
fi
echo ""
echo "2. Add Assets:"
echo "   Place Woodful logo in public/assets/woodful_logo.png"
echo "   Update PDF_LOGO_PATH in backend/.env if needed"
echo ""
echo "3. Start Backend (FastAPI):"
echo "   cd backend"
if [ "$OS_NAME" = "Windows" ]; then
    echo "   venv\Scripts\activate"
else
    echo "   source venv/bin/activate"
fi
echo "   uvicorn app.main:app --reload"
echo ""
echo "4. Start Frontend (React):"
echo "   npm run dev"
echo ""
echo "5. (Optional) Start Desktop App (PyQt5):"
echo "   cd desktop"
if [ "$OS_NAME" = "Windows" ]; then
    echo "   venv\Scripts\activate"
else
    echo "   source venv/bin/activate"
fi
echo "   python main.py"
echo ""
echo "6. Access the Application:"
echo "   Web Frontend: http://localhost:3000"
echo "   FastAPI Backend: http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo "   API ReDoc: http://localhost:8000/redoc"
echo ""

echo "DOCUMENTATION:"
echo "  See README.md for project overview"
echo "  See SETUP_GUIDE.md for detailed setup instructions"
echo "  See API_DOCUMENTATION.md for API endpoints"
echo "  See MODULES.md for feature details"
echo ""

echo "SECURITY REMINDERS:"
echo "  Change SECRET_KEY in backend/.env"
echo "  Use strong database passwords"
echo "  Never commit .env files to version control"
echo "  Enable HTTPS in production"
echo "  Keep API keys secure"
echo ""

echo "Happy coding!"
echo ""
