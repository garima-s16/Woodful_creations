# Woodful Creations - Setup Guide

## System Requirements

### Before You Start
Ensure your system has the following:

| Requirement | Version | Notes |
|-------------|---------|-------|
| Operating System | Windows 10/11, macOS, or Linux | Tested on all platforms |
| Python | 3.9, 3.10, 3.11, 3.12, 3.13, or **3.14** | Recommended: 3.10+ |
| Node.js | 14 or higher (LTS versions preferred) | For frontend development |
| PostgreSQL | 12 or higher | For database |
| RAM | Minimum 8GB | 16GB recommended |
| Storage | Minimum 5GB free space | For all dependencies |
| Internet Connection | Required | For setup and email features |

---

## Installation Steps

### Step 1: Clone the Repository

Open your terminal/command prompt and run:

```bash
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations
```

---

### Step 2: Set Up PostgreSQL Database

#### Windows/macOS/Linux:
1. Download and install PostgreSQL from https://www.postgresql.org/download/
2. Run the installer and follow the setup wizard
3. Remember the password you set for the `postgres` superuser

#### Create Database and User:

Open your terminal/command prompt and run:

```bash
psql -U postgres
```

Then execute these SQL commands:

```sql
CREATE DATABASE woodful_creations;
CREATE USER woodful_user WITH PASSWORD 'your_secure_password';
ALTER ROLE woodful_user SET client_encoding TO 'utf8';
ALTER ROLE woodful_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE woodful_user SET default_transaction_deferrable TO on;
ALTER ROLE woodful_user SET default_transaction_read_committed TO off;
GRANT ALL PRIVILEGES ON DATABASE woodful_creations TO woodful_user;
\q
```

**Important**: Note down your database credentials (username, password, database name). You'll need them in the .env configuration.

---

### Step 3: Set Up Backend (FastAPI with Python 3.14 Support)

#### 3.1 Verify Python Version

First, ensure you have a compatible Python version:

```bash
python --version
# or
python3 --version
```

Output should show: Python 3.9 or higher (3.14 is fully supported)

**Note**: If you have multiple Python versions, you may need to use `python3.14` or `python3.10` specifically.

#### 3.2 Create Python Virtual Environment

Navigate to the project root and create a virtual environment:

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (Python 3.14 compatible)
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

You should see `(venv)` at the start of your command prompt.

#### 3.3 Upgrade pip and Install Dependencies

With the virtual environment activated:

```bash
# Upgrade pip to latest version (important for Python 3.14)
pip install --upgrade pip setuptools wheel

# Install core dependencies
pip install fastapi==0.104.1
pip install uvicorn[standard]==0.24.0
pip install sqlalchemy==2.0.23
pip install psycopg2-binary==2.9.9
pip install pydantic==2.5.0
pip install pydantic-settings==2.1.0
pip install python-multipart==0.0.6
pip install python-dotenv==1.0.0

# Install file generation dependencies
pip install reportlab==4.0.7
pip install openpyxl==3.11.0
pip install python-docx==0.8.11

# Install image processing
pip install pillow==10.1.0

# Install authentication & security
pip install python-jose[cryptography]==3.3.0
pip install passlib[bcrypt]==1.7.4
pip install cryptography==41.0.7
pip install email-validator==2.1.0

# Install API client
pip install requests==2.31.0

# Install async file support
pip install aiofiles==23.2.1

# Install OpenAI for AI features
pip install openai==1.3.0
pip install langchain==0.1.0
```

**Alternative**: Install from requirements.txt if available:

```bash
pip install -r requirements.txt
```

#### 3.4 Create Backend Environment Configuration

Create a `.env` file in the `backend` directory:

```bash
# On Windows:
type nul > .env

# On macOS/Linux:
touch .env
```

Edit the `.env` file and add:

```env
# Database Configuration
DATABASE_URL=postgresql://woodful_user:your_secure_password@localhost:5432/woodful_creations

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=True

# Secret Key (generate a secure random string - use: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY=your_very_secure_random_key_here_minimum_32_characters

# Email Configuration (for notifications)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password
SENDER_NAME=Woodful Creations

# JWT Configuration
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application Settings
APP_NAME=Woodful Creations
APP_VERSION=2.0.0

# OpenAI Configuration (for AI features)
OPENAI_API_KEY=your_openai_api_key_here
```

