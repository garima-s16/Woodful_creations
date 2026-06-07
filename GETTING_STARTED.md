WOODFUL STOCK INVENTORY - GET STARTED GUIDE

Step-by-Step Access Instructions

Welcome to Woodful Inventory Management System! Follow these simple steps to start using the platform.

---

TABLE OF CONTENTS

1. [System Requirements](system-requirements)
2. [Initial Setup](initial-setup)
3. [Access the Website](access-the-website)
4. [First Login](first-login)
5. [Troubleshooting](troubleshooting)

---

SYSTEM REQUIREMENTS

 For Desktop (Windows/Mac/Linux)
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Internet connection
- No software installation needed!

 For Mobile (iOS/Android)
- Latest iOS or Android device
- Web browser or Woodful app
- Optional: Install as PWA app

---

INITIAL SETUP (First Time Only)

 Step 1: Clone Repository
```bash
git clone https://github.com/garima-s16/Woodful-stock-inventory.git
cd Woodful-stock-inventory
```

 Step 2: Run Automated Setup
```bash
bash scripts/setup.sh
```

This script will:
-  Check Python and Node.js installation
-  Create virtual environment
-  Install all dependencies
-  Initialize SQLite database
-  Create configuration files

Step 3: Configure Environment

 Backend Configuration
```bash
 Edit backend/.env file
cd backend
nano .env
```

Add these settings:
```env
 Gmail Email Setup (for alerts)
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

OpenAI API (for AI chat features)
OPENAI_API_KEY=sk-your-api-key

Business Owner Email (receives alerts)
BUSINESS_OWNER_EMAIL=owner@example.com

 Security
SECRET_KEY=your-secure-random-key
```

Get Gmail App Password:
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Windows Computer"
3. Google generates a 16-character password
4. Copy and paste into EMAIL_PASSWORD

 Frontend Configuration
```bash
cd ../frontend
nano .env.local
```

Add:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

ACCESS THE WEBSITE

Option 1: Local Development (Recommended for Testing)

Terminal 1 - Start Backend:
```bash
cd backend
source venv/bin/activate     On Windows: venv\Scripts\activate
uvicorn app.main:app --reload
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

Terminal 2 - Start Frontend:
```bash
cd frontend
npm run dev
```

Expected output:
```
  ▲ Next.js 15.0.0
  - Local:        http://localhost:3000
```

Then Open in Browser:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

---

Option 2: Production Deployment

Deploy Frontend to Vercel
1. Push code to GitHub
2. Go to https://vercel.com
3. Click "Import Project"
4. Select your repository
5. Set "frontend" as root directory
6. Add environment variables
7. Click "Deploy"

Your app will be live at: `https://your-project.vercel.app`

Deploy Backend to AWS
```bash
pip install awsebcli
cd backend
eb init -p python-3.10
eb create production
eb deploy
```

Your API will be at: `https://your-api.elasticbeanstalk.com`

---

FIRST LOGIN

Step 1: Create Account

1. Open http://localhost:3000 in your browser
2. Click "Create Account" button
3. Fill in the registration form:

```
Email:              your@email.com
Username:           yourname
Full Name:          Your Full Name
Password:           MySecurePassword123!  (12+ characters required)
Confirm Password:   MySecurePassword123!
```

Password Requirements:
- Minimum 12 characters
- At least 1 uppercase letter (A-Z)
- At least 1 number (0-9)
- At least 1 special character (!@$%^&*)

4. Click "Sign Up"
5. You'll be logged in automatically 

 Step 2: Verify Your Account

Check your email for a verification link (if enabled):
- Click the link in the email
- Your account is now verified

 Step 3: Complete Profile

1. Click your profile icon (top right)
2. Select "Settings"
3. Add:
   - Business name
   - Location
   - Warehouse details
4. Click "Save"

---

FIRST ACTIONS

 1. Add Your First Inventory Item

1. Click "Inventory" in navigation
2. Click "Add Item" button
3. Fill in the form:
   ```
   SKU:              WD-001
   Item Name:        Oak Wood Board
   Category:         Wood
   Quantity:         100
   Min Stock:        10
   Max Stock:        500
   Unit Price:       25.99
   Warehouse:        Main
   ```
4. Click "Create"
5. Item appears in inventory list 

 2. View Dashboard

1. Click "Dashboard" in navigation
2. You'll see:
   - Stock overview cards
   - Charts showing inventory levels
   - Recent activity
   - Alerts and notifications

 3. Test Chat Interface

