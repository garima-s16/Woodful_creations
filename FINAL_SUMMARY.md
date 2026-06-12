WOODFUL STOCK INVENTORY

Core Features
- SQLite Database
- JWT Authentication
- Email Alerts
- Chat Interface
- Stock Dashboard
- Excel Export and Import
- Mobile Ready
- Pop-up Alerts - Low stock notifications
- Testing - Robot Framework with Selenium
- Real-time WebSocket updates
- Barcode/QR scanner
- GPS tracking
- Dark/Light mode
- Audit logging
- Role-based access
- Custom reports
- Activity timeline
- Notification center
- Keyboard shortcuts

---

QUICK START

```bash
 1. Clone
git clone https://github.com/garima-s16/Woodful_creations.git
cd Woodful_creations

 2. Setup (automatic)
bash scripts/setup.sh

 3. Configure
 Edit backend/.env and frontend/.env.local

 4. Run backend (Terminal 1)
cd backend && source venv/bin/activate
uvicorn app.main:app --reload

 5. Run frontend (Terminal 2)
cd frontend && npm run dev

 6. Open browser
 http://localhost:3000
```

---

FILES CREATED

```
 backend/
   ├── requirements.txt (all dependencies)
   ├── .env.example (configuration template)
   ├── app/
   │   ├── database.py (SQLite wrapper)
   │   ├── routes/auth.py (JWT + 12+ char passwords)
   │   └── services/
   │       ├── email_service.py (email alerts)
   │       └── export_service.py (Excel/CSV)
   └── Dockerfile

 frontend/
   ├── package.json (all dependencies)
   ├── .env.example (config template)
   ├── capacitor.config.json (mobile)
   ├── tailwind.config.ts
   ├── tsconfig.json
   └── Dockerfile

 database/
   └── schema.sql (15+ tables, all indexes)

 tests/
   ├── robot/ (API + UI tests)
   └── pytest/ (backend tests)

 docs/
   ├── REQUIREMENTS.md
   ├── IMPLEMENTATION_GUIDE.md
   ├── SETUP_GUIDE.md
   ├── ROBOT_FRAMEWORK_GUIDE.md
   └── DEPLOYMENT.md

 scripts/
   ├── setup.sh (automatic setup)
   ├── run_robot_tests.sh (test runner)
   └── generate_robot_report.sh (report generator)

 docker-compose.yml (full stack)
 .github/workflows/ci-cd.yml (GitHub Actions)
 PROJECT_SUMMARY.md (THIS FILE)
```

---

SECURITY

 JWT token-based authentication
 12+ character password requirement (enforced)
 Bcrypt password hashing
 SQLite with foreign keys
 CORS protection
 SQL injection prevention (ORM)
 Rate limiting ready
 Audit logging

---

NEXT STEPS

 Step 1: Environment Setup
```bash
 Copy example configs
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

 Edit backend/.env
 EMAIL_USER=your-email@gmail.com
 EMAIL_PASSWORD=google-app-password
 OPENAI_API_KEY=sk-your-key
 BUSINESS_OWNER_EMAIL=owner@example.com
```

 Step 2: Generate Secure Key
```bash
 Generate JWT secret
openssl rand -hex 32
 Copy output to backend/.env as SECRET_KEY
```

 Step 3: Get Gmail App Password
1. Go to https://myaccount.google.com/apppasswords
2. Generate app password for "Mail"
3. Copy password to EMAIL_PASSWORD in .env

 Step 4: Run Everything
```bash
 Terminal 1: Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload

 Terminal 2: Frontend
cd frontend && npm run dev

 Open: http://localhost:3000
```

 Step 5: Test Features
- Create account (12+ char password)
- Create inventory items
- Check dashboard charts
- Try chat: "Add 50 units Oak"
- Test Excel export
- Verify low stock alert

---

MOBILE APP

 Web App (Works Now)
- Open http://localhost:3000 on mobile
- Install as app from browser menu
- Works offline with cached data

Native App (iOS/Android)
```bash
cd frontend
npm install -g @capacitor/cli
npm install @capacitor/core
npx cap add ios
npx cap add android
npx cap open ios      Opens Xcode
npx cap open android  Opens Android Studio
```

---

TESTING

```bash
 All tests
bash scripts/run_robot_tests.sh all

 API tests only
bash scripts/run_robot_tests.sh api

 UI tests only  
bash scripts/run_robot_tests.sh ui

 Smoke tests (fast)
bash scripts/run_robot_tests.sh smoke

 Generate report
bash scripts/generate_robot_report.sh
 Opens: results/report.html
```

---

DEPLOYMENT

 Frontend
```bash
cd frontend
npm run build
 Push to GitHub
git push origin main
 Vercel auto-deploys
```

 Backend
```bash
 Install AWS CLI
pip install awsebcli

cd backend
eb init -p python-3.10 woodful
eb create woodful-env
eb deploy

 Set environment variables
eb setenv DATABASE_URL=... OPENAI_API_KEY=...
```

---

| File | Purpose |
|------|---------|
| `docs/SETUP_GUIDE.md` | Installation steps |
| `docs/REQUIREMENTS.md` | Feature requirements |
| `docs/IMPLEMENTATION_GUIDE.md` | What's implemented |
| `docs/ROBOT_FRAMEWORK_GUIDE.md` | Testing guide |
| `docs/DEPLOYMENT.md` | Production deployment |
| `http://localhost:8000/docs` | Live API docs |

---
TROUBLESHOOTING

 Port Already in Use
```bash
 Kill process on port 3000
lsof -ti:3000 | xargs kill -9

 Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

 Database Issues
```bash
 Reinitialize database
cd backend
rm woodful.db
python3 -c "from app.database import db; print('Done')"
```

 Module Not Found
```bash
cd backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

 Email Not Sending
- Verify EMAIL_USER and EMAIL_PASSWORD in .env
- Check Gmail app password is correct
- Verify BUSINESS_OWNER_EMAIL is set
- Check firewall/network settings

---

SUPPORT

Questions? Check these first:

1. Setup Issues → `docs/SETUP_GUIDE.md`
2. API Questions → `http://localhost:8000/docs`
3. Testing Help → `docs/ROBOT_FRAMEWORK_GUIDE.md`
4. Deployment → `docs/DEPLOYMENT.md`
5. Common Issues → `docs/TROUBLESHOOTING.md`

---

One-Command Setup

Copy this entire command and run it:

```bash
git clone https://github.com/garima-s16/Woodful_creations.git && \
cd Woodful_creations && \
bash scripts/setup.sh && \
echo " Setup complete! Edit .env files then run:" && \
echo "Backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload" && \
echo "Frontend: cd frontend && npm run dev"
```
---

*Woodful Stock Inventory - AI-Powered Inventory Management*
*Version 1.0.0 | June 2026 | Production Ready*
