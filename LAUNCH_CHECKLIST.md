# Woodful Creations - Local Environment Launch Checklist

This document provides a comprehensive verification checklist to ensure your Woodful Creations development environment is correctly set up and ready for local launch.

---

## Pre-Launch System Verification

### System Requirements Check
- [ ] Operating System: Windows 10/11, macOS, or Linux
- [ ] Python Version: 3.14 installed
  ```bash
  python --version
  ```
- [ ] Node.js Version: 14 or higher installed
  ```bash
  node --version
  npm --version
  ```
- [ ] PostgreSQL Version: 12 or higher installed
  ```bash
  psql --version
  ```
- [ ] RAM: Minimum 8GB available
- [ ] Storage: Minimum 5GB free space
- [ ] Internet Connection: Required for setup

---

## Database Setup Verification

- [ ] PostgreSQL Service Running
  - Windows: Check Services panel for "postgresql-x64"
  - macOS: `brew services list`
  - Linux: `sudo systemctl status postgresql`

- [ ] Database Created
  ```bash
  psql -U postgres -c "SELECT datname FROM pg_database WHERE datname='woodful_creations';"
  ```

- [ ] Database User Created
  ```bash
  psql -U postgres -c "SELECT usename FROM pg_user WHERE usename='woodful_user';"
  ```

- [ ] Database Connection Verified
  ```bash
  psql -U woodful_user -d woodful_creations -h localhost
  ```

- [ ] Database Tables Created
  ```bash
  psql -U woodful_user -d woodful_creations -c "\dt"
  ```

---

## Backend Setup Verification

- [ ] Repository Cloned
  ```bash
  git clone https://github.com/garima-s16/Woodful_creations.git
  cd Woodful_creations
  ```

- [ ] Navigate to Backend
  ```bash
  cd backend
  ```

- [ ] Virtual Environment Created
  ```bash
  ls -la venv/  # macOS/Linux
  dir venv     # Windows
  ```

- [ ] Virtual Environment Activated
  - Windows: `venv\Scripts\activate`
  - macOS/Linux: `source venv/bin/activate`
  - Indicator: `(venv)` prefix in terminal

- [ ] Pip Upgraded
  ```bash
  pip --version
  ```

- [ ] Dependencies Installed
  ```bash
  pip list | grep fastapi
  pip list | grep sqlalchemy
  ```

- [ ] Backend .env File Created
  ```bash
  ls -la .env  # macOS/Linux
  dir .env     # Windows
  ```

- [ ] Backend .env Configured with all variables:
  - [ ] DATABASE_URL set correctly
  - [ ] SERVER_HOST and SERVER_PORT configured
  - [ ] DEBUG set to True (for development)
  - [ ] SECRET_KEY generated (minimum 32 characters)
  - [ ] JWT_ALGORITHM set to HS256
  - [ ] ACCESS_TOKEN_EXPIRE_MINUTES set to 30
  - [ ] APP_NAME set to "Woodful Creations"
  - [ ] APP_VERSION set to "2.0.0"
  - [ ] OPENAI_API_KEY configured (if using AI features)
  - [ ] SMTP settings configured (for email features)

---

## Frontend Setup Verification

- [ ] Navigate to Frontend
  ```bash
  cd ../frontend
  ```

- [ ] Dependencies Installed
  ```bash
  ls -la node_modules/  # macOS/Linux
  dir node_modules      # Windows
  npm list react
  ```

- [ ] Frontend .env File Created
  ```bash
  ls -la .env  # macOS/Linux
  dir .env     # Windows
  ```

- [ ] Frontend .env Configured with:
  - [ ] REACT_APP_API_URL=http://localhost:8000
  - [ ] REACT_APP_API_TIMEOUT=30000
  - [ ] REACT_APP_APP_NAME=Woodful Creations
  - [ ] REACT_APP_VERSION=2.0.0

---

## Database Schema & Users Verification

- [ ] Database Schema Applied
  ```bash
  cd ../scripts
  python init_db.py
  ```

- [ ] Master User 1 (Garima) Created
  ```bash
  python create_master_user.py \
    --username garimas \
    --name "Garima" \
    --email "admin1@example.com" \
    --role admin
  ```

- [ ] Master User 2 (Nikhil) Created
  ```bash
  python create_master_user.py \
    --username nikhils \
    --name "Nikhil" \
    --email "admin2@example.com" \
    --role admin
  ```

- [ ] Regular User (Shweta) Created
  ```bash
  python create_master_user.py \
    --username shwetav \
    --name "Shweta" \
    --email "user@example.com" \
    --role user
  ```

- [ ] User Credentials Verified in Database
  ```bash
  psql -U woodful_user -d woodful_creations -c "SELECT id, username, email, role FROM users ORDER BY created_at;"
  ```

---

## Application Launch Sequence

### Terminal 1: PostgreSQL Service
- [ ] PostgreSQL Running
  - Windows: Check Windows Services
  - macOS: `brew services start postgresql`
  - Linux: `sudo systemctl start postgresql`