**Important**: Replace placeholder values with your actual credentials.

---

### Step 4: Set Up Frontend (React)

#### 4.1 Install Node.js Dependencies

In a new terminal, navigate to the frontend directory:

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install
# or if you prefer yarn:
yarn install
```

This will install all React dependencies from `package.json`.

#### 4.2 Create Frontend Environment Configuration

Create a `.env` file in the `frontend` directory:

```bash
# On Windows:
type nul > .env

# On macOS/Linux:
touch .env
```

Edit the `.env` file and add:

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_API_TIMEOUT=30000
REACT_APP_APP_NAME=Woodful Creations
REACT_APP_VERSION=2.0.0
```

---

### Step 5: Set Up PyQt5 Desktop Application (Optional)

If you plan to use the desktop application:

#### 5.1 Install PyQt5 Dependencies

With the Python virtual environment activated in the backend:

```bash
# Ensure you're in the backend directory with venv activated
pip install PyQt5==5.15.9
pip install PyQt5-sip==12.13.0
```

---

## Running the Application

### Option A: Development Mode

Use multiple terminal windows to run all services simultaneously:

#### Terminal 1 - Start PostgreSQL

```bash
# On Windows (if installed as service):
# PostgreSQL usually starts automatically
# Check Services > PostgreSQL

# On macOS:
brew services start postgresql

# On Linux:
sudo systemctl start postgresql
```

#### Terminal 2 - Start FastAPI Backend

```bash
# Navigate to backend
cd backend

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

#### Terminal 3 - Start React Frontend

```bash
# Navigate to frontend
cd frontend

# Start the development server
npm start
# or
yarn start
```

The browser should automatically open at `http://localhost:3000`.

#### Terminal 4 - Start PyQt5 Desktop (if needed)

```bash
# Navigate to desktop directory
cd desktop

# Ensure backend virtual environment is activated
python main.py
```

### Option B: Using Shell/Batch Scripts

For convenience, use the provided startup scripts:

```bash
# Start all services at once
# On macOS/Linux:
./start_all.sh

# On Windows:
start_all.bat
```

### Option C: Using Docker (Recommended for Production)

If Docker is installed:

```bash
# Navigate to project root
cd Woodful_creations

# Start all services with Docker
docker-compose up

# Run in background
docker-compose up -d
```

---

## Accessing the Application

Once all services are running:

### Web Interface
- **URL**: http://localhost:3000
- **Default Master Users**: Nikhil, Garima
- **Password**: Set during initial setup

### Backend API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **API Base URL**: http://localhost:8000

### Desktop Application
- Launch directly from Terminal 4 output

### Database Connection
- **Host**: localhost
- **Port**: 5432
- **Database**: woodful_creations
- **User**: woodful_user

---

## Initial Database Setup

### Create Database Tables

If migration scripts are available:

```bash
# In the backend directory with venv activated
python scripts/init_db.py
```

### Create Master User Account

```bash
python scripts/create_master_user.py \
  --name "Nikhil" \
  --email "nikhil@woodfulcreations.com" \
  --password "secure_password"

python scripts/create_master_user.py \
  --name "Garima" \
  --email "garima@woodfulcreations.com" \
  --password "secure_password"
```

---

## Configuration Guide

### Email Setup (Gmail)

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password:
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer" (or your device)
   - Copy the generated 16-character password
3. Add to `.env`:
   ```env
   SENDER_EMAIL=your_email@gmail.com
   SENDER_PASSWORD=your_16_character_app_password
   ```

### OpenAI API Key Setup

1. Sign up at https://platform.openai.com
2. Navigate to API keys section
3. Create a new API key
4. Add to `.env`:
   ```env
   OPENAI_API_KEY=sk-your_api_key_here
   ```

### JWT Secret Key Generation

Generate a secure random key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output and add to `.env` as `SECRET_KEY`.

---

## Troubleshooting

### Issue: PostgreSQL Connection Error

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
```bash
# Check if PostgreSQL is running
# Windows: Check Services panel
# macOS: brew services list
# Linux: sudo systemctl status postgresql

# Verify credentials in .env file
# Test connection:
psql -U woodful_user -d woodful_creations -h localhost

# If permission error, reset permissions:
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE woodful_creations TO woodful_user;"
```