1. Click "Chat" in navigation
2. Try these commands:
   ```
   "Add 50 units of Oak Wood"
   "Show low stock items"
   "What's the total inventory value?"
   "Recommend restocking"
   ```

 4. Export to Excel

1. Go to "Inventory"
2. Click "Export to Excel"
3. File downloads to your computer
4. Open in Excel/Google Sheets

---

MOBILE ACCESS

 Web App (PWA)

1. Open http://localhost:3000 on mobile
2. Browser menu → "Install app" or "Add to Home Screen"
3. App appears on home screen
4. Works offline with cached data!

 Native Mobile App

1. Install Capacitor:
   ```bash
   npm install -g @capacitor/cli
   cd frontend
   npx cap add ios
   npx cap add android
   ```

2. For iOS:
   ```bash
   npx cap open ios
    Opens Xcode
    Click Play button to run simulator
   ```

3. For Android:
   ```bash
   npx cap open android
    Opens Android Studio
    Click Play button to run emulator
   ```

---

CUSTOMIZE APPEARANCE

 Dark Mode

1. Click user profile icon (top right)
2. Click "Settings"
3. Toggle "Dark Mode"
4. Interface switches to dark theme

 Change Theme Colors

Edit `frontend/tailwind.config.js`:
```js
colors: {
  'woodful': {
    'dark': '6B4423',      // Your brand color
    'light': 'A0826D',
    'beige': 'D4C4B0',
  }
}
```

---

TROUBLESHOOTING

 "Port Already in Use"
```bash
 Kill process on port 3000
lsof -ti:3000 | xargs kill -9

 Or use different port
npm run dev -- -p 3001
```

 "Database Connection Error"
```bash
 Reinitialize database
cd backend
rm woodful.db
python3 -c "from app.database import db; print('Done')"
```

 "Module Not Found"
```bash
cd backend
pip install -r requirements.txt

cd ../frontend
npm install
```

 "Email Not Sending"
- Verify EMAIL_USER is correct
- Check EMAIL_PASSWORD (16-char app password)
- Verify BUSINESS_OWNER_EMAIL is set
- Allow 30 seconds for delivery

 "Can't Connect to Backend"
- Verify backend is running: `http://localhost:8000/health`
- Check NEXT_PUBLIC_API_URL in .env.local
- Check firewall isn't blocking port 8000

---

FEATURE TOUR

 Dashboard
- Real-time stock levels
- Beautiful charts
- KPI cards
- Recent activity log

 Inventory Management
- Add/edit/delete items
- Search and filter
- Bulk operations
- Barcode scanning

 Chat Interface
- AI-powered commands
- Natural language input
- Instant responses
- Chat history

 Reports
- Custom report builder
- Export to Excel/PDF
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

---

SECURITY TIPS

1. Password Security:
   - Use 12+ character passwords
   - Use strong, unique passwords
   - Change password regularly

2. Session Management:
   - Logout when done
   - Don't share login credentials
   - Use "Remember Me" only on personal devices

3. Data Backup:
   - Download SQLite database regularly
   - Keep backups in multiple locations
   - Test restore procedures

---

CHECKLIST - YOU'RE READY!

- [ ] Repository cloned
- [ ] Setup script run
- [ ] Environment files configured
- [ ] Backend running on localhost:8000
- [ ] Frontend running on localhost:3000
- [ ] Created account
- [ ] Added first inventory item
- [ ] Viewed dashboard
- [ ] Tested chat feature
- [ ] Exported to Excel
- [ ] Installed mobile app

---

NEED HELP?

1. Setup Issues? → See `docs/SETUP_GUIDE.md`
2. How to Use Features? → See `docs/REQUIREMENTS.md`
3. Deployment Help? → See `docs/DEPLOYMENT.md`
4. API Questions? → Check `http://localhost:8000/docs`
5. Still Stuck? → Create GitHub issue

---

QUICK START COMMAND

Copy and run this command:

```bash
git clone https://github.com/garima-s16/Woodful-stock-inventory.git && \
cd Woodful-stock-inventory && \
bash scripts/setup.sh && \
echo " Setup complete!" && \
echo "Backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload" && \
echo "Frontend: cd frontend && npm run dev" && \
echo "Then open: http://localhost:3000"
```

---

Version: 1.0.0
Last Updated: June 2026