- [ ] Service Status: Active
- [ ] Port 5432: Listening
  ```bash
  # Verify connection
  psql -U woodful_user -d woodful_creations -c "SELECT NOW();"
  ```

### Terminal 2: Backend (FastAPI)
- [ ] Navigate to backend
  ```bash
  cd backend
  ```

- [ ] Virtual Environment Activated
  - Windows: `venv\Scripts\activate`
  - macOS/Linux: `source venv/bin/activate`

- [ ] FastAPI Server Started
  ```bash
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
  ```

- [ ] Expected Output Observed:
  ```
  INFO:     Will watch for changes in these directories: ['/path/to/backend']
  INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
  INFO:     Started server process
  INFO:     Application startup complete
  ```

- [ ] Backend Health Check
  ```bash
  # In another terminal:
  curl http://localhost:8000/api/health
  ```
  Expected: Success response (200 OK)

- [ ] Swagger UI Accessible
  - Open http://localhost:8000/docs in browser
  - [ ] API endpoints listed
  - [ ] Try it out buttons functional

### Terminal 3: Frontend (React)
- [ ] Navigate to frontend
  ```bash
  cd ../frontend
  ```

- [ ] React Development Server Started
  ```bash
  npm start
  ```

- [ ] Expected Output:
  ```
  On Your Network: http://192.168.x.x:3000
  Compiled successfully!
  ```

- [ ] Browser Opened Automatically
  - [ ] Page loads at http://localhost:3000
  - [ ] No critical errors in console
  - [ ] Page responsive on desktop

- [ ] Console Check (DevTools F12)
  - [ ] No red error messages
  - [ ] API connection message or status
  - [ ] Network tab shows requests

---

## Application Access Verification

### Web Interface
- [ ] URL Accessible: http://localhost:3000
- [ ] Page Loads Completely
- [ ] Login Form Visible
- [ ] Woodful Logo Displays (if configured)
- [ ] Responsive Design Works
  - [ ] Desktop view: Full width
  - [ ] Mobile view: Responsive layout

### Backend API
- [ ] Base URL Accessible: http://localhost:8000
  - [ ] Returns API response
  - [ ] Status code: 200 or 307 (redirect)

- [ ] Swagger UI: http://localhost:8000/docs
  - [ ] All endpoints listed
  - [ ] Authorization button visible
  - [ ] Try it out functionality works

- [ ] ReDoc: http://localhost:8000/redoc
  - [ ] Documentation loaded
  - [ ] Endpoints documented

### Database Connection
- [ ] Connection Verified
  ```bash
  psql -U woodful_user -d woodful_creations -h localhost -c "SELECT version();"
  ```

- [ ] Tables Visible
  ```bash
  psql -U woodful_user -d woodful_creations -c "\dt"
  ```

- [ ] Master Users Visible
  ```bash
  psql -U woodful_user -d woodful_creations -c "SELECT username, role FROM users;"
  ```

---

## Login Functionality Testing

### Test Master Admin Login (Garima)
- [ ] Navigate to http://localhost:3000
- [ ] Enter Username: `garimas`
- [ ] Enter Password: the password you configured locally
- [ ] Click Login Button
- [ ] Verify: Redirected to dashboard
- [ ] Verify: Session token received (check localStorage/cookies)
- [ ] Verify: Full admin controls visible
- [ ] Verify: Can access all modules
- [ ] Verify: Can view all user data

### Test Master Admin Login (Nikhil)
- [ ] Logout from current session
  - [ ] Logout button clicked
  - [ ] Redirected to login page
  - [ ] Session cleared
- [ ] Enter Username: `nikhils`
- [ ] Enter Password: the password you configured locally
- [ ] Click Login Button
- [ ] Verify: Successfully logged in as Nikhil
- [ ] Verify: Full admin access confirmed

### Test Regular User Login (Shweta)
- [ ] Logout from current session
- [ ] Enter Username: `shwetav`
- [ ] Enter Password: the password you configured locally
- [ ] Click Login Button
- [ ] Verify: Successfully logged in
- [ ] Verify: Dashboard visible with limited access
- [ ] Verify: Can only see stock inventory options
- [ ] Verify: Cannot access payment management
- [ ] Verify: Cannot access user management

### Test Login Security
- [ ] Test Invalid Username
  - [ ] Enter non-existent username
  - [ ] Enter valid password
  - [ ] Error message displayed
  - [ ] Not logged in

- [ ] Test Invalid Password
  - [ ] Enter valid username
  - [ ] Enter wrong password
  - [ ] Error message displayed
  - [ ] Not logged in

- [ ] Test Empty Fields
  - [ ] Leave username empty
  - [ ] Error message shown
  - [ ] Try leave password empty
  - [ ] Error message shown

- [ ] Test SQL Injection Attempt
  - [ ] Enter SQL in username field: `admin' OR '1'='1`
  - [ ] Verify: Treated as literal string
  - [ ] Error message shown
  - [ ] Not logged in

