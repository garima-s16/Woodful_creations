# Woodful Creations - Setup Guide

## Project Overview

Woodful Creations is a comprehensive business management application designed for woodcraft and furniture design businesses. It provides features for inventory management, cost estimation, employee tracking, client management, and advanced analytics.

### Technology Stack
- **Frontend**: React Native (Mobile & Desktop support)
- **Backend**: FastAPI (Python)
- **Desktop UI**: PyQt5
- **Database**: PostgreSQL
- **Additional**: AI chat features, file generation (PDF, Excel, Word), email notifications

### Key Features
1. Stock Inventory Management with AI alerts
2. Cost Estimation and PDF generation
3. Employee Attendance and Salary Management
4. Interview Tracking
5. Client Management with project tracking
6. Payment Management
7. Advanced Analytics
8. Multi-level Access Control (Master users: Nikhil & Garima)

---

## System Requirements

### Before You Start
Ensure your laptop has the following:
- **Operating System**: Windows 10/11, macOS, or Linux
- **Python**: Version 3.9 or higher
- **Node.js**: Version 14 or higher
- **PostgreSQL**: Version 12 or higher
- **RAM**: Minimum 8GB (16GB recommended)
- **Storage**: Minimum 5GB free space
- **Internet Connection**: Required for initial setup and email features

---

## Installation Steps

### Step 1: Clone the Repository

Open your terminal/command prompt and run:

