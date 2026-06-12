SETUP GUIDE - Woodful Stock Inventory Management System

This guide walks you through setting up the Woodful Stock Inventory system on Windows, macOS, Android, or iPhone.

SYSTEM REQUIREMENTS

Minimum Requirements for Desktop:
- Python 3.9 or higher
- Node.js 16 or higher
- Git for version control
- 2GB free disk space
- Internet connection

For Mobile Access:
- iOS 13+ or Android 8+
- Chrome, Safari, Firefox, or Edge browser

STEP 1: DOWNLOAD AND SETUP

Windows Users:

1. Install Python
   - Visit https://www.python.org/downloads/
   - Download Python 3.10 or higher
   - During installation, check "Add Python to PATH"
   - Click Install Now

2. Install Node.js
   - Visit https://nodejs.org/en/download/
   - Download LTS version
   - Run the installer and follow defaults
   - Restart your computer after installation

3. Install Git
   - Visit https://git-scm.com/download/win
   - Download and run installer
   - Use default settings

4. Open Command Prompt or PowerShell
   - Press Windows + R
   - Type cmd or powershell
   - Press Enter

macOS Users:

1. Install Python
   - Visit https://www.python.org/downloads/
   - Download Python 3.10 or higher
   - Run the installer
   - Follow the installation steps

2. Install Node.js
   - Visit https://nodejs.org/en/download/
   - Download macOS Installer
   - Run and follow installation steps

3. Install Git
   - Visit https://git-scm.com/download/mac
   - Download and run installer
   - Or use Homebrew: brew install git

4. Open Terminal
   - Press Command + Space
   - Type Terminal
   - Press Enter

STEP 2: CLONE REPOSITORY

Windows (Command Prompt or PowerShell):
git clone https://github.com/garima-s16/Woodful-stock-inventory.git
cd Woodful-stock-inventory

macOS (Terminal):
git clone https://github.com/garima-s16/Woodful-stock-inventory.git
cd Woodful-stock-inventory

STEP 3: RUN AUTOMATED SETUP

The setup script will automatically:
- Check Python and Node.js installation
- Create Python virtual environment
- Install all dependencies
- Create configuration files

Windows:
cd /c/Automation_Files/Woodful-stock-inventory
bash scripts/setup.sh

Git bash:
cd /c/Automation_Files/Woodful-stock-inventory
chmod +x scripts/setup.sh
./scripts/setup.sh

Or if bash is not available:
python scripts/setup.sh

macOS:
bash scripts/setup.sh

Wait for completion. This takes 5-10 minutes depending on internet speed.

STEP 4: CONFIGURE ENVIRONMENT

Backend Configuration

Edit backend/.env file with your settings:

Windows:
- Option 1: notepad backend\.env
- Option 2: Use VS Code: Open folder Woodful-stock-inventory in VS Code, then edit backend\.env

macOS:
- Option 1: nano backend/.env
- Option 2: Use VS Code: Open folder in VS Code, then edit backend/.env

Required Configuration:

EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-16-char-app-password
OPENAI_API_KEY=sk-your-api-key-here
BUSINESS_OWNER_EMAIL=owner@example.com
SECRET_KEY=your-secure-key

Setup Gmail for Alerts:

1. Go to https://myaccount.google.com/apppasswords
2. Sign in with your Gmail account
3. Select App: Mail
4. Select Device: Windows Computer (or your device)
5. Google generates a 16-character password
6. Copy the password
7. Paste into backend/.env:
   EMAIL_PASSWORD=your-16-char-password

Setup OpenAI API:

1. Visit https://platform.openai.com/account/api-keys
2. Click Create new secret key
3. Copy your API key
4. Paste into backend/.env:
   OPENAI_API_KEY=sk-your-api-key

Generate Secret Key:

Windows Command Prompt:
python -c "import secrets; print(secrets.token_urlsafe(32))"

macOS Terminal:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

Copy the output and update SECRET_KEY in backend/.env

Frontend Configuration:

Windows (notepad):
notepad .env.local

macOS (nano):
nano .env.local

Add this line:
NEXT_PUBLIC_API_URL=http://localhost:8000

Save and exit.

STEP 5: START THE APPLICATION

You need two terminal windows running simultaneously.

Windows - Terminal 1 (Backend):

cd backend

create virtual environment:
python -m venv venv

Then verify: 
dir venv

You should see:
Include
Lib
Scripts
pyvenv.cfg

.\venv\Scripts\Activate.ps1
pip install uvicorn fastapi
uvicorn app.main:app --reload

Expected output:
INFO:     Uvicorn running on http://127.0.0.1:8000
Press Ctrl+C to stop

Windows - Terminal 2 (Frontend):

Open new Command Prompt window
cd Woodful-stock-inventory
cd frontend
npm run dev

Expected output:
Local:        http://localhost:3000
Press Ctrl+C to stop

macOS - Terminal 1 (Backend):

cd backend
source venv/bin/activate
pip install uvicorn fastapi
uvicorn app.main:app --reload

Expected output:
INFO:     Uvicorn running on http://127.0.0.1:8000
Press Ctrl+C to stop

macOS - Terminal 2 (Frontend):

Open new Terminal window
cd Woodful-stock-inventory
cd frontend
npm run dev

Expected output:
Local:        http://localhost:3000
Press Ctrl+C to stop

STEP 6: OPEN IN BROWSER

On your computer:
- Frontend: http://localhost:3000
- API Documentation: http://localhost:8000/docs

STEP 7: CREATE ACCOUNT