---

## API Endpoint Testing

### Authentication Endpoints
- [ ] POST /api/auth/login
  ```bash
  curl -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin1@example.com","password":"<your-password>"}'
  ```
  Expected: 200 OK with token

- [ ] GET /api/auth/me
  ```bash
  curl -H "Authorization: Bearer YOUR_TOKEN" \
    http://localhost:8000/api/auth/me
  ```
  Expected: 200 OK with user data

- [ ] POST /api/auth/logout
  Expected: 200 OK

### User Management Endpoints
- [ ] GET /api/users
  - Master user: Should return all users
  - Regular user: Should return 403 Forbidden

- [ ] GET /api/users/me
  - Should return logged-in user's profile

### Health Check
- [ ] GET /api/health
  Expected: 200 OK

---

## Performance & Security Verification

### Frontend Performance
- [ ] Page Load Time: Under 3 seconds
  - [ ] Initial request: Fast
  - [ ] DOM Content Loaded: Visible
  - [ ] Full Page Load: Complete

- [ ] No Console Errors
  ```bash
  # Open DevTools F12 > Console
  # Should show no red error messages
  ```

- [ ] Memory Usage Reasonable
  - [ ] DevTools > Performance
  - [ ] Check memory profile
  - [ ] No memory leaks detected

### Backend Performance
- [ ] API Response Time: Under 500ms
  ```bash
  # Monitor in Swagger UI
  # Or check Network tab in DevTools
  ```

- [ ] Database Queries Efficient
  - [ ] No N+1 queries
  - [ ] Connection pooling working

### Security Verification
- [ ] No Sensitive Data in Logs
  - [ ] Passwords not logged
  - [ ] API keys not exposed
  - [ ] Tokens not in URLs

- [ ] CORS Configured
  - [ ] Cross-origin requests work
  - [ ] Proper headers set
  - [ ] Unauthorized origins blocked

- [ ] Authentication Secure
  - [ ] JWT tokens in headers
  - [ ] Passwords hashed
  - [ ] Session management working

- [ ] Input Validation
  - [ ] HTML injection blocked
  - [ ] SQL injection prevented
  - [ ] File uploads validated

---

## Browser Compatibility Check

- [ ] Chrome/Edge: Latest version
  - [ ] Login works
  - [ ] Dashboard responsive
  - [ ] API calls successful

- [ ] Firefox: Latest version
  - [ ] All features working
  - [ ] No JavaScript errors
  - [ ] DevTools integration works

- [ ] Safari: Latest version (macOS)
  - [ ] CSS renders correctly
  - [ ] Responsive design works

- [ ] Mobile Browsers (if testing mobile)
  - [ ] Responsive layout active
  - [ ] Touch interactions work
  - [ ] No horizontal scrolling

---

## Troubleshooting & Issue Resolution

### If Any Check Failed

Document the issue:
- [ ] Note which check failed
- [ ] Record error message
- [ ] Document steps to reproduce
- [ ] Check SETUP_GUIDE.md troubleshooting section

### Backend Port Conflicts
- [ ] Stop other services using port 8000
- [ ] Use alternative port if needed
- [ ] Update frontend .env if port changed

### Frontend Port Conflicts
- [ ] Stop other services using port 3000
- [ ] Clear npm cache if issues persist
- [ ] Reinstall node_modules if needed

### Database Connection Issues
- [ ] Verify PostgreSQL service is running
- [ ] Check .env DATABASE_URL is correct
- [ ] Verify database user permissions
- [ ] Check firewall settings

### Login Not Working
- [ ] Verify users created successfully
- [ ] Check backend logs for errors
- [ ] Verify JWT_SECRET_KEY in .env
- [ ] Clear browser cookies and try again

---

## Final Sign-Off

When all checks pass, complete the following:

### Development Team Approval
- [ ] All services running successfully
- [ ] No critical errors or warnings
- [ ] Login functionality verified
- [ ] API endpoints responding
- [ ] Database connected and populated

### Documentation Updated
- [ ] SETUP_GUIDE.md reviewed and complete
- [ ] PROJECT_INFO.md contains latest info
- [ ] Issue resolution documented
- [ ] Troubleshooting steps recorded

### Ready for Development
- [ ] Local environment fully functional
- [ ] All prerequisites met
- [ ] Team ready to begin Phase 1
- [ ] Credentials secured and documented

---

## Launch Sign-Off

**Local Environment Status**: READY / NOT READY (circle one)

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | _____ | _____ | _____ |
| QA Lead | _____ | _____ | _____ |
| Project Manager | _____ | _____ | _____ |

---

## Next Steps After Launch

1. Begin Phase 1: Stock Inventory Module
2. Set up version control workflow
3. Create feature branches for development
4. Set up automated testing
5. Configure CI/CD pipeline
6. Plan sprint schedule

---

## Support Contacts

- Use your internal support contact list for deployment help

---

*Last Updated: June 2026*
*Version: 1.0*
