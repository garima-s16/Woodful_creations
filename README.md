WOODFUL STOCK INVENTORY MANAGEMENT SYSTEM

Quick Start Guide

Welcome to Woodful Stock Inventory, an AI-powered stock inventory management system built with Next.js, Python FastAPI, LangChain, and PostgreSQL. Works on Windows, macOS, iOS, and Android.

WHAT IS THIS SYSTEM?

Woodful Stock Inventory is a complete solution for managing warehouse stock with real-time tracking, intelligent forecasting, and AI-powered automation. The system helps you:

- Track inventory levels in real-time
- Get alerts when stock runs low
- Forecast demand using AI
- Automate reordering processes
- Export data to Excel for analysis
- Access inventory from any device (computer, phone, tablet)
- Chat with AI to manage inventory using natural language

SYSTEM ARCHITECTURE

The system consists of three main parts:

Frontend (Next.js)
- Web interface for managing inventory
- Real-time charts and dashboards
- Mobile-responsive design works on all devices
- Progressive Web App - works offline

Backend (Python FastAPI)
- REST API for all operations
- Database management
- Authentication and security
- Email notifications

Database (SQLite/PostgreSQL)
- Stores all inventory data
- User accounts and permissions
- Activity logs and audit trails

SUPPORTED PLATFORMS

Desktop:
- Windows 10, 11, and later
- macOS 10.13 and later
- Linux (Ubuntu, CentOS, etc.)

Mobile:
- iPhone (iOS 13+) - Safari browser
- iPad (iOS 13+) - Safari browser
- Android phones (Android 8+) - Chrome/Firefox browser
- Android tablets (Android 8+) - Chrome/Firefox browser

REQUIREMENTS

For Desktop Setup:
- Python 3.9 or higher
- Node.js 16 or higher
- npm (comes with Node.js)
- Git for version control
- 2GB free disk space
- Internet connection

For Mobile Access:
- iOS 13+ or Android 8+
- Chrome, Safari, Firefox, or Edge browser
- WiFi connection to computer running the app

QUICK START (5 MINUTES)

Step 1: Install Required Software

Windows:
1. Download Python from https://www.python.org/downloads/
2. During installation, check "Add Python to PATH"
3. Download Node.js from https://nodejs.org/
4. Run both installers using default settings
5. Restart your computer

macOS:
1. Download Python from https://www.python.org/downloads/
2. Download Node.js from https://nodejs.org/
3. Run both installers
4. Or use Homebrew: brew install python@3.10 node

Step 2: Clone Repository

Windows (Command Prompt):
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations

macOS (Terminal):
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations

Step 3: Run Setup Script

Windows or macOS:
bash scripts/setup.sh

Wait 5-10 minutes for setup to complete.

Step 4: Configure Environment

Edit backend/.env file:

Windows: notepad backend\.env
macOS: nano backend/.env

Update these values:
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-16-char-app-password
OPENAI_API_KEY=sk-your-api-key
BUSINESS_OWNER_EMAIL=owner@example.com

Step 5: Start Backend

Windows:
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload

macOS:
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

Step 6: Start Frontend (new terminal)

Windows:
cd frontend
npm run dev

macOS:
cd frontend
npm run dev

Step 7: Open in Browser

Desktop: http://localhost:3000

From Phone (same WiFi):
1. Find your computer IP address:
   Windows: Command Prompt, type ipconfig
   macOS: Terminal, type ifconfig
2. On phone browser: http://YOUR-IP:3000

GETTING STARTED

Create Account:
1. Click "Create Account"
2. Enter email, username, password
3. Password: 12+ chars, uppercase, number, special character
4. Click "Sign Up"

Complete Profile:
1. Click profile icon
2. Select "Settings"
3. Add business details
4. Click "Save"

Add Inventory:
1. Click "Inventory"
2. Click "Add Item"
3. Fill details
4. Click "Create"

View Dashboard:
1. Click "Dashboard"
2. See real-time overview

Test Chat:
1. Click "Chat"
2. Try: "Show all items" or "Add 50 units"

FEATURES

Dashboard
Real-time stock overview with visual charts and key metrics. See stock levels at a glance from any device.

Inventory Management
Complete control with add, edit, delete, search, filter. Bulk operations and barcode scanning supported.

AI Chat Interface
Talk to your system using natural language. Commands like "Show low stock items" are understood and executed.

Reports
Generate custom reports with Excel and PDF export. Schedule automatic reports and receive via email.