1. Open http://localhost:3000
2. Click Create Account
3. Fill in:
   Email: your-email@gmail.com
   Username: yourname
   Full Name: Your Full Name
   Password: MySecurePassword123! (12+ chars, uppercase, number, special character)
4. Click Sign Up
5. Verify your email when prompted

STEP 8: COMPLETE PROFILE

1. Click your profile icon (top right)
2. Click Settings
3. Enter:
   - Business name
   - Location
   - Warehouse details
4. Click Save

STEP 9: ADD FIRST INVENTORY ITEM

1. Click Inventory
2. Click Add Item
3. Fill in:
   SKU: WD-001
   Item Name: Oak Wood Board
   Category: Wood
   Quantity: 100
   Min Stock: 10
   Unit Price: 25.99
4. Click Create

STEP 10: ACCESS FROM MOBILE

iPhone / iPad:

1. On your computer, find your local IP address:
   Windows: Open Command Prompt, type: ipconfig
   Look for IPv4 Address (usually 192.168.x.x or 10.x.x.x)
   
   macOS: Open Terminal, type: ifconfig
   Look for inet address (usually 192.168.x.x)

2. On your iPhone/iPad Safari:
   http://YOUR-IP-ADDRESS:3000
   Example: http://192.168.1.100:3000

3. Bookmark the page for quick access

4. Optional - Install as app:
   - Tap Share
   - Tap Add to Home Screen
   - Tap Add
   - App appears on home screen

Android Phone / Tablet:

1. On your computer, find your local IP address:
   Windows: Open Command Prompt, type: ipconfig
   macOS: Open Terminal, type: ifconfig

2. On Android Chrome browser:
   http://YOUR-IP-ADDRESS:3000
   Example: http://192.168.1.100:3000

3. Bookmark the page for quick access

4. Optional - Install as app:
   - Tap Menu (three dots)
   - Tap Install app
   - Tap Install
   - App appears on home screen

MOBILE APP FEATURES:

Works on both iPhone and Android:
- Full inventory management
- Real-time charts
- Chat interface
- Export data
- Works offline with cached data
- Responsive design fits any screen

TROUBLESHOOTING

Port Already in Use

Windows:
- Change port in Terminal 2:
  npm run dev -- -p 3001
- Then access: http://localhost:3001

macOS:
- Change port in Terminal 2:
  npm run dev -- -p 3001
- Then access: http://localhost:3001

Python Not Found

Windows:
- Make sure Python is installed and added to PATH
- Restart Command Prompt after installing Python
- Try: python --version

macOS:
- Try: python3 --version
- If not working, install Python from https://www.python.org

Backend Won't Start

Windows:
- Check if another app is using port 8000
- Try: netstat -ano | findstr :8000
- Kill the process: taskkill /PID <PID> /F
- Then start backend again

macOS:
- Check if another app is using port 8000
- Try: lsof -ti:8000
- Kill process: kill -9 <PID>
- Then start backend again

Email Not Sending

- Verify EMAIL_USER and EMAIL_PASSWORD are correct
- Make sure EMAIL_PASSWORD is 16-character app password (not Gmail password)
- Check BUSINESS_OWNER_EMAIL is valid
- Wait 30 seconds for email delivery
- Check spam folder

Cannot Access From Phone

- Both devices must be on same WiFi network
- Get your computer IP: Windows (ipconfig) or macOS (ifconfig)
- Use IP:3000 on phone browser
- Make sure backend is running on computer
- Check firewall isn't blocking port 3000

Database Error

Windows:
cd backend
del stock_inventory.db
python -c "from app.database import init_db; init_db()"

macOS:
cd backend
rm stock_inventory.db
python3 -c "from app.database import init_db; init_db()"

FEATURES

Dashboard
- Real-time stock overview
- Visual charts and graphs
- Key metrics cards
- Activity log

Inventory Management
- Add, edit, delete items
- Search and filter
- Bulk operations
- Barcode scanning

AI Chat
- Natural language commands
- Instant responses
- Chat history
- Smart suggestions

Reports
- Custom reports
- Export to Excel/PDF
- Scheduled delivery
- Email sharing

Notifications
- Low stock alerts
- Email notifications
- Push alerts
- Alert center

SECURITY

Password Tips:
- Use 12+ characters
- Mix uppercase, numbers, special characters
- Change regularly
- Don't share credentials

Data Protection:
- Backup database regularly
- Keep API keys secret
- Never commit .env files
- Enable email verification

STOP THE APPLICATION

Windows:
- In backend terminal: Press Ctrl+C
- In frontend terminal: Press Ctrl+C

macOS:
- In backend terminal: Press Ctrl+C
- In frontend terminal: Press Ctrl+C

RESTART THE APPLICATION

Windows - Terminal 1:
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload

Windows - Terminal 2:
cd frontend
npm run dev

macOS - Terminal 1:
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

macOS - Terminal 2:
cd frontend
npm run dev

PRODUCTION DEPLOYMENT

Deploy Frontend to Vercel:

1. Push code to GitHub
2. Go to https://vercel.com
3. Import repository
4. Set frontend as root directory
5. Add .env variables
6. Click Deploy

Deploy Backend to AWS:

1. Install AWS EB CLI
2. Configure AWS credentials
3. Run: eb init
4. Run: eb create production
5. Run: eb deploy

NEED HELP?

Common Issues: See section above
Feature Questions: GitHub Issues
API Documentation: http://localhost:8000/docs
Email Support: Contact maintainers

Version: 1.0.0
Supports: Windows, macOS, iOS, Android
Last Updated: June 2026
