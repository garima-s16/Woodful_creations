SETUP GUIDE - Woodful Stock Inventory Management System

This guide walks you through setting up the Woodful Stock Inventory system on your local machine.

PREREQUISITES

Before starting, ensure you have installed:
- Python 3.9 or higher
- Node.js 16 or higher
- Git
- A text editor (VS Code, Sublime, etc.)

STEP 1: CLONE REPOSITORY

Open your terminal and run:

git clone https://github.com/garima-s16/Woodful-stock-inventory.git
cd Woodful-stock-inventory

STEP 2: RUN AUTOMATED SETUP

This script will check Python and Node.js installation, create virtual environment, install all dependencies, initialize SQLite database, and create configuration files.

bash scripts/setup.sh

Wait for the script to complete. This may take 5-10 minutes depending on your internet speed.

STEP 3: CONFIGURE ENVIRONMENT

Backend Configuration

The setup script creates a backend/.env file with default values. You need to update it with your actual configuration.

cd backend
nano .env

Or if you prefer a graphical editor:
- On macOS: open -a TextEdit .env
- On Windows: notepad .env
- On Linux: gedit .env

Configure Gmail Email Setup for Alerts

To enable email alerts for low stock items:

1. Go to https://myaccount.google.com/apppasswords
2. Sign in with your Gmail account
3. Select "Mail" and "Windows Computer" (or your device type)
4. Google generates a 16-character password
5. Copy the entire password (without spaces)
6. Update in .env:
   EMAIL_USER=your-email@gmail.com
   EMAIL_PASSWORD=paste-the-16-char-password-here

Configure OpenAI API for AI Chat Features

1. Go to https://platform.openai.com/account/api-keys
2. Click "Create new secret key"
3. Copy the API key
4. Update in .env:
   OPENAI_API_KEY=sk-your-api-key-here

Configure Business Owner Email

Update the email address that receives system alerts:

BUSINESS_OWNER_EMAIL=owner@example.com

Generate Secure Secret Key

For production, generate a secure secret key:

python3 -c "import secrets; print(secrets.token_urlsafe(32))"

Copy the output and update in .env:

SECRET_KEY=paste-generated-key-here

Frontend Configuration

Navigate to the frontend directory and configure environment variables:

cd ../frontend
nano .env.local

Add the following (or update if already present):

NEXT_PUBLIC_API_URL=http://localhost:8000

Save the file (Ctrl+X, then Y, then Enter in nano).

STEP 4: VERIFY INSTALLATION

Check if everything is installed correctly:

python3 --version
node --version
npm --version
ls -la backend/venv/

You should see version numbers for each command.

STEP 5: ACCESS THE WEBSITE

Option 1: Local Development (Recommended for Testing)

You will need two terminal windows running simultaneously.

Terminal 1 - Start Backend

cd backend
source venv/bin/activate

On Windows use: venv\Scripts\activate

uvicorn app.main:app --reload

Expected output:
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete

Terminal 2 - Start Frontend

Open a new terminal window in the project root directory:

cd frontend
npm run dev

Expected output:
▲ Next.js 15.0.0
- Local:        http://localhost:3000
- Environments: .env.local

Then open your browser and visit:
Frontend: http://localhost:3000
API Documentation: http://localhost:8000/docs

Option 2: Production Deployment

Deploy Frontend to Vercel

1. Push your code to GitHub
2. Go to https://vercel.com
3. Click "Import Project"
4. Select your repository
5. Set "frontend" as the root directory
6. Add environment variables from .env.example
7. Click "Deploy"

Your app will be live at: https://your-project.vercel.app

Deploy Backend to AWS Elastic Beanstalk

pip install awsebcli
cd backend
eb init -p python-3.10
eb create production
eb deploy

Your API will be at: https://your-api.elasticbeanstalk.com

STEP 6: FIRST LOGIN

Create Account

1. Open http://localhost:3000 in your browser
2. Click "Create Account" button
3. Fill in the registration form:
   Email: your@email.com
   Username: yourname
   Full Name: Your Full Name
   Password: MySecurePassword123!
   Confirm Password: MySecurePassword123!

Password Requirements:
- Minimum 12 characters
- At least 1 uppercase letter (A-Z)
- At least 1 number (0-9)
- At least 1 special character (!@$%^&*)

4. Click "Sign Up"
5. You will be logged in automatically

Verify Your Account

Check your email for a verification link:
- Click the link in the email
- Your account is now verified

Complete Profile

1. Click your profile icon in the top right corner
2. Select "Settings"
3. Add the following information:
   - Business name
   - Location
   - Warehouse details
4. Click "Save"

STEP 7: FIRST ACTIONS