### Issue: FastAPI Port Already in Use

**Error**: `Address already in use`

**Solution**:
```bash
# Use a different port
uvicorn main:app --reload --host 0.0.0.0 --port 8001

# Or kill the existing process
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux:
lsof -i :8000
kill -9 <PID>
```

### Issue: Python Module Not Found (Python 3.14)

**Error**: `ModuleNotFoundError: No module named 'xyz'`

**Solution**:
```bash
# Ensure you're in the correct virtual environment
# Check which Python:
which python

# Reinstall dependencies with Python 3.14 compatibility
pip install --upgrade --force-reinstall pip setuptools wheel
pip install -r requirements.txt
```

### Issue: Node.js Dependencies Error

**Error**: `npm ERR!` or missing modules

**Solution**:
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### Issue: PyQt5 Import Error

**Error**: `ModuleNotFoundError: No module named 'PyQt5'`

**Solution**:
```bash
# Reinstall PyQt5
pip uninstall PyQt5 -y
pip install PyQt5 --force-reinstall
```

---

## Testing the Application

### Test Backend API

```bash
# Check API documentation
curl http://localhost:8000/docs

# Test a health check endpoint (if available)
curl http://localhost:8000/api/health
```

### Test Frontend Connection

1. Open http://localhost:3000 in your browser
2. Open Developer Tools (F12)
3. Check Network tab for API calls
4. Look for any CORS errors in the Console

### Test Database Connection

```bash
python -c "import psycopg2; conn = psycopg2.connect('dbname=woodful_creations user=woodful_user password=your_password host=localhost'); print('Connection successful'); conn.close()"
```

---

## Python 3.14 Specific Notes

### Compatibility
- All listed dependencies are fully compatible with Python 3.14
- If you encounter issues, ensure you're using the latest pip: `pip install --upgrade pip`

### Virtual Environment
- Virtual environments work seamlessly with Python 3.14
- If issues arise, delete and recreate: `rm -rf venv` then `python -m venv venv`

### Performance
- Python 3.14 may show improved performance compared to earlier versions
- No code changes are required for Python 3.14 compatibility

---

## Security Checklist

Before any production deployment:

- [ ] Change all default passwords
- [ ] Generate secure SECRET_KEY
- [ ] Configure HTTPS/SSL certificates
- [ ] Set up firewall rules
- [ ] Enable database backups
- [ ] Configure email authentication properly
- [ ] Set environment variables on server (not in .env file)
- [ ] Enable CORS only for trusted domains
- [ ] Set DEBUG=False in production
- [ ] Implement rate limiting
- [ ] Set up monitoring and logging
- [ ] Regular security audits

---

## Next Steps

1. **Create Master User Accounts** for Nikhil and Garima
2. **Configure Email Settings** for alerts and notifications
3. **Set Up Stock Inventory Module** (Priority 1)
4. **Implement AI Chat Feature** (Priority 2)
5. **Build Authentication System** (Priority 3)
6. **Create API Endpoints** for remaining modules
7. **Build UI Components** in React
8. **Set Up Testing Suite**
9. **Deploy to Staging Environment**
10. **User Acceptance Testing**
11. **Production Deployment**

---

## Support & Resources

### Documentation
- **PROJECT_INFO.md** - Comprehensive project overview
- **FastAPI Docs** - http://localhost:8000/docs
- **React Documentation** - https://react.dev
- **PostgreSQL Docs** - https://www.postgresql.org/docs/

### Community & Support
- Python Package Issues: Check requirements.txt versions
- FastAPI Issues: https://github.com/tiangolo/fastapi
- React Issues: https://github.com/facebook/react

---

## Version Information

| Component | Version | Date Updated |
|-----------|---------|---------------|
| Setup Guide | 2.0.0 | June 2026 |
| Python Support | 3.9 - 3.14 | June 2026 |
| FastAPI | 0.104.1 | June 2026 |
| React | 18.2.0 | June 2026 |
| PostgreSQL | 12+ | June 2026 |

---

*Last Updated: June 2026*  
*Maintained by: Woodful Creations Development Team*
