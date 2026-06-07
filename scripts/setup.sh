#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "Woodful Stock Inventory Setup Script"
echo "======================================"
echo ""

# Check Python installation
echo -e "${GREEN}[1/7] Checking Python installation...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if (( PYTHON_MAJOR > 3 )) || (( PYTHON_MAJOR == 3 && PYTHON_MINOR >= 9 )); then
        echo -e "${GREEN}✓ Python $PYTHON_VERSION found (required: 3.9+)${NC}"
    else
        echo -e "${RED}✗ Python version $PYTHON_VERSION is too old. Please install Python 3.9 or higher.${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Python 3 is not installed. Please install Python 3.9 or higher.${NC}"
    exit 1
fi

# Check Node.js installation
echo -e "\n${GREEN}[2/7] Checking Node.js installation...${NC}"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓ Node.js $NODE_VERSION found${NC}"
else
    echo -e "${RED}✗ Node.js is not installed. Please install Node.js 16 or higher.${NC}"
    exit 1
fi

# Check npm installation
echo -e "\n${GREEN}[3/7] Checking npm installation...${NC}"
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✓ npm $NPM_VERSION found${NC}"
else
    echo -e "${RED}✗ npm is not installed. Please install npm.${NC}"
    exit 1
fi

# Create Python virtual environment
echo -e "\n${GREEN}[4/7] Creating Python virtual environment...${NC}"
if [ -d "backend/venv" ]; then
    echo -e "${YELLOW}⚠ Virtual environment already exists. Skipping...${NC}"
else
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment created${NC}"
    
    # Install Python dependencies
    echo -e "\n${GREEN}Installing Python dependencies...${NC}"
    pip install --upgrade pip setuptools wheel > /dev/null 2>&1
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        echo -e "${GREEN}✓ Python dependencies installed${NC}"
    else
        echo -e "${YELLOW}⚠ requirements.txt not found. Skipping pip install...${NC}"
    fi
    
    cd ..
fi

# Create backend configuration files
echo -e "\n${GREEN}[5/7] Creating backend configuration files...${NC}"

# Create .env file if it doesn't exist
if [ ! -f "backend/.env" ]; then
    cat > backend/.env << 'EOF'
# ==========================================
# Woodful Stock Inventory - Backend Configuration
# ==========================================

# Database Configuration
# Options: sqlite, postgresql
DATABASE_URL=sqlite:///./stock_inventory.db
# For PostgreSQL: postgresql://user:password@localhost:5432/woodful_inventory

# Security Configuration
SECRET_KEY=your-secret-key-change-this-in-production-use-32-chars-minimum
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Environment
DEBUG=False
ENVIRONMENT=development

# AI/LLM Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here
LANGCHAIN_API_KEY=your-langchain-api-key-here
LANGCHAIN_PROJECT=woodful-inventory

# Server Configuration
HOST=0.0.0.0
PORT=8000
RELOAD=true

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000

# Email Configuration (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=noreply@woodful.com

# Logging
LOG_LEVEL=INFO

# Stock Inventory Settings
MAX_REORDER_LEVEL=1000
MIN_STOCK_ALERT_THRESHOLD=10
FORECAST_DAYS=30
EOF
    echo -e "${GREEN}✓ backend/.env created${NC}"
else
    echo -e "${YELLOW}⚠ backend/.env already exists. Skipping...${NC}"
fi

# Create .env.example for reference
if [ ! -f "backend/.env.example" ]; then
    cat > backend/.env.example << 'EOF'
# ==========================================
# Woodful Stock Inventory - Backend Configuration
# Copy this file to .env and update the values
# ==========================================

# Database Configuration
# Options: sqlite, postgresql
DATABASE_URL=sqlite:///./stock_inventory.db

# Security Configuration
SECRET_KEY=your-secret-key-change-this-in-production-use-32-chars-minimum
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Environment
DEBUG=False
ENVIRONMENT=development

# AI/LLM Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here
LANGCHAIN_API_KEY=your-langchain-api-key-here
LANGCHAIN_PROJECT=woodful-inventory

# Server Configuration
HOST=0.0.0.0
PORT=8000
RELOAD=true

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000

# Email Configuration (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=noreply@woodful.com

# Logging
LOG_LEVEL=INFO

# Stock Inventory Settings
MAX_REORDER_LEVEL=1000
MIN_STOCK_ALERT_THRESHOLD=10
FORECAST_DAYS=30
EOF
    echo -e "${GREEN}✓ backend/.env.example created${NC}"
else
    echo -e "${YELLOW}⚠ backend/.env.example already exists. Skipping...${NC}"
fi

# Create frontend configuration
echo -e "\n${GREEN}[6/7] Creating frontend configuration files...${NC}"

if [ ! -f ".env.local" ]; then
    cat > .env.local << 'EOF'
# Frontend Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Woodful Stock Inventory
EOF
    echo -e "${GREEN}✓ .env.local created${NC}"
else
    echo -e "${YELLOW}⚠ .env.local already exists. Skipping...${NC}"
fi

if [ ! -f ".env.example" ]; then
    cat > .env.example << 'EOF'
# Frontend Configuration - Copy to .env.local and update values
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Woodful Stock Inventory
EOF
    echo -e "${GREEN}✓ .env.example created${NC}"
else
    echo -e "${YELLOW}⚠ .env.example already exists. Skipping...${NC}"
fi

# Install Node.js dependencies
echo -e "\n${GREEN}[7/7] Installing Node.js dependencies...${NC}"
if [ -f "package.json" ]; then
    npm install
    echo -e "${GREEN}✓ Node.js dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ package.json not found. Skipping npm install...${NC}"
fi

# Summary
echo -e "\n${GREEN}======================================"
echo "✓ Setup Complete!"
echo "======================================${NC}"
echo ""
echo -e "${YELLOW}Configuration Files Created:${NC}"
echo "  • backend/.env (main configuration)"
echo "  • backend/.env.example (reference template)"
echo "  • .env.local (frontend configuration)"
echo "  • .env.example (frontend reference template)"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Edit backend/.env with your actual configuration:"
echo "     nano backend/.env"
echo ""
echo "  2. Update these values:"
echo "     • SECRET_KEY (generate a secure key)"
echo "     • OPENAI_API_KEY (if using OpenAI)"
echo "     • LANGCHAIN_API_KEY (if using LangChain)"
echo "     • DATABASE_URL (if using PostgreSQL)"
echo ""
echo "  3. Start the backend:"
echo "     cd backend"
echo "     source venv/bin/activate"
echo "     uvicorn app.main:app --reload"
echo ""
echo "  4. Start the frontend (in another terminal):"
echo "     npm run dev"
echo ""
echo "  5. Access the application:"
echo "     Frontend: http://localhost:3000"
echo "     Backend API: http://localhost:8000"
echo "     API Docs: http://localhost:8000/docs"
echo ""
echo -e "${GREEN}For more information, see README.md${NC}"