Add Your First Inventory Item

1. Click "Inventory" in the navigation menu
2. Click "Add Item" button
3. Fill in the form:
   SKU: WD-001
   Item Name: Oak Wood Board
   Category: Wood
   Quantity: 100
   Min Stock: 10
   Max Stock: 500
   Unit Price: 25.99
   Warehouse: Main
4. Click "Create"
5. The item appears in your inventory list

View Dashboard

1. Click "Dashboard" in the navigation menu
2. You will see:
   - Stock overview cards
   - Charts showing inventory levels
   - Recent activity
   - Alerts and notifications

Test Chat Interface

1. Click "Chat" in the navigation menu
2. Try these commands:
   "Add 50 units of Oak Wood"
   "Show low stock items"
   "What is the total inventory value?"
   "Recommend restocking"

Export to Excel

1. Go to "Inventory"
2. Click "Export to Excel"
3. File downloads to your computer
4. Open in Excel or Google Sheets

STEP 8: MOBILE ACCESS

Web App (Progressive Web App)

1. Open http://localhost:3000 on your mobile phone
2. Open the browser menu and select "Install app" or "Add to Home Screen"
3. The app appears on your home screen
4. Works offline with cached data

Native Mobile App

1. Install Capacitor:
   npm install -g @capacitor/cli
   cd frontend
   npx cap add ios
   npx cap add android

2. For iOS:
   npx cap open ios
   This opens Xcode. Click the Play button to run the simulator.

3. For Android:
   npx cap open android
   This opens Android Studio. Click the Play button to run the emulator.

STEP 9: CUSTOMIZE APPEARANCE

Dark Mode

1. Click your profile icon in the top right corner
2. Click "Settings"
3. Toggle "Dark Mode"
4. The interface switches to dark theme

Change Theme Colors

Edit frontend/tailwind.config.js:

colors: {
  'woodful': {
    'dark': '6B4423',
    'light': 'A0826D',
    'beige': 'D4C4B0',
  }
}

TROUBLESHOOTING

Port Already in Use

Kill process on port 3000:
lsof -ti:3000 | xargs kill -9

Or use a different port:
npm run dev -- -p 3001

Database Connection Error

Reinitialize the database:
cd backend
rm stock_inventory.db
python3 -c "from app.database import init_db; init_db()"

Module Not Found

Install dependencies again:
cd backend
pip install -r requirements.txt

cd ../frontend
npm install

Email Not Sending

Verify the following:
- EMAIL_USER is your correct Gmail address
- EMAIL_PASSWORD is the 16-character app password (not your Gmail password)
- BUSINESS_OWNER_EMAIL is set to a valid email
- Allow 30 seconds for the email to be delivered

Cannot Connect to Backend

1. Verify the backend is running by visiting: http://localhost:8000/health
2. Check NEXT_PUBLIC_API_URL in .env.local matches your backend URL
3. Check firewall settings are not blocking port 8000

FEATURE TOUR

Dashboard
- Real-time stock levels
- Beautiful charts and graphs
- Key performance indicator cards
- Recent activity log

Inventory Management
- Add, edit, and delete items
- Search and filter functionality
- Bulk operations
- Barcode scanning support

Chat Interface
- AI-powered commands
- Natural language input
- Instant responses
- Chat history

Reports
- Custom report builder
- Export to Excel and PDF
- Scheduled reports
- Email delivery

Notifications
- Low stock alerts
- Email notifications
- In-app popups
- Notification center

Audit Logs
- Complete activity history
- User actions tracked
- Timestamp logging
- Compliance ready

SECURITY TIPS

Password Security
- Use 12 or more character passwords
- Use strong, unique passwords
- Change your password regularly

Session Management
- Logout when you are done using the application
- Do not share login credentials
- Use "Remember Me" only on personal devices

Data Backup
- Download and backup your SQLite database regularly
- Keep backups in multiple secure locations
- Test restore procedures periodically

QUICK START COMMAND

Copy and run this entire command to get started quickly:

git clone https://github.com/garima-s16/Woodful-stock-inventory.git && \
cd Woodful-stock-inventory && \
bash scripts/setup.sh && \
echo "Setup complete!" && \
echo "Backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload" && \
echo "Frontend: cd frontend && npm run dev" && \
echo "Then open: http://localhost:3000"

NEED HELP?

Setup Issues: See docs/SETUP_GUIDE.md
Feature Questions: See docs/REQUIREMENTS.md
Deployment Help: See docs/DEPLOYMENT.md
API Documentation: Visit http://localhost:8000/docs
Still Need Help: Create a GitHub issue in the repository

Version: 1.0.0
Last Updated: June 2026
