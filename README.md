WOODFUL STOCK INVENTORY MANAGEMENT SYSTEM

Quick Start Guide

Welcome to Woodful Stock Inventory, an AI-powered stock inventory management system built with Next.js, Python FastAPI, LangChain, and PostgreSQL.

WHAT IS THIS SYSTEM?

Woodful Stock Inventory is a complete solution for managing your warehouse stock with real-time tracking, intelligent forecasting, and AI-powered automation. The system helps you:

- Track inventory levels in real-time
- Get alerts when stock runs low
- Forecast demand using AI
- Automate reordering processes
- Export data to Excel for analysis
- Access inventory from mobile devices
- Chat with AI to manage inventory using natural language

SYSTEM ARCHITECTURE

The system consists of three main parts:

Frontend (Next.js)
- Web interface for managing inventory
- Real-time charts and dashboards
- Mobile-responsive design
- Progressive Web App support

Backend (Python FastAPI)
- REST API for all operations
- Database management
- Authentication and security
- Email notifications

Database (SQLite/PostgreSQL)
- Stores all inventory data
- User accounts and permissions
- Activity logs and audit trails

REQUIREMENTS

Before installation, you need:
- Python 3.9 or higher
- Node.js 16 or higher
- npm (comes with Node.js)
- Git for version control
- Gmail account (for email alerts)
- OpenAI API key (for AI features, optional but recommended)

QUICK START (5 MINUTES)

1. Clone Repository
git clone https://github.com/garima-s16/Woodful-stock-inventory.git
cd Woodful-stock-inventory

2. Run Setup Script
bash scripts/setup.sh

3. Configure Environment
cd backend
nano .env

Update these values:
EMAIL_USER=your-gmail@gmail.com
EMAIL_PASSWORD=your-16-char-app-password
OPENAI_API_KEY=sk-your-api-key
BUSINESS_OWNER_EMAIL=owner@example.com
SECRET_KEY=your-secure-key

4. Start Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

5. Start Frontend (in another terminal)
cd frontend
npm run dev

6. Open Browser
Frontend: http://localhost:3000
API Docs: http://localhost:8000/docs

GETTING STARTED (10 MINUTES)

Create Account
- Click "Create Account"
- Enter email, username, and password
- Password must have 12+ characters, uppercase, number, and special character
- Click "Sign Up"

Complete Profile
- Click profile icon
- Select "Settings"
- Add business name, location, and warehouse details
- Click "Save"

Add Inventory Item
- Click "Inventory"
- Click "Add Item"
- Fill details and click "Create"

View Dashboard
- Click "Dashboard"
- See inventory overview and charts

Test Chat
- Click "Chat"
- Try: "Show all items" or "Add 50 units of Oak Wood"

MAIN FEATURES

Dashboard
Real-time overview with visual charts and key metrics. See stock levels at a glance.

Inventory Management
Complete control with add, edit, delete, search, filter, and bulk operations support.

AI Chat Interface
Talk to your system using natural language. System understands inventory commands.

Reports
Custom reports with Excel and PDF export. Schedule automatic reports with email delivery.

Notifications
Receive alerts for low stock. Email notifications for critical events.

Audit Logs
Complete record of all system activity for compliance and troubleshooting.

CONFIGURATION SETUP

Email Setup (Gmail)

1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Windows Computer"
3. Copy the 16-character password
4. Add to backend/.env:
   EMAIL_USER=your-email@gmail.com
   EMAIL_PASSWORD=the-16-char-password

OpenAI API Setup

1. Go to https://platform.openai.com
2. Generate API key
3. Add to backend/.env:
   OPENAI_API_KEY=sk-your-key

Business Owner Email
BUSINESS_OWNER_EMAIL=owner@example.com

Secret Key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

Copy output and add to backend/.env:
SECRET_KEY=generated-key

DETAILED DOCUMENTATION

For step-by-step setup instructions, see SETUP_GUIDE.md

For feature details and requirements, see docs/REQUIREMENTS.md

For deployment instructions, see docs/DEPLOYMENT.md

DEVELOPMENT

Local Development

Terminal 1 - Backend:
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

Terminal 2 - Frontend:
cd frontend
npm run dev

Access at http://localhost:3000

Production Deployment

Frontend - Deploy to Vercel
1. Push to GitHub
2. Go to vercel.com
3. Import repository
4. Set frontend as root directory
5. Add environment variables
6. Deploy

Backend - Deploy to AWS
pip install awsebcli
cd backend
eb init -p python-3.10
eb create production
eb deploy

TROUBLESHOOTING

Port Already in Use
lsof -ti:3000 | xargs kill -9
Or use different port: npm run dev -- -p 3001

Database Error
cd backend
rm stock_inventory.db
python3 -c "from app.database import init_db; init_db()"

Module Not Found
pip install -r requirements.txt
npm install

Email Not Sending
- Verify EMAIL_USER and EMAIL_PASSWORD in .env
- Check app password is 16 characters
- Allow 30 seconds for delivery

Cannot Connect to Backend
- Check http://localhost:8000/health
- Verify NEXT_PUBLIC_API_URL in .env.local
- Check port 8000 is not blocked

SECURITY TIPS

Use Strong Passwords
Minimum 12 characters with uppercase, numbers, and special characters.

Keep Secrets Safe
Never commit .env files. Keep API keys secure.

Enable Email Verification
Verify new accounts via email.

Regular Backups
Backup database regularly. Test recovery procedures.

Update Dependencies
Keep packages and modules updated for security.

FILE STRUCTURE

Woodful-stock-inventory/
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
Built with Next.js 15, FastAPI, LangChain, and PostgreSQL
Last Updated: June 2026

SUPPORT

Documentation: See SETUP_GUIDE.md for detailed setup help
API Docs: http://localhost:8000/docs (when running locally)
GitHub Issues: Create issue in repository
Email Support: Contact project maintainers

Ready to get started? Follow the SETUP_GUIDE.md for step-by-step instructions.