Notifications
Receive alerts when stock falls below minimum. Email notifications for critical events.

Audit Logs
Complete record of all system activity. Track who did what and when for compliance.

Mobile Access
Access from iPhone, iPad, Android phones and tablets. Same features as desktop. Works offline.

CONFIGURATION

Email Setup (Gmail):

1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and your device type
3. Copy the 16-character password
4. Add to backend/.env:
   EMAIL_USER=your-email@gmail.com
   EMAIL_PASSWORD=16-char-password

OpenAI API Setup:

1. Go to https://platform.openai.com/account/api-keys
2. Create new secret key
3. Add to backend/.env:
   OPENAI_API_KEY=sk-your-key

Business Owner Email:
BUSINESS_OWNER_EMAIL=owner@example.com

Secret Key (Windows):
python -c "import secrets; print(secrets.token_urlsafe(32))"

Secret Key (macOS):
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

Copy output and add:
SECRET_KEY=generated-key

MOBILE ACCESS

iPhone / iPad:

1. Find your computer IP:
   Windows: Command Prompt, ipconfig
   macOS: Terminal, ifconfig

2. On Safari, go to: http://YOUR-IP:3000
   Example: http://192.168.1.100:3000

3. Bookmark for quick access

4. Install as app (optional):
   Tap Share > Add to Home Screen > Add

Android:

1. Find your computer IP (same steps as above)

2. On Chrome, go to: http://YOUR-IP:3000

3. Bookmark for quick access

4. Install as app (optional):
   Tap Menu > Install app > Install

DEVELOPMENT

Local Setup:

Terminal 1 (Backend):
cd backend
source venv/bin/activate (macOS)
venv\Scripts\activate (Windows)
uvicorn app.main:app --reload

Terminal 2 (Frontend):
cd frontend
npm run dev

Access: http://localhost:3000

Production Deployment:

Frontend - Vercel:
1. Push to GitHub
2. Go to vercel.com
3. Import repository
4. Set frontend as root
5. Deploy

Backend - AWS:
pip install awsebcli
cd backend
eb init -p python-3.10
eb create production
eb deploy

TROUBLESHOOTING

Port Already in Use:

Windows:
npm run dev -- -p 3001
Then access: http://localhost:3001

macOS:
npm run dev -- -p 3001
Then access: http://localhost:3001

Python Not Found:

Windows: Reinstall Python and restart computer
macOS: Use python3 instead of python

Backend Won't Start:

Windows: Check port 8000 not in use
macOS: Check port 8000 not in use

Email Not Sending:

- Verify EMAIL_USER correct
- Check EMAIL_PASSWORD is 16-char app password
- Verify BUSINESS_OWNER_EMAIL set
- Wait 30 seconds

Cannot Connect Backend:

- Check backend running: http://localhost:8000/health
- Verify NEXT_PUBLIC_API_URL in .env.local
- Check firewall not blocking port 8000

Mobile Can't Connect:

- Both devices on same WiFi
- Use computer IP:3000 on phone
- Check backend running
- Check firewall

Database Error:

Windows:
cd backend
del stock_inventory.db

macOS:
cd backend
rm stock_inventory.db

SECURITY

Use Strong Passwords:
- 12+ characters
- Uppercase, numbers, special characters
- Change regularly

Keep Secrets Safe:
- Never commit .env files
- Keep API keys secure
- Don't share login credentials

Regular Backups:
- Backup database regularly
- Test restore procedures

FILE STRUCTURE

Woodful_creations/
├── backend/              (Python FastAPI)
│   ├── app/
│   ├── venv/
│   ├── .env
│   └── requirements.txt
├── frontend/            (Next.js)
│   ├── app/
│   ├── components/
│   ├── .env.local
│   └── package.json
├── scripts/
│   └── setup.sh
├── docs/
├── README.md
└── SETUP_GUIDE.md

VERSION INFORMATION

Woodful Stock Inventory v1.0.0
Built with Next.js 15, FastAPI, LangChain, PostgreSQL
Supports: Windows, macOS, iOS, Android
Last Updated: June 2026

SUPPORT

Documentation: See SETUP_GUIDE.md for detailed setup
API Docs: http://localhost:8000/docs (when running)
GitHub Issues: Create issue for bugs or features
Email Support: Contact project maintainers

Ready to get started? Follow SETUP_GUIDE.md for step-by-step instructions.
