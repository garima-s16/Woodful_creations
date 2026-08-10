# Woodful Creations - Setup Guide

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

# Install from requirements.txt
pip install -r requirements.txt
```

**Python 3.14 Compatibility**: All dependencies in requirements.txt are tested and compatible with Python 3.14.

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

### Step 5: Initialize Database Schema

#### 5.1 Apply Database Schema

Run the schema initialization script:

```bash
# Navigate to scripts directory
cd ../scripts

# Initialize database
python init_db.py
```

This creates all necessary tables for:
- User management
- Stock inventory
- Client management
- Cost estimation
- Employee management
- Interview tracking
- Payment tracking
- Communication history

#### 5.2 Verify Database Tables

Check that tables were created:

```bash
psql -U woodful_user -d woodful_creations -c "\dt"
```

---

### Step 6: Create Master Users

Create the master administrator accounts and regular users:

```bash
# Create Master User 1 - Garima
python create_master_user.py \
  --username garimas \
  --name "Garima" \
  --email "garima@woodfulcreations.com" \
  --password "Gullak*16" \
  --phone "+919229083242" \
  --role admin

# Create Master User 2 - Nikhil
python create_master_user.py \
  --username nikhils \
  --name "Nikhil" \
  --email "nikhil@woodfulcreations.com" \
  --password "Nikhil*27" \
  --phone "9339555554" \
  --role admin

# Create Regular User - Shweta
python create_master_user.py \
  --username shwetav \
  --name "Shweta" \
  --email "shweta@woodfulcreations.com" \
  --password "Shweta*05" \
  --role user
```

---

### Step 7: Set Up PyQt5 Desktop Application (Optional)

If you plan to use the desktop application later:

```bash
# Ensure you're in the backend directory with venv activated
pip install PyQt5==5.15.9
pip install PyQt5-sip==12.13.0
```

---

## Running the Application - Development Mode

Use multiple terminal windows to run all services simultaneously:

### Terminal 1: Start PostgreSQL

```bash
# On Windows (if installed as service):
# PostgreSQL usually starts automatically
# Check Services > PostgreSQL

# On macOS:
brew services start postgresql

# On Linux:
sudo systemctl start postgresql
```

### Terminal 2: Start FastAPI Backend

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

### Terminal 3: Start React Frontend

```bash
# Navigate to frontend
cd frontend

# Start the development server
npm start
# or
yarn start
```

The browser should automatically open at `http://localhost:3000`.

### Terminal 4: Start PyQt5 Desktop (if needed)

```bash
# Navigate to desktop
cd desktop

# Ensure backend virtual environment is activated
python main.py
```

---

## Using Shell/Batch Scripts (Optional)

For convenience, use the provided startup scripts:

```bash
# Start all services at once
# On macOS/Linux:
./start_all.sh

# On Windows:
start_all.bat
```

---

## Using Docker (Recommended for Consistent Environment)

If Docker is installed:

```bash
# Navigate to project root
cd Woodful_creations

# Start all services with Docker
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## Accessing the Application

Once all services are running:

### Web Interface
- **URL**: http://localhost:3000
- **Default Master Users**:
  - Username: `garimas`, Password: `Gullak*16`
  - Username: `nikhils`, Password: `Nikhil*27`
- **Regular User**:
  - Username: `shwetav`, Password: `Shweta*05`

### Backend API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health

### Database Connection
- **Host**: localhost
- **Port**: 5432
- **Database**: woodful_creations
- **User**: woodful_user

---

## Local Environment Launch Verification

Follow the **LAUNCH_CHECKLIST.md** for comprehensive verification steps to ensure:
- All services are running correctly
- Database connection is established
- Master users are created
- Login functionality works
- API endpoints are accessible

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
pip install -r requirements.txt --force-reinstall
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

### Issue: Login Fails

**Error**: Authentication fails with correct credentials

**Solution**:
```bash
# Verify users exist in database
psql -U woodful_user -d woodful_creations -c "SELECT id, username, email, role FROM users;"

# Check that users were created successfully
# If not, recreate master users using create_master_user.py

# Clear browser cookies and try again
# Check backend logs for errors
```

---

## Testing the Application

### Test Backend API

```bash
# Check API documentation
curl http://localhost:8000/docs

# Test health check endpoint
curl http://localhost:8000/api/health

# Test login endpoint
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"garimas","password":"Gullak*16"}'
```

### Test Frontend Connection

1. Open http://localhost:3000 in your browser
2. Open Developer Tools (F12 or Right-click > Inspect)
3. Check Network tab for API calls
4. Look for any CORS errors in Console
5. Try logging in with master user credentials

### Test Database Connection

```bash
python -c "import psycopg2; conn = psycopg2.connect('dbname=woodful_creations user=woodful_user password=your_password host=localhost'); print('Connection successful'); conn.close()"
```

---

## Python 3.14 Specific Notes

### Compatibility
- All listed dependencies are fully compatible with Python 3.14
- If you encounter issues, ensure you're using the latest pip: `pip install --upgrade pip`
- Virtual environments work seamlessly with Python 3.14

### Performance
- Python 3.14 may show improved performance compared to earlier versions
- No code changes are required for Python 3.14 compatibility

---

## Security Checklist (Before Production)

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

1. Complete SETUP_GUIDE.md installation
2. Verify LAUNCH_CHECKLIST.md requirements
3. Launch website on local environment (http://localhost:3000)
4. Test login with master user credentials
5. Verify all API endpoints in Swagger documentation
6. Begin Phase 1: Stock Inventory Module development

---

## Support & Resources

### Documentation
- **PROJECT_INFO.md** - Comprehensive project overview and roadmap
- **LAUNCH_CHECKLIST.md** - Step-by-step local launch verification
- **FastAPI Docs** - http://localhost:8000/docs
- **React Documentation** - https://react.dev
- **PostgreSQL Docs** - https://www.postgresql.org/docs/

### Community & Support
- Python Package Issues: Check requirements.txt versions
- FastAPI Issues: https://github.com/tiangolo/fastapi
- React Issues: https://github.com/facebook/react
- Woodful Team: Nikhil (9339555554) or Garima (+919229083242)

---

## Version Information

| Component | Version | Date Updated |
|-----------|---------|---------------|
| Setup Guide | 2.0.0 | June 2026 |
| Python Support | 3.9 - 3.14 | June 2026 |
| FastAPI | 0.104.1 | June 2026 |
| React | 18.2.0 | June 2026 |
| PostgreSQL | 12+ | June 2026 |
| Node.js | 14+ | June 2026 |

---

*Last Updated: June 2026*
*Maintained by: Woodful Creations Development Team*