```bash
git clone https://github.com/garima-s1611/Woodful_creations.git
cd Woodful_creations

Step 2: Set Up PostgreSQL Database
Windows/macOS/Linux:
Download and Install PostgreSQL from https://www.postgresql.org/download/

Create a new database:

psql -U postgres
CREATE DATABASE woodful_creations;
CREATE USER woodful_user WITH PASSWORD 'your_secure_password';
ALTER ROLE woodful_user SET client_encoding TO 'utf8';
ALTER ROLE woodful_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE woodful_user SET default_transaction_deferrable TO on;
ALTER ROLE woodful_user SET default_transaction_read_committed TO off;
GRANT ALL PRIVILEGES ON DATABASE woodful_creations TO woodful_user;
\q

Note down your credentials - you'll need them for configuration

Step 3: Set Up Backend (FastAPI)
3.1 Create Python Virtual Environment
bash
# Navigate to backend directory (if it exists)
cd backend
# or create it if needed

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

3.2 Install Python Dependencies
bash
pip install --upgrade pip
pip install fastapi uvicorn python-multipart
pip install psycopg2-binary sqlalchemy
pip install pydantic python-dotenv
pip install pydantic-settings
pip install pillow  # For image processing
pip install reportlab  # For PDF generation
pip install openpyxl  # For Excel generation
pip install python-docx  # For Word generation
pip install aiofiles
pip install python-jose[cryptography]  # For authentication
pip install passlib[bcrypt]  # For password hashing
pip install email-validator
pip install requests  # For API calls

Or install from requirements file if available:
pip install -r requirements.txt

3.3 Create Environment Configuration
Create a .env file in the backend directory:

env
# Database Configuration
DATABASE_URL=postgresql://woodful_user:your_secure_password@localhost:5432/woodful_creations

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=True

# Secret Key (generate a secure random string)
SECRET_KEY=your_very_secure_random_key_here

# Email Configuration (for notifications and client emails)
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
APP_VERSION=1.0.0


Step 4: Set Up Frontend (React Native)

4.1 Install Node.js Dependencies
bash
# Navigate to frontend directory
cd ../frontend
# or appropriate path

# Install dependencies
npm install
# or
yarn install

4.2 Environment Configuration for Frontend
Create a .env file in the frontend directory:

env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_API_TIMEOUT=30000
Step 5: Set Up PyQt5 Desktop Application (Optional)

5.1 Install PyQt5 Dependencies
In your Python virtual environment:

bash
pip install PyQt5
pip install PyQt5-sip

Running the Application
Option A: Development Mode
Terminal 1 - Start PostgreSQL (if not already running)
bash
# On Windows (if installed via installer, it usually runs as service)
# On macOS:
brew services start postgresql
# On Linux:
sudo systemctl start PostgreSQL

Terminal 2 - Start FastAPI Backend
bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn main:app --reload --host 0.0.0.0 --port 8000

Expected output:
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete

Terminal 3 - Start React Native Frontend
bash
cd frontend
npm start
# or
yarn start

For web version:
bash
npm run web
# or
yarn web

Terminal 4 - Start PyQt5 Desktop (if needed)
bash
cd desktop
python main.py

---
Option B: Production Mode
Refer to deployment documentation (to be created)

---

Accessing the Application
Web Interface
URL: http://localhost:3000
Default Master Users: Nikhil, Garima (configure during initial setup)

FastAPI Documentation
Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

Desktop Application
Launch PyQt5 application directly from Terminal 4

-----
Initial Setup Steps
1. Create Database Tables
Run migration scripts (to be created):

bash
python scripts/init_db.py

2. Create Master User Account
bash
python scripts/create_master_user.py \
  --name "Nikhil" \
  --email "nikhil@woodfulcreations.com" \
  --password "secure_password"
3. Configure Email Settings
Update SMTP credentials in .env for:

Low stock alerts to Nikhil/Garima
ETA reminders
Cost estimate PDFs to clients
Salary slip emails

4. Upload Logo
Place the Woodful Creations logo in:

frontend/public/assets/logo/woodful_logo.png
desktop/assets/logo/woodful_logo.png


Project Structure

Woodful_creations/
├── backend/
│   ├── venv/
│   ├── app/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routes/
│   │   ├── services/
│   │   └── database.py
│   ├── main.py
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.jsx
│   ├── package.json
│   └── .env
├── desktop/
│   ├── main.py
│   ├── ui/
│   └── requirements.txt
├── scripts/
│   ├── init_db.py
│   └── create_master_user.py
└── SETUP_GUIDE.md

-----

Troubleshooting
Issue: PostgreSQL Connection Error
Solution:

bash
# Check if PostgreSQL is running
# Windows: Check Services
# macOS: brew services list
# Linux: sudo systemctl status postgresql

# Verify credentials in .env file
# Make sure database user has correct permissions
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE woodful_creations TO woodful_user;"

Issue: FastAPI Port Already in Use
Solution:

bash
# Change port in command
uvicorn main:app --reload --host 0.0.0.0 --port 8001

# Or kill existing process on port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

Issue: Node.js Dependencies Error
Solution:

bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install

Issue: PyQt5 Import Error
Solution:

bash
# Reinstall PyQt5
pip uninstall PyQt5 -y
pip install PyQt5 --force-reinstall

-----
Testing the Application
Test Backend API
bash
curl http://localhost:8000/docs

Test Frontend Connection
Open browser console and check:

Network tab for API calls
No CORS errors

Test Database Connection
bash
python -c "import psycopg2; conn = psycopg2.connect('dbname=woodful_creations user=woodful_user password=<password>'); print('Connection successful')"

-----
Security Checklist
Before production deployment:

 Change all default passwords
 Generate secure SECRET_KEY
 Enable HTTPS
 Configure CORS properly
 Set up firewall rules
 Enable database backups
 Configure email authentication (App Password for Gmail)
 Set environment variables on server
 Enable user authentication tokens
 Set up role-based access control (Nikhil & Garima as master users)

-----
Next Steps
Create Master User Accounts for Nikhil and Garima
Configure Email Settings for alerts and notifications
Set Up Stock Inventory Module (Priority 1)
Design Database Schema for all modules
Implement Authentication System
Create API Endpoints for each module
Build UI Components in React Native
Set Up Testing Suite
Deploy to Staging Environment
User Acceptance Testing

-----
Support & Documentation
For additional help:

Check individual module documentation
Review FastAPI docs at http://localhost:8000/docs
Contact development team


Version History
v1.0.0 - Initial Setup Guide
Release Date - June 2026